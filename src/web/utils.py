import json
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

# Custom JSON encoder to handle datetime objects
class DateTimeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)

async def generate_log_messages(message: Optional[Dict[str, Any]], next_agent: Optional[str], last_agent: Optional[str], final_report: Optional[str], report_status: Optional[str] = None) -> List[Dict[str, Any]]:
    """Generates structured log messages based on agent state and message content."""
    log_messages = []
    
    if message:
        agent_name = message.get("name")
        content_str = message.get("content")
        
        if agent_name and content_str:
            
            # Special handling for analyst and reporter before trying to parse JSON
            if agent_name == "analyst":
                log_messages.append({"type": "agent_output", "agent": agent_name, "content": f"Analyst has finished generating insight."})
            elif agent_name == "reporter":
                # Reporter status will be handled separately based on report_status
                if report_status == "saved":
                    log_messages.append({"type": "agent_output", "agent": agent_name, "content": f"Reporter agent has finished and the report has been saved."})
                elif report_status == "error":
                     log_messages.append({"type": "error", "agent": agent_name, "content": f"Reporter agent finished, but there was an error saving the report."})
                else:
                     log_messages.append({"type": "agent_output", "agent": agent_name, "content": f"Reporter agent is processing"})
            else:
                # For all other agents, try to parse the content
                try:
                    content = json.loads(content_str) if isinstance(content_str, str) else content_str
                    
                    if agent_name == "planner":
                        if isinstance(content, dict):
                            log_messages.append({"type": "agent_output", "agent": agent_name, "content": f"Plan Title: {content.get('title', 'N/A')}"}) # Keep title for debugging/log
                            log_messages.append({"type": "agent_output", "agent": agent_name, "content": f"Thought: {content.get('thought', 'N/A')}"})

                            for step in content.get('steps', []):
                                 log_messages.append({"type": "plan_step", "agent": step.get('agent'), "content": {
                                     "Task": step.get('task'),
                                     "Agent": step.get('agent'),
                                     "Description": step.get('description'),
                                     "Note": step.get('note')
                                 }})
                        else:
                             log_messages.append({"type": "agent_output", "agent": agent_name, "content": f"Received planner content (non-dict): {content_str}"})

                    elif agent_name == "coordinator":
                        if isinstance(content, dict):
                            log_messages.append({"type": "agent_output", "agent": agent_name, "content": f"Coordinator processed query and set time range: {content.get('time_range', 'N/A')}"})
                        else:
                            log_messages.append({"type": "agent_output", "agent": agent_name, "content": f"Received coordinator content (non-dict): {content_str}"})

                    elif agent_name == "supervisor":
                         if isinstance(content, dict):
                            log_messages.append({"type": "status", "content": f"Supervisor assigned the following task to {next_agent or 'N/A'}: \n{content.get('task', 'N/A')}"})
                         else:
                            log_messages.append({"type": "agent_output", "agent": agent_name, "content": f"Received supervisor content (non-dict): {content_str}"})


                    elif agent_name == "researcher":
                        if isinstance(content, dict):
                            log_messages.append({"type": "agent_output", "agent": agent_name, "content": f"Researcher finished: {content.get('result_summary', 'No summary provided.')}"})
                        else:
                             log_messages.append({"type": "agent_output", "agent": agent_name, "content": f"Received researcher content (non-dict): {content_str}"})

                    elif agent_name == "coder":
                         if isinstance(content, dict):
                            log_messages.append({"type": "agent_output", "agent": agent_name, "content": f"Coder finished: {content.get('result_summary', 'No summary provided.')}"})
                         else:
                            log_messages.append({"type": "agent_output", "agent": agent_name, "content": f"Received coder content (non-dict): {content_str}"})

                    elif agent_name == "market":
                         if isinstance(content, dict):
                            log_messages.append({"type": "agent_output", "agent": agent_name, "content": f"Market agent finished: {content.get('result_summary', 'No summary provided.')}"})
                         else:
                            log_messages.append({"type": "agent_output", "agent": agent_name, "content": f"Received market content (non-dict): {content_str}"})
                    
                    else: # Handle other or unknown agent names
                        log_messages.append({"type": "agent_output", "agent": agent_name, "content": f"{agent_name.capitalize()} content: {content_str}"})

                except json.JSONDecodeError:
                    log_messages.append({"type": "agent_output", "agent": agent_name, "content": f"{agent_name.capitalize()} raw content: {content_str}"})
                except Exception as e:
                    log_messages.append({"type": "error", "content": f"Error processing message from {agent_name}: {e}"})
        
        elif agent_name: # Content is None or empty
             log_messages.append({"type": "status", "content": f"Received empty message from {agent_name}."})


    if next_agent:
        status_message = f"Waiting for {next_agent}..." # Default message
        if next_agent == "planner":
            status_message = 'Planner is thinking'
        elif next_agent == "supervisor":
            status_message = f'Supervisor is evaluating response from {last_agent or "previous agent"}...' # Keep this detail
        elif next_agent == "researcher":
            status_message = 'Researcher is gathering information'
        elif next_agent == "coder":
            status_message = 'Coder is coding'
        elif next_agent == "market":
            status_message = 'Market agent is retrieving market data'
        elif next_agent == "browser":
            status_message = 'Browser agent is browsing the web'
        elif next_agent == "analyst":
            status_message = 'Analyst agent is analyzing the gathered information'
        elif next_agent == "reporter":
             # Don't signal report readiness here; wait for save confirmation
             status_message = 'Reporter agent is preparing the final report'
        elif next_agent == "coordinator":
            status_message = 'Coordinator is processing the query'

        log_messages.append({"type": "status", "agent": next_agent, "content": status_message})

    return log_messages

