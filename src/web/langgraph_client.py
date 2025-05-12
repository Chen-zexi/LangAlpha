import os
import logging
import asyncio
import json
from datetime import datetime
from typing import List, Dict, Any, Optional
import uuid
import yfinance as yf

from langgraph_sdk import get_client

from agent.market_intelligence_agent.config import TEAM_MEMBERS
from agent.market_intelligence_agent.config.agents import get_agent_llm_map

from database.models.messages import Message, save_message
from database.models.reports import Report, save_report

from .schemas import WorkflowConfig
from .utils import DateTimeEncoder, format_report_status_update, format_chunk_for_streaming

logger = logging.getLogger(__name__)

# LangGraph client setup
async def get_lg_client_and_thread():
    """Creates a LangGraph client and thread."""
    logger.debug("Creating LangGraph client and thread")
    try:
        LANGGRAPH_API_URL = os.getenv("LANGGRAPH_API_URL", "http://langgraph-api:8000")
        lg_client = get_client(url=LANGGRAPH_API_URL)
        thread_info = await lg_client.threads.create()
        logger.debug(f"Created thread: {thread_info}")
        return lg_client, thread_info
    except Exception as e:
        logger.error(f"Error creating LangGraph client and thread: {e}")
        raise

async def stream_with_heartbeat(langgraph_stream, heartbeat_interval=20): # Interval of 20s
    """Wraps a LangGraph stream to inject heartbeat messages if the stream is idle."""
    logger.debug(f"Heartbeat wrapper activated with interval: {heartbeat_interval}s")
    langgraph_iter = langgraph_stream.__aiter__()
    
    next_item_task = None

    while True:
        if next_item_task is None:
            next_item_task = asyncio.create_task(langgraph_iter.__anext__())
        
        timeout_task = asyncio.create_task(asyncio.sleep(heartbeat_interval))
        
        done, pending = await asyncio.wait(
            [next_item_task, timeout_task],
            return_when=asyncio.FIRST_COMPLETED
        )
        
        if next_item_task in done:
            if timeout_task in pending:
                timeout_task.cancel()
                try:
                    await timeout_task
                except asyncio.CancelledError:
                    pass

            try:
                chunk = await next_item_task
                yield chunk
                next_item_task = None
            except StopAsyncIteration:
                logger.debug("Upstream LangGraph stream finished.")
                break
            except Exception as e:
                logger.error(f"Error in stream_with_heartbeat (data task): {e}", exc_info=True)
                next_item_task = None
                raise
        
        elif timeout_task in done:
            logger.debug("Sending heartbeat message due to stream inactivity.")
            yield {"type": "heartbeat", "timestamp": datetime.now().isoformat(), "session_id": "heartbeat_session"}

