import duckdb
import pandas as pd
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class ParquetStore:
    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self.daily_dir = base_dir / "daily"
        self.financial_dir = base_dir / "financial"
        self.indicators_dir = base_dir / "indicators"

    def write_daily(self, df: pd.DataFrame):
        if df.empty:
            return

        file_path = self.daily_dir / "data.parquet"

        if file_path.exists():
            existing_df = pd.read_parquet(file_path)
            df_combined = pd.concat([existing_df, df], ignore_index=True)
            df_combined = df_combined.drop_duplicates(subset=["stock_code", "trade_date"], keep="last")
            df_combined.to_parquet(file_path, index=False)
        else:
            df.to_parquet(file_path, index=False)
        logger.info(f"写入日线数据到 {file_path}，共 {len(df)} 条记录")

    def write_financial(self, df: pd.DataFrame):
        if df.empty:
            return

        file_path = self.financial_dir / "data.parquet"

        if file_path.exists():
            existing_df = pd.read_parquet(file_path)
            df_combined = pd.concat([existing_df, df], ignore_index=True)
            df_combined = df_combined.drop_duplicates(subset=["stock_code", "report_date", "report_type"], keep="last")
            df_combined.to_parquet(file_path, index=False)
        else:
            df.to_parquet(file_path, index=False)
        logger.info(f"写入财务数据到 {file_path}，共 {len(df)} 条记录")

    def write_indicators(self, df: pd.DataFrame):
        if df.empty:
            return

        file_path = self.indicators_dir / "data.parquet"

        if file_path.exists():
            existing_df = pd.read_parquet(file_path)
            df_combined = pd.concat([existing_df, df], ignore_index=True)
            df_combined = df_combined.drop_duplicates(subset=["stock_code", "trade_date"], keep="last")
            df_combined.to_parquet(file_path, index=False)
        else:
            df.to_parquet(file_path, index=False)
        logger.info(f"写入指标数据到 {file_path}，共 {len(df)} 条记录")

    def read_daily(self, stock_code: Optional[str] = None) -> pd.DataFrame:
        file_path = self.daily_dir / "data.parquet"
        if not file_path.exists():
            return pd.DataFrame()

        df = pd.read_parquet(file_path)
        if stock_code:
            df = df[df["stock_code"] == stock_code]
        return df

    def read_financial(self, stock_code: Optional[str] = None) -> pd.DataFrame:
        file_path = self.financial_dir / "data.parquet"
        if not file_path.exists():
            return pd.DataFrame()

        df = pd.read_parquet(file_path)
        if stock_code:
            df = df[df["stock_code"] == stock_code]
        return df

    def read_indicators(self, stock_code: Optional[str] = None) -> pd.DataFrame:
        file_path = self.indicators_dir / "data.parquet"
        if not file_path.exists():
            return pd.DataFrame()

        df = pd.read_parquet(file_path)
        if stock_code:
            df = df[df["stock_code"] == stock_code]
        return df