"""多数据源编排器 - 统一调度各数据源采集器

数据源分工:
- mootdx: 日线行情 (TCP直连, 最稳定)
- baostock: 股本/行业/分红 (免费稳定)
- tencent: 估值PE/PB (零鉴权)
- akshare: 财务数据/融资融券/公告/龙虎榜 (独有数据)
- tushare: 北向资金个股数据 (作为AKShare的回退,需Pro版token)

每个采集步骤都有主源+备源, 主源失败自动回退
"""
import logging
from datetime import datetime, timedelta
from .base import BaseCollector
from .mootdx_collector import MootdxCollector
from .baostock_collector import BaostockCollector
from .tencent_collector import TencentCollector
from .eastmoney import EastmoneyCollector
from .tushare_collector import TushareCollector

logger = logging.getLogger(__name__)

STALE_DATA_THRESHOLD_DAYS = 30


class MultiSourceCollector(BaseCollector):
    """多数据源编排器 - 按数据类型选择最优数据源"""

    def __init__(self, db_ops, parquet_store, start_date: str, tushare_token: str = ""):
        super().__init__(db_ops, parquet_store, start_date)
        self.mootdx = MootdxCollector(db_ops, parquet_store, start_date)
        self.baostock = BaostockCollector(db_ops, parquet_store, start_date)
        self.tencent = TencentCollector(db_ops, parquet_store, start_date)
        self.akshare = EastmoneyCollector(db_ops, parquet_store, start_date)
        self.tushare = TushareCollector(db_ops, parquet_store, start_date, tushare_token)

    def collect_stock(self, stock_code: str):
        """按优先级依次采集各类型数据"""
        steps = [
            # 日线行情: mootdx主, AKShare备(内置于mootdx)
            ("日线行情", self._collect_daily),

            # 股本/行业/分红: BaoStock
            ("股本数据", self._collect_capital),
            ("行业数据", self._collect_industry),
            ("分红数据", self._collect_dividend),

            # 财务数据: AKShare Sina (字段最全)
            ("财务数据", self._collect_financial),
            ("财务补充", self._collect_financial_supplement),
            ("资产负债表补充", self._collect_balance_sheet),

            # 估值数据: 腾讯财经
            ("估值数据", self._collect_valuation),

            # 融资融券: AKShare (BaoStock无此API)
            ("融资融券", self._collect_margin),

            # AKShare独有数据
            ("公告数据", self._collect_announcements),
            ("龙虎榜", self._collect_dragon_tiger),

            # 北向资金: AKShare (仅沪深港通标的有数据)
            ("北向资金", self._collect_northbound),
        ]

        for name, method in steps:
            try:
                method(stock_code)
            except Exception as e:
                logger.error(f"{stock_code} {name}采集失败: {e}")

    def _collect_daily(self, stock_code: str):
        """日线行情: mootdx -> AKShare回退"""
        try:
            self.mootdx.collect_daily_data(stock_code)
        except Exception as e:
            logger.warning(f"[mootdx] {stock_code} 日线失败, 尝试AKShare: {e}")
            self.mootdx._fallback_akshare(stock_code)

    def _collect_capital(self, stock_code: str):
        """股本数据: BaoStock"""
        self.baostock.collect_capital_data(stock_code)

    def _collect_industry(self, stock_code: str):
        """行业数据: BaoStock"""
        self.baostock.collect_industry_data(stock_code)

    def _collect_dividend(self, stock_code: str):
        """分红数据: BaoStock"""
        self.baostock.collect_dividend_data(stock_code)

    def _collect_financial(self, stock_code: str):
        """财务数据: AKShare Sina"""
        self.akshare.collect_financial_data(stock_code)

    def _collect_financial_supplement(self, stock_code: str):
        """财务补充: AKShare EM"""
        self.akshare._update_missing_financial_fields(stock_code)

    def _collect_balance_sheet(self, stock_code: str):
        """资产负债表补充: AKShare EM"""
        self.akshare._update_balance_sheet_fields(stock_code)

    def _collect_valuation(self, stock_code: str):
        """估值数据: 腾讯财经"""
        self.tencent.collect_valuation_data(stock_code)

    def _collect_margin(self, stock_code: str):
        """融资融券: AKShare"""
        self.akshare.collect_margin_trading(stock_code)

    def _collect_announcements(self, stock_code: str):
        """公告: AKShare"""
        self.akshare.collect_announcements(stock_code)

    def _collect_dragon_tiger(self, stock_code: str):
        """龙虎榜: AKShare"""
        self.akshare.collect_dragon_tiger(stock_code)

    def _collect_northbound(self, stock_code: str):
        """北向资金: AKShare主, Tushare备(数据过期时)

        策略:
        1. 先尝试 AKShare 采集
        2. 检查数据是否过期(最新日期距今天超过30天)
        3. 数据过期且配置了Tushare token,则尝试Tushare Pro
        """
        try:
            self.akshare.collect_northbound_flow(stock_code)
        except Exception as e:
            logger.warning(f"[akshare] {stock_code} 北向资金失败: {e}")

        if self._is_northbound_stale(stock_code):
            logger.info(f"[tushare] {stock_code} 北向资金数据过期,尝试Tushare回退")
            try:
                self.tushare.collect_northbound_flow(stock_code)
            except Exception as e:
                logger.warning(f"[tushare] {stock_code} 北向资金回退失败: {e}")

    def _is_northbound_stale(self, stock_code: str) -> bool:
        """检查北向资金数据是否过期"""
        try:
            result = self.db_ops.conn.execute("""
                SELECT MAX(trade_date) FROM northbound_flow WHERE stock_code = ?
            """, [stock_code]).fetchone()
            if result and result[0]:
                latest_date = result[0]
                if isinstance(latest_date, str):
                    latest_date = datetime.strptime(latest_date, "%Y-%m-%d").date()
                days_diff = (datetime.now().date() - latest_date).days
                if days_diff > STALE_DATA_THRESHOLD_DAYS:
                    logger.debug(f"[tushare] {stock_code} 北向资金最新日期 {latest_date}, 已过期 {days_diff} 天")
                    return True
            return False
        except Exception:
            return False

    def close(self):
        """关闭所有数据源连接"""
        self.mootdx.close()
        self.baostock.close()
        self.tushare.close()
