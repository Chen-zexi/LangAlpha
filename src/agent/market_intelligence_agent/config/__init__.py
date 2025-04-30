from .env import (
    # Reasoning LLM
    REASONING_MODEL,
    REASONING_MODEL_PROVIDER,
    # Basic LLM
    BASIC_MODEL,
    BASIC_MODEL_PROVIDER,
    # Economic LLM
    ECONOMIC_MODEL,
    ECONOMIC_MODEL_PROVIDER,
    # Coding LLM
    CODING_MODEL,
    CODING_MODEL_PROVIDER,
    # Vision-language LLM
    CHROME_INSTANCE_PATH,
)

# Team configuration
TEAM_MEMBERS = ["researcher", "coder", "reporter", "market", "browser", "analyst"]

__all__ = [
    # Reasoning LLM
    "REASONING_MODEL",
    "REASONING_MODEL_PROVIDER",
    # Basic LLM
    "BASIC_MODEL",
    "BASIC_MODEL_PROVIDER",
    # Economic LLM
    "ECONOMIC_MODEL",
    "ECONOMIC_MODEL_PROVIDER",
    # Coding LLM
    "CODING_MODEL",
    "CODING_MODEL_PROVIDER",
    # Other configurations
    "TEAM_MEMBERS",
    "CHROME_INSTANCE_PATH",
]
