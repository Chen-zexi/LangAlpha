import os
import wrds
import pandas as pd
from datetime import datetime, timedelta
import logging

# Configure logging to show info level messages
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Default tech stock tickers
DEFAULT_TICKERS = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'META', 'TSLA', 'NFLX', 'ADBE',
                'CRM', 'AMD', 'INTC', 'AVGO', 'QCOM', 'SHOP', 'ZM', 'SNOW', 'PYPL', 'PLTR']


class WRDSConnector:
    """Class to handle WRDS connection and data retrieval."""
    
    def __init__(self, username=None, tickers=None, start_date=None, end_date=None):
        """Initialize WRDS connection."""
        self.username = username or os.environ.get('WRDS_USERNAME', 'zxchen')
        self.db = None
        self.ticker_gvkeys = None
        
        # Set tickers (use default if not provided)
        self.tickers = tickers or DEFAULT_TICKERS
        
        # Set date range
        if end_date:
            self.end_date = datetime.strptime(end_date, '%Y-%m-%d') if isinstance(end_date, str) else end_date
        else:
            self.end_date = datetime.now()
            
        if start_date:
            self.start_date = datetime.strptime(start_date, '%Y-%m-%d') if isinstance(start_date, str) else start_date
        else:
            self.start_date = self.end_date - timedelta(days=365*2)
            
        self.start_date_str = self.start_date.strftime('%Y-%m-%d')
        self.end_date_str = self.end_date.strftime('%Y-%m-%d')
        
    def connect(self):
        """Establish connection to WRDS."""
        try:
            self.db = wrds.Connection(wrds_username=self.username)
            logger.info("Successfully connected to WRDS")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to WRDS: {str(e)}")
            return False
    
    def close(self):
        """Close the WRDS connection."""
        if self.db is not None:
            self.db.close()
            logger.info("WRDS connection closed")
    
    def execute_query(self, query):
        """Execute a query and handle date conversion."""
        try:
            return self.db.raw_sql(query)
        except Exception as e:
            logger.error(f"Query error: {str(e)}")
            return pd.DataFrame()
    
    def get_gvkeys(self):
        """Get GVKEY identifiers for the tickers."""
        if self.db is None:
            return None
        
        try:
            tickers_sql = ','.join([f"'{ticker}'" for ticker in self.tickers])
            
            query = f"""
            SELECT DISTINCT n.tic as ticker, n.gvkey, n.conm
            FROM comp.names n
            WHERE n.tic IN ({tickers_sql})
            ORDER BY n.tic
            """
            
            self.ticker_gvkeys = self.execute_query(query)
            logger.info(f"Retrieved {len(self.ticker_gvkeys)} GVKEYs for tickers")
            return self.ticker_gvkeys
        except Exception as e:
            logger.error(f"Error retrieving GVKEYs: {str(e)}")
            return None
    
    def get_identifiers(self):
        """Get various identifiers for merging datasets."""
        if self.db is None or self.ticker_gvkeys is None:
            return pd.DataFrame()
        
        try:
            # Just return the ticker_gvkeys we already have since we don't need additional identifiers
            # This avoids issues with missing columns in the company table
            logger.info(f"Using {len(self.ticker_gvkeys)} existing identifiers")
            return self.ticker_gvkeys.copy()
        except Exception as e:
            logger.error(f"Error retrieving identifiers: {str(e)}")
            return pd.DataFrame()
    
    def get_financial_ratios(self):
        """Get financial ratios using funda table."""
        if self.db is None or self.ticker_gvkeys is None:
            return pd.DataFrame()
        
        try:
            gvkeys_sql = ','.join([f"'{gvkey}'" for gvkey in self.ticker_gvkeys['gvkey']])
            
            query = f"""
            SELECT a.gvkey, a.datadate, a.fyear, 
                   a.at, a.lt, a.sale, a.ni,
                   CASE WHEN a.ceq > 0 THEN (a.ni / a.ceq) ELSE NULL END as roe,
                   CASE WHEN a.at > 0 THEN (a.ni / a.at) ELSE NULL END as roa
            FROM comp.funda a
            WHERE a.gvkey IN ({gvkeys_sql})
            AND a.indfmt = 'INDL'
            AND a.datafmt = 'STD'
            AND a.consol = 'C'
            AND a.datadate >= '{self.start_date_str}'
            AND a.datadate <= '{self.end_date_str}'
            ORDER BY a.datadate DESC
            """
            
            ratios_df = self.execute_query(query)
            
            # Convert date
            if not ratios_df.empty and 'datadate' in ratios_df.columns:
                ratios_df['datadate'] = pd.to_datetime(ratios_df['datadate'])
            
            # Merge with ticker information
            result = ratios_df.merge(self.ticker_gvkeys[['gvkey', 'ticker', 'conm']], 
                               on='gvkey', how='left')
            
            logger.info(f"Retrieved {len(result)} financial ratio records")
            return result
            
        except Exception as e:
            logger.error(f"Error retrieving financial ratios: {str(e)}")
            return pd.DataFrame()
    
    def get_fundamentals_annual(self):
        """Get annual fundamental data."""
        if self.db is None or self.ticker_gvkeys is None:
            return pd.DataFrame()
        
        try:
            gvkeys_sql = ','.join([f"'{gvkey}'" for gvkey in self.ticker_gvkeys['gvkey']])
            
            # Define important fundamental columns
            core_columns = ['gvkey', 'datadate', 'fyear', 'fyr', 'indfmt', 'consol']
            balance_sheet = ['at', 'lt', 'ceq', 'ch', 'dltt', 'dlc', 'rect', 'invt']
            income_stmt = ['sale', 'revt', 'cogs', 'xsga', 'ebit', 'ebitda', 'ni', 'ib', 'xrd', 'capx']
            
            columns_sql = ', '.join([f'a.{col}' for col in core_columns + balance_sheet + income_stmt])
            
            query = f"""
            SELECT {columns_sql}
            FROM comp.funda a
            WHERE a.gvkey IN ({gvkeys_sql})
            AND a.indfmt = 'INDL'
            AND a.datafmt = 'STD'
            AND a.consol = 'C'
            AND a.datadate >= '{self.start_date_str}'
            AND a.datadate <= '{self.end_date_str}'
            ORDER BY a.datadate DESC
            """
            
            annual_df = self.execute_query(query)
            
            # Convert date
            if not annual_df.empty and 'datadate' in annual_df.columns:
                annual_df['datadate'] = pd.to_datetime(annual_df['datadate'])
            
            # Merge with ticker information
            result = annual_df.merge(self.ticker_gvkeys[['gvkey', 'ticker', 'conm']], 
                               on='gvkey', how='left')
            
            logger.info(f"Retrieved {len(result)} annual fundamental records")
            return result
        except Exception as e:
            logger.error(f"Error retrieving annual fundamentals: {str(e)}")
            return pd.DataFrame()
    
    def get_fundamentals_quarterly(self):
        """Get quarterly fundamental data based on updated metrics requirements."""
        if self.db is None or self.ticker_gvkeys is None:
            return pd.DataFrame()
        
        try:
            gvkeys_sql = ','.join([f"'{gvkey}'" for gvkey in self.ticker_gvkeys['gvkey']])
            logger.info(f"Using gvkeys: {gvkeys_sql}")
            
            # Define required fundamental columns based on new metrics
            core_columns = ['gvkey', 'datadate', 'fyearq', 'fqtr']
            
            # Profitability metrics
            profitability = ['ibq', 'niq', 'epspiq', 'epsfiq', 'oibdpq', 'saleq', 'cogsq', 'cshoq']
            
            # Financial health metrics
            financial_health = ['actq', 'lctq', 'atq', 'ltq', 'dlttq', 'ceqq', 'icaptq']
            
            # Cash flow metrics - Note: these might be problematic, so we'll handle them separately
            cash_flow = ['oancfy', 'capxy']
            
            columns_sql = ', '.join([f'q.{col}' for col in core_columns + profitability + financial_health + cash_flow])
            
            
            query = f"""
            SELECT {columns_sql}
            FROM comp.fundq q
            WHERE q.gvkey IN ({gvkeys_sql})
            AND q.indfmt = 'INDL'
            AND q.datafmt = 'STD'
            AND q.consol = 'C'
            AND q.datadate >= '{self.start_date_str}'
            AND q.datadate <= '{self.end_date_str}'
            ORDER BY q.datadate DESC
            """
            
            logger.info(f"Executing quarterly fundamentals query for date range: {self.start_date_str} to {self.end_date_str}")
            quarterly_df = self.execute_query(query)
            
            # Check if we got any data
            if quarterly_df.empty:
                logger.warning(f"No quarterly data found for the specified criteria. Trying with a more relaxed query...")
                
                # Try a simpler query with just core columns
                relaxed_query = f"""
                SELECT q.gvkey, q.datadate, q.fyearq, q.fqtr
                FROM comp.fundq q
                WHERE q.gvkey IN ({gvkeys_sql})
                AND q.indfmt = 'INDL'
                AND q.datafmt = 'STD'
                AND q.consol = 'C'
                LIMIT 10
                """
                
            
            # Convert date
            if not quarterly_df.empty and 'datadate' in quarterly_df.columns:
                quarterly_df['datadate'] = pd.to_datetime(quarterly_df['datadate'])
            
            # Rename columns for clarity
            if not quarterly_df.empty:
                rename_dict = {
                    'ibq': 'net_income',
                    'niq': 'net_income_including_extraordinary',
                    'epspiq': 'basic_eps',
                    'epsfiq': 'diluted_eps',
                    'oibdpq': 'operating_income',
                    'saleq': 'revenue',
                    'cogsq': 'cost_of_goods_sold',
                    'actq': 'current_assets',
                    'lctq': 'current_liabilities',
                    'atq': 'total_assets',
                    'ltq': 'total_liabilities',
                    'dlttq': 'long_term_debt',
                    'ceqq': 'common_equity',
                    'cshoq': 'common_shares_outstanding',
                    'icaptq': 'invested_capital',
                    'datadate': 'report_date',
                    'fyearq': 'fiscal_year',
                    'fqtr': 'fiscal_quarter',
                    'oancfy': 'net_operating_cash_flow',
                    'capxy': 'capital_expenditure'
                }
                
                quarterly_df.rename(columns=rename_dict, inplace=True)
            
            # Merge with ticker information
            result = quarterly_df.merge(self.ticker_gvkeys[['gvkey', 'ticker', 'conm']], 
                                  on='gvkey', how='left')
            
            logger.info(f"Retrieved {len(result)} quarterly fundamental records")
            return result
        except Exception as e:
            logger.error(f"Error retrieving quarterly fundamentals: {str(e)}")
            return pd.DataFrame()
    
    def get_security_daily(self):
        """Get daily security data."""
        if self.db is None:
            return pd.DataFrame()
        
        try:
            tickers_sql = ','.join([f"'{ticker}'" for ticker in self.tickers])
            
            query = f"""
            SELECT s.tic, s.datadate, s.cshtrd, s.prccd, s.prchd, s.prcld, s.prcod, 
            s.cshoc, s.ajexdi 
            FROM comp_na_daily_all.secd s
            WHERE s.tic IN ({tickers_sql})
            AND s.datadate >= '{self.start_date_str}'
            AND s.datadate <= '{self.end_date_str}'
            ORDER BY s.datadate DESC
            """
            
            security_df = self.execute_query(query)
            
            # Convert date
            if not security_df.empty and 'datadate' in security_df.columns:
                security_df['datadate'] = pd.to_datetime(security_df['datadate'])
                
            if 'ajexdi' in security_df.columns:
                    security_df['adj_close_price'] = security_df['prccd'] / security_df['ajexdi']
                    logger.info("Calculated adjusted closing prices")
            else:
                security_df['adj_close_price'] = security_df['prccd']
            security_df['market_cap'] = security_df['cshoc'] * security_df['prccd']
            # Rename to standardized columns
            
            new_name = {
                'tic': 'ticker',
                'datadate': 'date',
                'prcod': 'open_price',
                'prchd': 'high_price',
                'prcld': 'low_price',
                'prccd': 'close_price',
                'adj_close_price': 'adj_close_price',
                'cshtrd': 'trading_volume',
                'market_cap': 'market_cap',
                'cshoc': 'outstanding_shares',
                'ajexdi': 'adj_factor'
            }

            security_df = security_df[new_name.keys()].rename(columns=new_name)
                
            
            logger.info(f"Retrieved {len(security_df)} security daily records")
            return security_df
                
        except Exception as e:
            logger.error(f"Error retrieving security daily data: {str(e)}")
            return pd.DataFrame()
    
    def get_capital_structure_debt(self):
        """Get debt data for capital structure analysis."""
        if self.db is None or self.ticker_gvkeys is None:
            return pd.DataFrame()
        
        try:
            gvkeys_sql = ','.join([f"'{gvkey}'" for gvkey in self.ticker_gvkeys['gvkey']])
            
            query = f"""
            SELECT a.gvkey, a.datadate, a.fyear, a.dltt, a.dlc, 
                   a.dd1, a.dd2, a.dd3, a.dd4, a.dd5
            FROM comp.funda a
            WHERE a.gvkey IN ({gvkeys_sql})
            AND a.indfmt = 'INDL'
            AND a.datafmt = 'STD'
            AND a.consol = 'C'
            AND a.datadate >= '{self.start_date_str}'
            AND a.datadate <= '{self.end_date_str}'
            ORDER BY a.datadate DESC
            """
            
            debt_df = self.execute_query(query)
            
            # Convert date
            if not debt_df.empty and 'datadate' in debt_df.columns:
                debt_df['datadate'] = pd.to_datetime(debt_df['datadate'])
            
            # Merge with ticker information
            result = debt_df.merge(self.ticker_gvkeys[['gvkey', 'ticker', 'conm']], 
                             on='gvkey', how='left')
            
            logger.info(f"Retrieved {len(result)} debt structure records")
            return result
        except Exception as e:
            logger.error(f"Error retrieving debt structure data: {str(e)}")
            return pd.DataFrame()
    
    def get_capital_structure_equity(self):
        """Get equity data for capital structure analysis."""
        if self.db is None or self.ticker_gvkeys is None:
            return pd.DataFrame()
        
        try:
            gvkeys_sql = ','.join([f"'{gvkey}'" for gvkey in self.ticker_gvkeys['gvkey']])
            
            query = f"""
            SELECT a.gvkey, a.datadate, a.fyear, a.ceq, a.seq, 
                   a.pstk, a.csho, a.prcc_f, a.dvc
            FROM comp.funda a
            WHERE a.gvkey IN ({gvkeys_sql})
            AND a.indfmt = 'INDL'
            AND a.datafmt = 'STD'
            AND a.consol = 'C'
            AND a.datadate >= '{self.start_date_str}'
            AND a.datadate <= '{self.end_date_str}'
            ORDER BY a.datadate DESC
            """
            
            equity_df = self.execute_query(query)
            
            # Convert date
            if not equity_df.empty and 'datadate' in equity_df.columns:
                equity_df['datadate'] = pd.to_datetime(equity_df['datadate'])
            
            # Merge with ticker information
            result = equity_df.merge(self.ticker_gvkeys[['gvkey', 'ticker', 'conm']], 
                               on='gvkey', how='left')
            
            logger.info(f"Retrieved {len(result)} equity structure records")
            return result
        except Exception as e:
            logger.error(f"Error retrieving equity structure data: {str(e)}")
            return pd.DataFrame()
    
    def get_capital_structure_summary(self):
        """Get summary data for capital structure analysis."""
        if self.db is None or self.ticker_gvkeys is None:
            return pd.DataFrame()
        
        try:
            gvkeys_sql = ','.join([f"'{gvkey}'" for gvkey in self.ticker_gvkeys['gvkey']])
            
            query = f"""
            SELECT a.gvkey, a.datadate, a.fyear, a.at, a.lt, 
                   a.dltt, a.dlc, a.ceq, a.seq, a.csho, a.prcc_f, a.mkvalt
            FROM comp.funda a
            WHERE a.gvkey IN ({gvkeys_sql})
            AND a.indfmt = 'INDL'
            AND a.datafmt = 'STD'
            AND a.consol = 'C'
            AND a.datadate >= '{self.start_date_str}'
            AND a.datadate <= '{self.end_date_str}'
            ORDER BY a.datadate DESC
            """
            
            summary_df = self.execute_query(query)
            
            # Convert date
            if not summary_df.empty and 'datadate' in summary_df.columns:
                summary_df['datadate'] = pd.to_datetime(summary_df['datadate'])
            
            # Merge with ticker information
            summary_df = summary_df.merge(self.ticker_gvkeys[['gvkey', 'ticker', 'conm']], 
                                      on='gvkey', how='left')
            
            # Add calculated fields
            if not summary_df.empty:
                if all(col in summary_df.columns for col in ['dltt', 'dlc', 'ceq']):
                    summary_df['debt_to_equity'] = (summary_df['dltt'].fillna(0) + summary_df['dlc'].fillna(0)) / summary_df['ceq']
                
                if all(col in summary_df.columns for col in ['dltt', 'dlc', 'at']):
                    summary_df['debt_to_assets'] = (summary_df['dltt'].fillna(0) + summary_df['dlc'].fillna(0)) / summary_df['at']
            
            logger.info(f"Retrieved {len(summary_df)} capital structure summary records")
            return summary_df
        except Exception as e:
            logger.error(f"Error retrieving capital structure summary: {str(e)}")
            return pd.DataFrame()
    
    def get_key_developments(self):
        """Get major corporate news."""
        if self.db is None or self.ticker_gvkeys is None:
            return pd.DataFrame()
        
        try:
            # Check if CIQ table exists
            table_query = """
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'ciq' 
            AND table_name = 'wrds_keydev'
            """
            tables = self.execute_query(table_query)
            
            if tables.empty:
                logger.info("Key developments table not found")
                return pd.DataFrame()
                
            gvkeys_sql = ','.join([f"'{gvkey}'" for gvkey in self.ticker_gvkeys['gvkey']])
            
            query = f"""
            SELECT k.*
            FROM ciq.wrds_keydev k
            WHERE k.gvkey IN ({gvkeys_sql})
            AND k.announcedate >= '{self.start_date_str}'
            AND k.announcedate <= '{self.end_date_str}'
            ORDER BY k.announcedate DESC
            """
            
            developments_df = self.execute_query(query)
            
            # Convert date columns
            if not developments_df.empty:
                date_cols = ['announcedate', 'keydevdate']
                for col in date_cols:
                    if col in developments_df.columns:
                        developments_df[col] = pd.to_datetime(developments_df[col])
            
                # Merge with company info
                result = developments_df.merge(self.ticker_gvkeys[['gvkey', 'ticker', 'conm']], 
                                        on='gvkey', how='left')
                logger.info(f"Retrieved {len(result)} key development records")
                return result
            
            logger.info("No key development records found")
            return developments_df
        except Exception as e:
            logger.error(f"Error retrieving key developments: {str(e)}")
            return pd.DataFrame()
    
    def retrieve_all_datasets(self, save_to_csv=True, output_dir='data/compustat/'):
        """Retrieve all datasets and optionally save to CSV."""
        if not self.connect():
            return None
        
        # Get GVKEYs first
        self.get_gvkeys()
        if self.ticker_gvkeys is None or len(self.ticker_gvkeys) == 0:
            logger.error("Failed to retrieve GVKEYs for tickers")
            return None
        
        # Convert relative path to absolute path
        if not os.path.isabs(output_dir):
            # Get the repository root directory (assumes the script is in src/)
            repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
            output_dir = os.path.join(repo_root, output_dir)
        
        # Retrieve all datasets
        datasets = {
            'financial_ratios': self.get_financial_ratios(),
            'fundamentals_annual': self.get_fundamentals_annual(),
            'fundamentals_quarterly': self.get_fundamentals_quarterly(),
            'security_daily': self.get_security_daily(),
            'identifiers': self.get_identifiers(),
            'capital_structure_debt': self.get_capital_structure_debt(),
            'capital_structure_equity': self.get_capital_structure_equity(),
            'capital_structure_summary': self.get_capital_structure_summary(),
            'key_developments': self.get_key_developments()
        }
        
        # Save to CSV if requested
        if save_to_csv:
            os.makedirs(output_dir, exist_ok=True)
            
            for name, df in datasets.items():
                if df is not None and not df.empty:
                    file_path = os.path.join(output_dir, f"{name}.csv")
                    df.to_csv(file_path, index=False)
        
        # Print summary of retrieved datasets
        logger.info("------- Summary of Retrieved Datasets -------")
        for name, df in datasets.items():
            status = "SUCCESS" if df is not None and not df.empty else "FAILED"
            count = len(df) if df is not None else 0
            logger.info(f"{name}: {status} - {count} records")
        logger.info("--------------------------------------------")
        
        # Close connection
        self.close()
        
        return datasets


