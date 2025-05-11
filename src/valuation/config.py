import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

POLYGON_API_KEY = os.getenv("POLYGON_API_KEY")
ALPHA_VANTAGE_API_KEY = os.getenv("ALPHA_VANTAGE_API_KEY")

# --- Google Sheets Setup ---
# Assumes this config.py is in src/valuation/
# Project root is two levels up from src/valuation/ which is the parent of src/
_PROJECT_ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
GOOGLE_CREDS_FILENAME = os.path.join(_PROJECT_ROOT_DIR, 'gcp_credential.json')

GINZU_SPREADSHEET_LINK = 'https://docs.google.com/spreadsheets/d/1xclQf2xrgw0swp2CRwE25OBaEhQdDTOkm8VVkTcpVks/edit?usp=sharing'
SPREADSHEET_ID = GINZU_SPREADSHEET_LINK.split('/d/')[1].split('/edit')[0]
INPUT_SHEET_NAME = 'Input sheet'
VALUATION_SHEET_INDEX = 1 # The second sheet (index 1) for B33-B35

# --- Warnings for missing API keys ---
if not POLYGON_API_KEY:
    print("Warning: POLYGON_API_KEY not found in environment variables.")
if not ALPHA_VANTAGE_API_KEY:
    print("Warning: ALPHA_VANTAGE_API_KEY not found in environment variables.") 