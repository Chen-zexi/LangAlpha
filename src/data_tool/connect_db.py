import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy import event
from sqlalchemy import text
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

        self.conn_string = 'mysql://{user}:{password}@{host}:{port}/{db}?charset={encoding}'.format(
            user=self.db_user,
            password=self.db_password,
            host = 'jsedocc7.scrc.nyu.edu',
            port     = 3306,
            encoding = 'utf8',
            db = 'Elite_Traders'
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
        
    def read_table(self, table_name):
        sql = f'SELECT * FROM {table_name}'
        return pd.read_sql(sql, self.engine)
    
    def show_tables(self):
        return pd.read_sql('SHOW TABLES', self.engine)
    
    def execute_sql(self, sql):
        with self.engine.connect() as conn:
            return conn.execute(text(sql))
        
    def drop_table(self, table_name):
        self.execute_sql(f'DROP TABLE IF EXISTS {table_name}')
        