import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Reasoning LLM configuration (for complex reasoning tasks)
REASONING_MODEL = os.getenv("REASONING_MODEL", "o3")
REASONING_MODEL_PROVIDER = os.getenv("REASONING_MODEL_PROVIDER", "OPENAI")

# Non-reasoning LLM configuration (for straightforward tasks)
BASIC_MODEL = os.getenv("BASIC_MODEL", "gpt-4.1")
BASIC_MODEL_PROVIDER = os.getenv("BASIC_MODEL_PROVIDER", "OPENAI")