# Wrapper functions for importing
def get_wrds_data(tickers=None, start_date=None, end_date=None, username=None, save_to_csv=True, output_dir='data/compustat/'):
    """Retrieve all Compustat datasets for specified tickers and date range."""
    connector = WRDSConnector(username=username, tickers=tickers, start_date=start_date, end_date=end_date)
    return connector.retrieve_all_datasets(save_to_csv=save_to_csv, output_dir=output_dir)

def get_financial_ratios(tickers=None, start_date=None, end_date=None, username=None):
    """Get financial ratios for specified tickers."""
    connector = WRDSConnector(username=username, tickers=tickers, start_date=start_date, end_date=end_date)
    if connector.connect() and connector.get_gvkeys() is not None:
        result = connector.get_financial_ratios()
        connector.close()
        return result
    return pd.DataFrame()

def get_fundamentals_annual(tickers=None, start_date=None, end_date=None, username=None):
    """Get annual fundamental data for specified tickers."""
    connector = WRDSConnector(username=username, tickers=tickers, start_date=start_date, end_date=end_date)
    if connector.connect() and connector.get_gvkeys() is not None:
        result = connector.get_fundamentals_annual()
        connector.close()
        return result
    return pd.DataFrame()

def get_fundamentals_quarterly(tickers=None, start_date=None, end_date=None, username=None):
    """Get quarterly fundamental data for specified tickers."""
    connector = WRDSConnector(username=username, tickers=tickers, start_date=start_date, end_date=end_date)
    if connector.connect() and connector.get_gvkeys() is not None:
        result = connector.get_fundamentals_quarterly()
        connector.close()
        return result
    return pd.DataFrame()

