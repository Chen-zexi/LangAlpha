import os
from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_anthropic import ChatAnthropic
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

from market_intelligence_agent.config import (
    REASONING_MODEL,
    REASONING_MODEL_PROVIDER,
    BASIC_MODEL,
    BASIC_MODEL_PROVIDER,
    CODING_MODEL,
    CODING_MODEL_PROVIDER,
    ECONOMIC_MODEL,
    ECONOMIC_MODEL_PROVIDER,
)
from market_intelligence_agent.config.agents import LLMType


def create_reasoning_llm(
        model: str,
        provider: str,
        **kwargs
) -> ChatOpenAI | ChatGoogleGenerativeAI | ChatAnthropic:
    """
    Create a LLM instance with the specified configuration
    """
    if provider in ["OPENAI", "openai"]:
        return ChatOpenAI(model=model, api_key=os.getenv("OPENAI_API_KEY"), **kwargs)
    else:
        raise ValueError(f"Unknown model: {model}")
    

def create_basic_llm(
    model: str,
    provider: str,
    temperature: float = 0.0,
    **kwargs
) -> ChatOpenAI | ChatGoogleGenerativeAI | ChatAnthropic:
    """
    Create a basic LLM inst ance with the specified configuration
    """
    if provider in ["OPENAI", "openai"]:
        return ChatOpenAI(model=model, temperature=temperature, api_key=os.getenv("OPENAI_API_KEY"), use_responses_api=False, **kwargs)
    elif provider in ["GEMINI", "gemini"]:
        return ChatGoogleGenerativeAI(model=model, temperature=temperature, api_key=os.getenv("GEMINI_API_KEY"), **kwargs)
    elif provider in ["ANTHROPIC", "anthropic"]:
        return ChatAnthropic(model=model, temperature=temperature, api_key=os.getenv("ANTHROPIC_API_KEY"), **kwargs)
    else:
        raise ValueError(f"Unknown model: {model}")
    
    
def create_coding_llm(
    model: str,
    provider: str,
    **kwargs
) -> ChatOpenAI | ChatGoogleGenerativeAI | ChatAnthropic:
    """
    Create a coding LLM instance with the specified configuration
    """
    if provider in ["OPENAI", "openai"]:
        return ChatOpenAI(model=model, api_key=os.getenv("OPENAI_API_KEY"), **kwargs)
    else:
        raise ValueError(f"Unknown model: {model}")
    
def create_economic_llm(
    model: str,
    provider: str,
    **kwargs
) -> ChatOpenAI | ChatGoogleGenerativeAI | ChatAnthropic:
    """
    Create a economic LLM instance with the specified configuration
    """
    if provider in ["OPENAI", "openai"]:
        return ChatOpenAI(model=model, api_key=os.getenv("OPENAI_API_KEY"), **kwargs)
    else:
        raise ValueError(f"Unknown model: {model}")

_llm_cache: dict[LLMType, ChatOpenAI | ChatGoogleGenerativeAI | ChatAnthropic] = {}

def get_llm_by_type(llm_type: LLMType) -> ChatOpenAI | ChatGoogleGenerativeAI | ChatAnthropic:
    """
    Get LLM instance by type. Returns cached instance if available.
    """
    if llm_type in _llm_cache:
        return _llm_cache[llm_type]

    if llm_type == "reasoning":
        llm = create_reasoning_llm(
            model=REASONING_MODEL,
            provider=REASONING_MODEL_PROVIDER,
        )
    elif llm_type == "basic":
        llm = create_basic_llm(
            model=BASIC_MODEL,
            provider=BASIC_MODEL_PROVIDER,
        )
    elif llm_type == "coding":
        llm = create_coding_llm(
            model=CODING_MODEL,
            provider=CODING_MODEL_PROVIDER,
        )
    elif llm_type == "economic":
        llm = create_economic_llm(
            model=ECONOMIC_MODEL,
            provider=ECONOMIC_MODEL_PROVIDER,
        )
    else:
        raise ValueError(f"Unknown LLM type: {llm_type}")

    _llm_cache[llm_type] = llm
    return llm


# Initialize LLMs for different purposes - now these will be cached
reasoning_llm = get_llm_by_type("reasoning")
basic_llm = get_llm_by_type("basic")
coding_llm = get_llm_by_type("coding")
economic_llm = get_llm_by_type("economic")


if __name__ == "__main__":
    stream = reasoning_llm.stream("what is mcp?")
    full_response = ""
    for chunk in stream:
        full_response += chunk.content
    print(full_response)

    basic_llm.invoke("Hello")