async def format_report_status_update(session_id: str, status: str, error_message: Optional[str] = None) -> str:
    """Formats an SSE message specifically for report status updates."""
    sse_data = {
        "type": "report_status",
        "session_id": session_id,
        "status": status, # e.g., 'saved', 'error'
    }
    if status == 'error' and error_message:
        sse_data["error_message"] = error_message
    
    return json.dumps(sse_data, cls=DateTimeEncoder)

async def format_chunk_for_streaming(chunk, report_status: Optional[str] = None):
    """Formats a LangGraph chunk into structured log messages for streaming."""
    try:
        messages_data = chunk.data.get("messages", [])
        next_agent = chunk.data.get("next", None)
        last_agent = chunk.data.get("last_agent", None)
        
        # Sanitize messages if necessary (keep existing logic)
        if messages_data:
            for i, msg in enumerate(messages_data):
                if isinstance(msg, dict) and 'content' in msg and isinstance(msg['content'], str):
                    try:
                        json.dumps(msg['content'])
                    except (TypeError, json.JSONDecodeError):
                        logger.warning(f"Problematic content detected in message from {msg.get('name', 'unknown')}. Content was: {msg['content'][:100]}...")
        # Use the latest message if available
        latest_message = messages_data[-1] if messages_data else None

        logger.debug(f"Processing chunk: last_agent={last_agent}, next_agent={next_agent}, message={latest_message is not None}")

        # Generate structured log messages, passing the report status
        log_messages = await generate_log_messages(latest_message, next_agent, last_agent, None, report_status=report_status)
        
        # Structure the SSE data
        sse_data = {
            "logs": log_messages,
            "next": next_agent,
            "last_agent": last_agent,
            "messages": [latest_message] if latest_message else []
        }

        # Convert to JSON string
        try:
            json_data = json.dumps(sse_data, cls=DateTimeEncoder)
            logger.debug(f"Streaming chunk size: {len(json_data)} bytes")
            return json_data
        except json.JSONDecodeError as json_err:
            logger.error(f"JSON encoding error: {json_err}. Sanitizing data and retrying.")
            safe_sse_data = {
                "logs": log_messages,
                "next": next_agent,
                "last_agent": last_agent,
                "messages": [] 
            }
            return json.dumps(safe_sse_data, cls=DateTimeEncoder)
    except Exception as e:
        logger.error(f"Error formatting chunk for streaming: {e}", exc_info=True)
        return json.dumps({"error": f"Error formatting chunk: {str(e)}"})