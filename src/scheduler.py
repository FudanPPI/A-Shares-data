
import logging
import duckdb
from src.config import DB_PATH, PARQUET_DIR, BACKUP_DIR, START_DATE, STOCK_CODES
from src.database.models import init_tables
from src.database.operations import DatabaseOperations
from src.database.parquet_store import ParquetStore
from src.database.backup import BackupManager
from src.collector.multi_source_collector import MultiSourceCollector
from src.indicators.technical import TechnicalIndicatorCalculator
from src.indicators.financial import FinancialIndicatorCalculator
from src.indicators.valuation import ValuationIndicatorCalculator

logger = logging.getLogger(__name__)


class Scheduler:
    def __init__(self):
        self.db_ops = DatabaseOperations(DB_PATH)
        self.parquet_store = ParquetStore(PARQUET_DIR)
        self.backup_manager = BackupManager(DB_PATH, BACKUP_DIR)
        self.collector = MultiSourceCollector(self.db_ops, self.parquet_store, START_DATE)
        self.tech_calc = TechnicalIndicatorCalculator(self.db_ops)
        self.fin_calc = FinancialIndicatorCalculator(self.db_ops)
        self.val_calc = ValuationIndicatorCalculator(self.db_ops)

    def run(self, stock_codes=None):
        if stock_codes is None:
            stock_codes = STOCK_CODES

        logger.info("启动数据采集与计算流程")

        init_tables(self.db_ops.conn)

        for stock_code in stock_codes:
            try:
                self.collector.collect_stock(stock_code)
            except Exception as e:
                logger.error(f"{stock_code} 采集流程异常: {e}", exc_info=True)

            try:
                self._calculate_daily_basic(stock_code)
            except Exception as e:
                logger.error(f"{stock_code} 日线基础指标计算失败: {e}")

            try:
                self.tech_calc.calculate_for_stock(stock_code)
            except Exception as e:
                logger.error(f"{stock_code} 技术指标计算失败: {e}")

            try:
                self.fin_calc.calculate_for_stock(stock_code)
            except Exception as e:
                logger.error(f"{stock_code} 财务指标计算失败: {e}")

            try:
                self.val_calc.calculate_for_stock(stock_code)
            except Exception as e:
                logger.error(f"{stock_code} 估值指标计算失败: {e}")

            try:
                self._calculate_northbound_accumulation(stock_code)
            except Exception as e:
                logger.error(f"{stock_code} 北向资金累计计算失败: {e}")

        self.db_ops.close()
        import time
        time.sleep(0.5)
        try:
            self.backup_manager.create_backup()
        except Exception as e:
            logger.warning(f"数据库备份失败: {e}")
        self.db_ops.conn = duckdb.connect(str(DB_PATH))
        try:
            self.backup_manager.check_integrity(self.db_ops.conn)
        except Exception as e:
            logger.warning(f"数据完整性检查失败: {e}")

        logger.info("流程完成")

    def _calculate_daily_basic(self, stock_code: str):
        df = self.db_ops.query("""
        SELECT stock_code, trade_date, open, high, low, close
        FROM stock_daily
        WHERE stock_code = ?
        ORDER BY trade_date
        """, (stock_code,))

        if df.empty:
            return

        df = df.sort_values('trade_date').reset_index(drop=True)
        df['prev_close'] = df['close'].shift(1)
        df['change_pct'] = (df['close'] - df['prev_close']) / df['prev_close'] * 100
        df['amplitude'] = (df['high'] - df['low']) / df['prev_close'] * 100
        df['body_size'] = abs(df['close'] - df['open'])
        df['upper_shadow'] = df['high'] - df[['open', 'close']].max(axis=1)
        df['lower_shadow'] = df[['open', 'close']].min(axis=1) - df['low']
        df['high_20'] = df['high'].rolling(window=20, min_periods=1).max()
        df['low_20'] = df['low'].rolling(window=20, min_periods=1).min()
        df['high_60'] = df['high'].rolling(window=60, min_periods=1).max()
        df['low_60'] = df['low'].rolling(window=60, min_periods=1).min()

        self.db_ops.conn.register("df_update", df)
        self.db_ops.conn.execute("""
        UPDATE stock_daily
        SET prev_close = df_update.prev_close,
            change_pct = df_update.change_pct,
            amplitude = df_update.amplitude,
            body_size = df_update.body_size,
            upper_shadow = df_update.upper_shadow,
            lower_shadow = df_update.lower_shadow,
            high_20 = df_update.high_20,
            low_20 = df_update.low_20,
            high_60 = df_update.high_60,
            low_60 = df_update.low_60
        FROM df_update
        WHERE stock_daily.stock_code = df_update.stock_code 
          AND stock_daily.trade_date = df_update.trade_date
        """)
        self.db_ops.conn.unregister("df_update")

    def _calculate_northbound_accumulation(self, stock_code: str):
        try:
            logger.info(f"计算 {stock_code} 北向资金累计流入")

            df = self.db_ops.query("""
            SELECT stock_code, trade_date, net_inflow
            FROM northbound_flow
            WHERE stock_code = ?
            ORDER BY trade_date
            """, (stock_code,))

            if df.empty or len(df) < 5:
                logger.info(f"{stock_code} 北向资金数据不足")
                return

            df = df.sort_values('trade_date').reset_index(drop=True)
            df['inflow_5d'] = df['net_inflow'].rolling(5, min_periods=1).sum()
            df['inflow_10d'] = df['net_inflow'].rolling(10, min_periods=1).sum()
            df['inflow_30d'] = df['net_inflow'].rolling(30, min_periods=1).sum()

            self.db_ops.conn.register("df_nb_acc", df)
            self.db_ops.conn.execute("""
            INSERT INTO northbound_flow 
            (stock_code, trade_date, net_inflow, inflow_5d, inflow_10d, inflow_30d)
            SELECT stock_code, trade_date, net_inflow, inflow_5d, inflow_10d, inflow_30d
            FROM df_nb_acc
            ON CONFLICT (stock_code, trade_date) DO UPDATE 
            SET inflow_5d = EXCLUDED.inflow_5d,
                inflow_10d = EXCLUDED.inflow_10d,
                inflow_30d = EXCLUDED.inflow_30d
            """)
            self.db_ops.conn.unregister("df_nb_acc")

            logger.info(f"{stock_code} 北向资金累计流入计算完成")

        except Exception as e:
            logger.error(f"{stock_code} 北向资金累计流入计算失败：{str(e)}")

    def close(self):
        self.db_ops.close()
