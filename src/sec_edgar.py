from secedgar import filings, FilingType
import os
import sys
import warnings

sys.path.append(os.path.abspath('..'))
warnings.filterwarnings("ignore", category=FutureWarning)

class sec_edgar:
    def __init__(self, user_agent='zc2610@nyu.edu'):
        self.user_agent = user_agent
    
    def get_filings(self, ticker='AAPL'):
        # 10Q filings for Apple (ticker "aapl")
        my_filings = filings(cik_lookup=ticker,
                            filing_type=FilingType.FILING_10Q,
                            user_agent=self.user_agent)
        try:
            my_filings.save('data/sec_edgar')
        except Exception as e:
            print(f"Error: {e}")
            print(f"Failed to save filings for {ticker}")
            print(f"Please check the ticker and try again.")
            print(f"If the problem persists, please contact the developer.")
            print(f"Error: {e}")