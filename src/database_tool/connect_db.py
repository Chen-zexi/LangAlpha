import pandas as pd
from sqlalchemy import create_engine, event, text, inspect
import os
from dotenv import load_dotenv

load_dotenv()

class ConnectDB:
    def __init__(self):
        self.db_user = os.getenv('DB_USER')
        self.db_password = os.getenv('DB_PASSWORD')
        if self.db_user is None or self.db_password is None:
            raise ValueError("DB_USER or DB_PASSWORD is not set")
        else:
            print("DB_USER and DB_PASSWORD are set")

        self.conn_string = 'mysql+pymysql://{user}:{password}@{host}:{port}/{db}?charset={encoding}'.format(
            user=self.db_user,
            password=self.db_password,
            host='jsedocc7.scrc.nyu.edu',
            port=3306,
            encoding='utf8',
            db='Elite_Traders'
        )

        self.engine = create_engine(self.conn_string)

        # This is for speeding up the insertion into the database schema
        @event.listens_for(self.engine, 'before_cursor_execute')
        def receive_before_cursor_execute(conn, cursor, statement, params, context, executemany):
            if executemany:
                cursor.fast_executemany = True
    
    def get_engine(self):
        return self.engine
        
    def create_table(self, table_name, df, if_exists='append', index=False):
        df.to_sql(table_name, self.engine, if_exists='append', index=False)
        
    def insert_df_to_table(self, table_name, df, if_exists='append', index=False):
        """Insert a DataFrame into a database table"""
        df.to_sql(table_name, self.engine, if_exists=if_exists, index=index)
        print(f"Data successfully inserted into {table_name}")
    
    def read_table(self, table_name):
        """Read all data from a table"""
        sql = text(f'SELECT * FROM {table_name}')
        with self.engine.connect() as conn:
            result = conn.execute(sql)
            return pd.DataFrame(result.fetchall(), columns=result.keys())
    
    def read_table_with_condition(self, table_name, condition, limit=1000):
        """Read data from a table with a WHERE condition"""
        query = f'SELECT * FROM {table_name} WHERE {condition}'
        if limit is not None:
            query += f' LIMIT {limit}'
        sql = text(query)
        with self.engine.connect() as conn:
            result = conn.execute(sql)
            return pd.DataFrame(result.fetchall(), columns=result.keys())
        
    def show_tables(self):
        """List all tables in the database"""
        with self.engine.connect() as conn:
            result = conn.execute(text('SHOW TABLES'))
            return pd.DataFrame(result.fetchall(), columns=['Tables'])
    
    def execute_sql(self, sql_statement):
        """Execute an arbitrary SQL statement"""
        with self.engine.connect() as conn:
            return conn.execute(text(sql_statement))
        
    def execute_sql_scalar(self, sql_statement):
        """Execute an SQL query and return the first value of the first row"""
        with self.engine.connect() as conn:
            result = conn.execute(text(sql_statement))
            row = result.fetchone()
            return row[0] if row else 0
        
    def execute_sql_scalar_tuple(self, sql_statement):
        """Execute an SQL query and return all values of the first row as a tuple"""
        with self.engine.connect() as conn:
            result = conn.execute(text(sql_statement))
            row = result.fetchone()
            return tuple(row) if row else None
        
    def drop_table(self, table_name):
        """Drop a table if it exists"""
        self.execute_sql(f'DROP TABLE IF EXISTS {table_name}')
        print(f"Table {table_name} dropped successfully")
    
    def check_if_table_exists(self, table_name):
        """Check if a table exists in the database"""
        inspector = inspect(self.engine)
        return table_name in inspector.get_table_names()
        