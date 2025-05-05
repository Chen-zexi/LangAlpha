import os
import logging
from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_anthropic import ChatAnthropic
from langchain_google_vertexai import ChatVertexAI
from langchain_xai import ChatXAI
from typing import Optional, Dict, Any
from dotenv import load_dotenv

load_dotenv()

from ..config.agents import LLMType
from ..graph.types import ModelConfig

logger = logging.getLogger(__name__)

# --- Default Configurations (Fallback if not provided in state) ---
def _get_default_llm_config(llm_type: LLMType) -> ModelConfig:
    if llm_type == "reasoning":
        return ModelConfig(model=os.getenv("REASONING_MODEL", "gpt-4.1"), provider=os.getenv("REASONING_MODEL_PROVIDER", "OPENAI"))
    elif llm_type == "basic":
        return ModelConfig(model=os.getenv("BASIC_MODEL", "gpt-4.1-mini"), provider=os.getenv("BASIC_MODEL_PROVIDER", "OPENAI"))
    elif llm_type == "coding":
        return ModelConfig(model=os.getenv("CODING_MODEL", "gpt-4.1"), provider=os.getenv("CODING_MODEL_PROVIDER", "OPENAI"))
    elif llm_type == "economic":
        return ModelConfig(model=os.getenv("ECONOMIC_MODEL", "gpt-4.1-mini"), provider=os.getenv("ECONOMIC_MODEL_PROVIDER", "OPENAI"))
    else:
        # Fallback to a generic default if type is unknown
        return ModelConfig(model=os.getenv("BASIC_MODEL", "gpt-4o-mini"), provider=os.getenv("BASIC_MODEL_PROVIDER", "OPENAI"))


def create_llm_from_config(
        config: ModelConfig,
        **kwargs
) -> ChatOpenAI | ChatGoogleGenerativeAI | ChatAnthropic | ChatXAI:
    """
    Create an LLM instance based on the provided ModelConfig.
    API keys are still read from environment variables.
    """
    provider = config.provider.upper()
    model = config.model
    
    # Allow overriding temperature via kwargs if needed
    temperature = kwargs.pop('temperature', 0.0 if provider != 'OPENAI' else 0.7) # Example default logic

    if provider == "OPENAI":
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable not set.")
        return ChatOpenAI(model=model, api_key=api_key, temperature=temperature, max_retries=3, **kwargs)
    elif provider == "GEMINI":
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY environment variable not set.")
        return ChatGoogleGenerativeAI(model=model, api_key=api_key, temperature=temperature, max_retries=3,**kwargs)
    elif provider == "VERTEXAI":
        return ChatVertexAI(model=model,temperature=temperature, max_retries=3,**kwargs)
    elif provider == "ANTHROPIC":
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable not set.")
        return ChatAnthropic(model=model, api_key=api_key, temperature=temperature, max_retries=3,**kwargs)
    elif provider == "XAI":
        api_key = os.getenv("XAI_API_KEY")
        if not api_key:
            raise ValueError("XAI_API_KEY environment variable not set.")
        return ChatXAI(model=model, api_key=api_key, temperature=temperature, max_retries=3,**kwargs)
    else:
        raise ValueError(f"Unknown LLM provider specified in config: {config.provider}")

def get_llm_by_type(llm_type: LLMType, llm_configs: Optional[Dict[str, Any]] = None) -> ChatOpenAI | ChatGoogleGenerativeAI | ChatAnthropic | ChatXAI:
    """
    Get LLM instance by type, using configuration from the provided llm_configs dict.
    Falls back to environment variables if configs are not provided or incomplete.
    Does NOT use caching anymore.
    """
    config_dict = None
    if llm_configs and llm_type in llm_configs:
        config_data = llm_configs[llm_type]
        if isinstance(config_data, dict):
            config_dict = config_data
        elif isinstance(config_data, ModelConfig):
            config_dict = config_data.model_dump()
        else:
             logger.warning(f"Invalid config format for {llm_type} in llm_configs. Falling back to defaults.")

    if config_dict:
        try:
            model_config = ModelConfig(**config_dict)
            logger.info(f"Using config for {llm_type}: Model={model_config.model}, Provider={model_config.provider}")
            llm = create_llm_from_config(model_config)
        except Exception as e:
            logger.error(f"Error creating LLM from config for type {llm_type}: {e}. Falling back to defaults.")
            default_config = _get_default_llm_config(llm_type)
            llm = create_llm_from_config(default_config)
    else:
        logger.warning(f"LLM config for type '{llm_type}' not found in state. Using default from env vars.")
        default_config = _get_default_llm_config(llm_type)
        llm = create_llm_from_config(default_config)

    return llm
