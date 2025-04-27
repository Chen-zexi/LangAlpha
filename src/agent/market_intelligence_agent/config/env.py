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

ECONOMIC_MODEL = os.getenv("ECONOMIC_MODEL", "gpt-4.1-mini")
ECONOMIC_MODEL_PROVIDER = os.getenv("ECONOMIC_MODEL_PROVIDER", "OPENAI")

CODING_MODEL = os.getenv("CODING_MODEL", "o4-mini")
CODING_MODEL_PROVIDER = os.getenv("CODING_MODEL_PROVIDER", "OPENAI")

CHROME_INSTANCE_PATH = os.getenv("CHROME_INSTANCE_PATH", None)