def get_security_daily(tickers=None, start_date=None, end_date=None, username=None):
    """Get daily security data for specified tickers."""
    connector = WRDSConnector(username=username, tickers=tickers, start_date=start_date, end_date=end_date)
    if connector.connect() and connector.get_gvkeys() is not None:
        result = connector.get_security_daily()
        connector.close()
        return result
    return pd.DataFrame()

def get_identifiers(tickers=None, username=None):
    """Get various identifiers for specified tickers."""
    connector = WRDSConnector(username=username, tickers=tickers)
    if connector.connect() and connector.get_gvkeys() is not None:
        result = connector.get_identifiers()
        connector.close()
        return result
    return pd.DataFrame()

def get_capital_structure(tickers=None, start_date=None, end_date=None, username=None):
    """Get capital structure data for specified tickers."""
    connector = WRDSConnector(username=username, tickers=tickers, start_date=start_date, end_date=end_date)
    if connector.connect() and connector.get_gvkeys() is not None:
        result = {
            'debt': connector.get_capital_structure_debt(),
            'equity': connector.get_capital_structure_equity(),
            'summary': connector.get_capital_structure_summary()
        }
        connector.close()
        return result
    return {'debt': pd.DataFrame(), 'equity': pd.DataFrame(), 'summary': pd.DataFrame()}

