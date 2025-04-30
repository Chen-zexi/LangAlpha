from src.database_tool.connect_db import ConnectDB
from sqlalchemy import text
import sys

class TableCreator:
    def __init__(self):
        # Create a single instance of ConnectDB to use across the class
        self.db = ConnectDB()
        self.engine = self.db.get_engine()
    
    def create_price_table(self):
        if not self.db.check_if_table_exists('price'):
            create_table_sql = """
            CREATE TABLE price (
                id INT AUTO_INCREMENT PRIMARY KEY,
                ticker VARCHAR(10) NOT NULL,
                open FLOAT NOT NULL,
                close FLOAT NOT NULL,
                high FLOAT NOT NULL,
                low FLOAT NOT NULL,
                volume INT NOT NULL,
                time VARCHAR(50) NOT NULL
            )
            """
            try:
                with self.engine.connect() as conn:
                    conn.execute(text(create_table_sql))
                    conn.commit()
                print("Price table created successfully")
            except Exception as e:
                print(f"Error creating price table: {e}")
                if "disk is full" in str(e):
                    print("WARNING: Database disk is full. Cannot create tables.")
                    print("Please contact your database administrator to free up disk space.")
                    sys.exit(1)
        else:
            print("Price table already exists")
    
    def create_financial_metrics_table(self):
        if not self.db.check_if_table_exists('financial_metrics'):
            create_table_sql = """
            CREATE TABLE financial_metrics (
                id INT AUTO_INCREMENT PRIMARY KEY,
                ticker VARCHAR(10) NOT NULL,
                report_period VARCHAR(20) NOT NULL,
                period VARCHAR(20) NOT NULL,
                currency VARCHAR(10) NOT NULL,
                market_cap FLOAT,
                enterprise_value FLOAT,
                price_to_earnings_ratio FLOAT,
                price_to_book_ratio FLOAT,
                price_to_sales_ratio FLOAT,
                enterprise_value_to_ebitda_ratio FLOAT,
                enterprise_value_to_revenue_ratio FLOAT,
                free_cash_flow_yield FLOAT,
                peg_ratio FLOAT,
                gross_margin FLOAT,
                operating_margin FLOAT,
                net_margin FLOAT,
                return_on_equity FLOAT,
                return_on_assets FLOAT,
                return_on_invested_capital FLOAT,
                asset_turnover FLOAT,
                inventory_turnover FLOAT,
                receivables_turnover FLOAT,
                days_sales_outstanding FLOAT,
                operating_cycle FLOAT,
                working_capital_turnover FLOAT,
                current_ratio FLOAT,
                quick_ratio FLOAT,
                cash_ratio FLOAT,
                operating_cash_flow_ratio FLOAT,
                debt_to_equity FLOAT,
                debt_to_assets FLOAT,
                interest_coverage FLOAT,
                revenue_growth FLOAT,
                earnings_growth FLOAT,
                book_value_growth FLOAT,
                earnings_per_share_growth FLOAT,
                free_cash_flow_growth FLOAT,
                operating_income_growth FLOAT,
                ebitda_growth FLOAT,
                payout_ratio FLOAT,
                earnings_per_share FLOAT,
                book_value_per_share FLOAT,
                free_cash_flow_per_share FLOAT
            )
            """
            try:
                with self.engine.connect() as conn:
                    conn.execute(text(create_table_sql))
                    conn.commit()
                print("Financial Metrics table created successfully")
            except Exception as e:
                print(f"Error creating financial_metrics table: {e}")
        else:
            print("Financial Metrics table already exists")
    
    def create_insider_trade_table(self):
        if not self.db.check_if_table_exists('insider_trade'):
            create_table_sql = """
            CREATE TABLE insider_trade (
                id INT AUTO_INCREMENT PRIMARY KEY,
                ticker VARCHAR(10) NOT NULL,
                issuer VARCHAR(100),
                name VARCHAR(100),
                title VARCHAR(100),
                is_board_director BOOLEAN,
                transaction_date VARCHAR(20),
                transaction_shares FLOAT,
                transaction_price_per_share FLOAT,
                transaction_value FLOAT,
                shares_owned_before_transaction FLOAT,
                shares_owned_after_transaction FLOAT,
                security_title VARCHAR(100),
                filing_date VARCHAR(20) NOT NULL
            )
            """
            try:
                with self.engine.connect() as conn:
                    conn.execute(text(create_table_sql))
                    conn.commit()
                print("Insider Trade table created successfully")
            except Exception as e:
                print(f"Error creating insider_trade table: {e}")
        else:
            print("Insider Trade table already exists")
    
    def create_company_news_table(self):
        if not self.db.check_if_table_exists('company_news'):
            create_table_sql = """
            CREATE TABLE company_news (
                id INT AUTO_INCREMENT PRIMARY KEY,
                polygon_id VARCHAR(255) NOT NULL UNIQUE,  -- Polygon's specific ID
                ticker VARCHAR(10) NOT NULL, -- Keep for association, though Polygon news can have multiple tickers
                title TEXT NOT NULL,
                author VARCHAR(255),
                publisher VARCHAR(255),
                published_utc DATETIME NOT NULL,
                article_url VARCHAR(512) UNIQUE, -- Use article_url for uniqueness check
                tickers JSON, -- Store list of associated tickers
                description TEXT,
                keywords JSON, -- Store list of keywords
                insights JSON -- Store insights data
            )
            """
            try:
                with self.engine.connect() as conn:
                    conn.execute(text(create_table_sql))
                    conn.commit()
                print("Company News table created successfully")
            except Exception as e:
                print(f"Error creating company_news table: {e}")
        else:
            print("Company News table already exists")
    
    
    def create_all_tables(self):
        """Create all tables defined in the models"""
        self.create_price_table()
        self.create_financial_metrics_table()
        self.create_insider_trade_table()
        self.create_company_news_table()
        print("All tables created successfully")

def main():
    # Create all tables
    table_creator = TableCreator()
    table_creator.create_all_tables()

if __name__ == "__main__":
    main()