async def stream_workflow_results(query: str, config: WorkflowConfig, session_id: str):
    """Stream results from the LangGraph workflow and save report directly."""
    logger.info(f"Starting workflow stream for query: '{query}' with budget: {config.budget}, session_id: {session_id}")
    
    if config.llm_configs:
        logger.info(f"Using custom LLM configurations provided in request.")
    else:
        logger.info(f"No custom LLM configurations provided, will use defaults based on env vars.")
        
    lg_client, thread_info = await get_lg_client_and_thread()
    
    agent_llm_map = get_agent_llm_map(config.budget)
    logger.debug(f"Using agent LLM map: {agent_llm_map}")
    
    llm_configs_dict = config.llm_configs.model_dump() if config.llm_configs else None
    if llm_configs_dict:
        logger.debug(f"Passing LLM configs to state: {llm_configs_dict}")
        for llm_type, llm_config_item in llm_configs_dict.items(): # Renamed llm_config to llm_config_item to avoid conflict
            logger.info(f"LLM config for {llm_type}: {llm_config_item}")
    else:
        logger.warning("No LLM configs provided, using defaults")

    try:
        initial_message = json.dumps({
            "type": "connection_established",
            "message": "Streaming connection established. Starting analysis...",
            "session_id": session_id
        })
        yield f"data: {initial_message}\n\n"
        
        planner_title = f"Analysis for: {query}"
        final_report_content = None
        report_saved_or_failed = False
        report_save_status = None
        ticker_type = None
        ticker_info_list: Optional[List[Dict[str, Any]]] = None

        langgraph_actual_stream = lg_client.runs.stream(
            thread_info["thread_id"],
            "market_intelligence_agent",
            input={
                "TEAM_MEMBERS": config.team_members or TEAM_MEMBERS,
                "messages": [query],
                "current_timestamp": datetime.now(),
                "researcher_credits": config.researcher_credits,
                "market_credits": config.market_credits,
                "coder_credits": config.coder_credits,
                "browser_credits": config.browser_credits,
                "agent_llm_map": agent_llm_map, 
                "llm_configs": llm_configs_dict,
            },
            config={
                "recursion_limit": config.stream_config.recursion_limit if config.stream_config else 150 # Ensure stream_config exists
            },
            stream_mode=["values", "custom"]
        )

        async for item in stream_with_heartbeat(langgraph_actual_stream):
            try:
                if isinstance(item, dict) and item.get("type") == "heartbeat":
                    heartbeat_message_content = {
                        "type": "heartbeat",
                        "session_id": session_id,
                        "timestamp": item["timestamp"]
                    }
                    heartbeat_sse_message = json.dumps(heartbeat_message_content)
                    logger.debug(f"Yielding heartbeat SSE: {heartbeat_sse_message}")
                    yield f"data: {heartbeat_sse_message}\n\n"
                    continue

                chunk = item

                messages_data = chunk.data.get("messages", [])
                if messages_data:
                    for message_item in messages_data: # Renamed message to message_item
                        if message_item and message_item.get("name") == "planner":
                            content_str = message_item.get("content", "")
                            try:
                                content_dict = json.loads(content_str) if isinstance(content_str, str) else content_str
                                if isinstance(content_dict, dict) and "title" in content_dict:
                                    planner_title = content_dict["title"]
                                    logger.info(f"Extracted planner title: {planner_title} for session {session_id}")
                            except (json.JSONDecodeError, TypeError):
                                logger.warning(f"Could not parse planner content for title: {content_str}")
                
                chunk_ticker_type = chunk.data.get("ticker_type", None)
                if chunk_ticker_type:
                    ticker_type = chunk_ticker_type.lower()
                    logger.info(f"Received ticker type update: {ticker_type} for session {session_id}")

                chunk_tickers = chunk.data.get("tickers", None)
                if chunk_tickers:
                    ticker_info_list = chunk_tickers
                    logger.info(f"Received ticker information update for session {session_id}: {ticker_info_list}")
                
                current_final_report = chunk.data.get("final_report", None)
                if current_final_report:
                    final_report_content = current_final_report
                    logger.info(f"Received final_report content for session {session_id}. Preparing to save.")

                    validated_ticker_info_list = []
                    if ticker_info_list:
                        logger.info(f"Attempting validation for tickers: {ticker_info_list}")
                        possible_exchanges = ["NASDAQ", "NYSE", "AMEX"]
                        
                        for ticker_info_item in ticker_info_list: # Renamed ticker_info
                            original_symbol = ticker_info_item.get('tradingview_symbol') or ticker_info_item.get('ticker')
                            if not original_symbol:
                                logger.warning(f"Skipping validation for ticker_info_item with no symbol: {ticker_info_item}")
                                validated_ticker_info_list.append(ticker_info_item)
                                continue

                            base_ticker = original_symbol.split(':')[-1]
                            validated = False
                            validated_symbol = None

                            exchanges_to_try = possible_exchanges[:]
                            if ':' in original_symbol:
                                provided_exchange = original_symbol.split(':')[0].upper()
                                if provided_exchange in exchanges_to_try:
                                     exchanges_to_try = [provided_exchange] + [ex for ex in possible_exchanges if ex != provided_exchange]
                                else:
                                     exchanges_to_try = [provided_exchange] + possible_exchanges

                            logger.debug(f"Validation order for {base_ticker}: {exchanges_to_try}")

                            for exchange in exchanges_to_try:
                                try_symbol = f"{exchange}:{base_ticker}"
                                try:
                                    logger.debug(f"Trying yfinance validation for: {try_symbol}")
                                    yf_ticker = yf.Ticker(base_ticker)
                                    info = yf_ticker.info
                                    if info and info.get('symbol'): 
                                        validated_symbol = f"{exchange}:{base_ticker}"
                                        logger.info(f"Validation successful for {base_ticker} on {exchange}. Using: {validated_symbol}")
                                        validated = True
                                        break
                                    else:
                                         logger.debug(f"No sufficient info from yfinance for {base_ticker} (tried as {try_symbol})")
                                except Exception as yf_error:
                                    logger.warning(f"yfinance error validating {try_symbol}: {yf_error}")

                            if validated:
                                ticker_info_item['tradingview_symbol'] = validated_symbol
                            else:
                                logger.warning(f"Could not validate {base_ticker} on {exchanges_to_try}. Keeping original/best guess: {original_symbol}")
                                ticker_info_item['tradingview_symbol'] = original_symbol
                            
                            validated_ticker_info_list.append(ticker_info_item)
                    else:
                         validated_ticker_info_list = ticker_info_list

                    ticker_info_list = validated_ticker_info_list

                    if session_id and planner_title and final_report_content and not report_saved_or_failed:
                        report_metadata: Dict[str, Any] = {
                            "query": query
                        }
                        if ticker_type:
                            report_metadata["ticker_type"] = ticker_type
                        if ticker_info_list:
                            report_metadata["tickers"] = ticker_info_list
                            
                        report_to_save: Report = {
                            "session_id": session_id,
                            "timestamp": datetime.now(),
                            "title": planner_title,
                            "content": final_report_content,
                            "metadata": report_metadata
                        }
                        saved_report = save_report(report_to_save)
                        if saved_report:
                            logger.info(f"Successfully saved/updated report for session {session_id}")
                            report_save_status = "saved"
                        else:
                            logger.error(f"Failed to save report for session {session_id}")
                            report_save_status = "error"
                        report_saved_or_failed = True
                        
                        report_update_message = await format_report_status_update(session_id, report_save_status)
                        yield f"data: {report_update_message}\n\n"
                
                formatted_chunk = await format_chunk_for_streaming(chunk, report_status=report_save_status)
                
                try:
                    chunk_data = json.loads(formatted_chunk)
                    chunk_data["session_id"] = session_id
                    formatted_chunk = json.dumps(chunk_data, cls=DateTimeEncoder) # Ensure DateTimeEncoder is used here too
                except json.JSONDecodeError as json_err:
                    logger.error(f"Error adding session_id to chunk: {json_err}")

                yield f"data: {formatted_chunk}\n\n"
            
            except Exception as e:
                logger.error(f"Error processing chunk: {e}", exc_info=True)
                error_data = json.dumps({
                    "error": "Error processing chunk",
                    "details": str(e),
                    "type": "chunk_error",
                    "session_id": session_id
                }, cls=DateTimeEncoder)
                yield f"data: {error_data}\n\n"
            
        final_message_dict = {
            "type": "stream_complete",
            "message": "Analysis stream complete.",
            "session_id": session_id,
            "report_status": report_save_status if report_saved_or_failed else "not_generated"
        }
        yield f"data: {json.dumps(final_message_dict, cls=DateTimeEncoder)}\n\n"
        
    except Exception as e:
        logger.error(f"Error streaming workflow results for session {session_id}: {e}", exc_info=True)
        try:
            # Explicitly type hint error_database_message if Message is a TypedDict or Pydantic model
            error_database_message_content: Dict[str, Any] = {
                "session_id": session_id,
                "timestamp": datetime.now(),
                "role": "system",
                "content": f"Error during stream: {str(e)}",
                "type": "error",
                "metadata": {
                    # thread_info might not be defined if get_lg_client_and_thread failed
                    "thread_id": thread_info["thread_id"] if thread_info else "unknown",
                    "error_details": str(e)
                }
            }
            # If Message is a Pydantic model: save_message(Message(**error_database_message_content))
            # If Message is a TypedDict: save_message(error_database_message_content) - assuming save_message expects a dict
            save_message(error_database_message_content) # Assuming save_message can take a dict
        except Exception as db_error:
            logger.error(f"Failed to save stream error message to MongoDB: {db_error}")
        
        error_message_dict = {
            "error": "An error occurred during the analysis stream.",
            "details": str(e),
            "type": "stream_error",
            "session_id": session_id
        }
        yield f"data: {json.dumps(error_message_dict, cls=DateTimeEncoder)}\n\n" 