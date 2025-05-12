import os
import sys
import gspread
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

from .config import GOOGLE_CREDS_FILENAME, GINZU_SPREADSHEET_LINK, VALUATION_SHEET_INDEX

# Globals for Google Sheets access
gc = None
input_worksheet = None
valuation_worksheet = None
service = None
google_sheets_initialized = False # Added flag

def initialize_google_sheets():
    global gc, input_worksheet, valuation_worksheet, service, google_sheets_initialized
    if google_sheets_initialized: # Prevent re-initialization
        return
    try:
        print(f"Attempting to load Google credentials from: {GOOGLE_CREDS_FILENAME}")
        current_creds_file = GOOGLE_CREDS_FILENAME
        if not os.path.exists(GOOGLE_CREDS_FILENAME):
            print(f"ERROR: Google credentials file NOT FOUND at '{GOOGLE_CREDS_FILENAME}'.")
            # Fallback logic for credentials path (adjust if needed)
            fallback_creds_path_cwd = os.path.join(os.getcwd(), 'gcp_credential.json')
            if os.path.exists(fallback_creds_path_cwd):
                print(f"Attempting fallback credentials path (current working dir): {fallback_creds_path_cwd}")
                current_creds_file = fallback_creds_path_cwd
            else:
                print("All fallback paths for credentials failed.")
                sys.exit(1) # Exit if credentials are not found
            
        print(f"Using credentials file: {current_creds_file}")
        gc = gspread.service_account(filename=current_creds_file)
        pricer = gc.open_by_url(GINZU_SPREADSHEET_LINK)
        input_worksheet = pricer.get_worksheet(0) # Input sheet is index 0
        valuation_worksheet = pricer.get_worksheet(1)

        creds = Credentials.from_service_account_file(current_creds_file, scopes=['https://www.googleapis.com/auth/spreadsheets'])
        service = build('sheets', 'v4', credentials=creds)
        google_sheets_initialized = True
        print("Google Sheets initialized successfully.")
    except FileNotFoundError:
        print(f"CRITICAL ERROR: Google credentials file not found at specified paths.")
        sys.exit(1)
    except Exception as e:
        print(f"Error initializing Google Sheets: {e}")
        print("Please ensure your Google credentials file is correctly set up, the sheet URL is accessible, and the service account has permissions.")
        sys.exit(1)

def get_dropdown_options(spreadsheet_id: str, sheet_name: str, cell: str) -> list:
    if not service: # Check if service is initialized
        print("Google Sheets service not initialized. Cannot get dropdown options.")
        initialize_google_sheets() # Attempt to initialize if not already
        if not service: return [] # Return empty if initialization fails

    range_name = f"'{sheet_name}'!{cell}"
    try:
        response = service.spreadsheets().get(
            spreadsheetId=spreadsheet_id,
            ranges=[range_name],
            includeGridData=True,
            fields='sheets.data.rowData.values.dataValidation'
        ).execute()

        validation_path = response.get('sheets', [{}])[0].get('data', [{}])[0].get('rowData', [{}])[0].get('values', [{}])[0].get('dataValidation')
        if not validation_path:
            print(f"No data validation found at {sheet_name}!{cell}.")
            return []
            
        condition = validation_path['condition']
        dropdown_values_raw = condition.get('values', [])
        if not dropdown_values_raw:
            print(f"No values in dropdown condition for {sheet_name}!{cell}.")
            return []

        dropdown_values = [v['userEnteredValue'] for v in dropdown_values_raw if 'userEnteredValue' in v]

        if not dropdown_values:
             print(f"No 'userEnteredValue' in dropdown values for {sheet_name}!{cell}.")
             return []

        dropdown_ref = dropdown_values[0]
        if isinstance(dropdown_ref, str) and dropdown_ref.startswith("="):
            raw_ref = dropdown_ref.lstrip("=").replace("'", "")
            ref_sheet_parts = raw_ref.split("!")
            if len(ref_sheet_parts) != 2:
                print(f"Could not parse dropdown range reference: {dropdown_ref}")
                return [str(v).strip() for v in dropdown_values if str(v).strip()] # return literals if parse fails
            
            ref_sheet, ref_range = ref_sheet_parts
            
            range_query = f"{ref_sheet}!{ref_range}" 
            print(f"Fetching dropdown options from range: {range_query}")
            values_resp = service.spreadsheets().values().get(
                spreadsheetId=spreadsheet_id,
                range=range_query
            ).execute()
            return [row[0].strip() for row in values_resp.get("values", []) if row and row[0] and isinstance(row[0], str) and row[0].strip()]
        else: # Hardcoded list
            return [str(v).strip() for v in dropdown_values if str(v).strip()]
    except (KeyError, IndexError, TypeError) as e:
        print(f"Error parsing dropdown at {sheet_name}!{cell}: {e}. Check sheet structure and validation rules.")
        return []
    except Exception as e:
        print(f"An unexpected error occurred in get_dropdown_options for {cell}: {e}")
        return [] 