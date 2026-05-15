
import logging
from .base import BaseCollector

logger = logging.getLogger(__name__)


class SinaFinanceCollector(BaseCollector):
    def __init__(self, db_ops, parquet_store, start_date: str):
        super().__init__(db_ops, parquet_store, start_date)

    def collect_stock(self, stock_code: str):
        logger.info("SinaFinanceCollector 占位实现，实际使用 EastmoneyCollector")