def get_key_developments(tickers=None, start_date=None, end_date=None, username=None):
    """Get key developments data for specified tickers."""
    connector = WRDSConnector(username=username, tickers=tickers, start_date=start_date, end_date=end_date)
    if connector.connect() and connector.get_gvkeys() is not None:
        result = connector.get_key_developments()
        connector.close()
        return result
    return pd.DataFrame()


def main():
    """Main function to retrieve all Compustat datasets."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Retrieve Compustat data from WRDS')
    parser.add_argument('--tickers', nargs='+', help='List of ticker symbols (e.g., AAPL MSFT)')
    parser.add_argument('--start_date', help='Start date in YYYY-MM-DD format')
    parser.add_argument('--end_date', help='End date in YYYY-MM-DD format')
    parser.add_argument('--username', help='WRDS username')
    parser.add_argument('--output_dir', default='data/compustat/', help='Directory to save CSV files')
    args = parser.parse_args()
    
    # Convert relative output directory to absolute if needed
    if not os.path.isabs(args.output_dir):
        # Get the repository root directory (assumes the script is in src/)
        repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
        args.output_dir = os.path.join(repo_root, args.output_dir)
        logger.info(f"Using absolute output directory: {args.output_dir}")
    
    logger.info("Starting WRDS data retrieval...")
    result = get_wrds_data(
        tickers=args.tickers,
        start_date=args.start_date,
        end_date=args.end_date,
        username=args.username,
        output_dir=args.output_dir
    )
    
    if result:
        logger.info("WRDS data retrieval completed successfully")
    else:
        logger.error("WRDS data retrieval failed")


if __name__ == "__main__":
    main() 