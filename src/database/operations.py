
import duckdb
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class DatabaseOperations:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.conn = duckdb.connect(str(db_path))

    def close(self):
        if self.conn:
            self.conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def get_last_update_date(self, stock_code: str, data_type: str, start_date: str) -> str:
        result = self.conn.execute("""
        SELECT MAX(last_update_date) FROM update_log 
        WHERE stock_code = ? AND data_type = ?
        """, (stock_code, data_type)).fetchone()

        if result[0] is None:
            return start_date
        else:
            last_date = datetime.strptime(str(result[0]), "%Y-%m-%d")
            next_date = last_date + timedelta(days=1)
            return next_date.strftime("%Y%m%d")

    def update_last_update_date(self, stock_code: str, data_type: str, end_date: str):
        end_date_dt = datetime.strptime(end_date, "%Y-%m-%d").date()
        self.conn.execute("""
        INSERT INTO update_log (stock_code, data_type, last_update_date, update_time)
        VALUES (?, ?, ?, now())
        ON CONFLICT (stock_code, data_type)
        DO UPDATE SET last_update_date = EXCLUDED.last_update_date,
                      update_time = now()
        """, (stock_code, data_type, end_date_dt))

    def insert_dataframe(self, table_name: str, df, conflict_columns: Optional[list] = None):
        if df.empty:
            return

        self.conn.register("df", df)
        columns = ", ".join(df.columns)

        if conflict_columns:
            conflict_str = ", ".join(conflict_columns)
            sql = f"""
            INSERT INTO {table_name} ({columns})
            SELECT {columns} FROM df
            ON CONFLICT ({conflict_str}) DO NOTHING
            """
        else:
            sql = f"""
            INSERT INTO {table_name} ({columns})
            SELECT {columns} FROM df
            """

        self.conn.execute(sql)
        self.conn.unregister("df")

    def query(self, sql: str, params: Optional[tuple] = None):
        if params:
            return self.conn.execute(sql, params).fetchdf()
        else:
            return self.conn.execute(sql).fetchdf()
