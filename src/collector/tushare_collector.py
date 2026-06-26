"""Tushare 数据采集器 - 作为 AKShare 的补充数据源

数据源分工:
- 北向资金个股数据: Tushare Pro (需积分)
- 市场整体北向资金: Tushare 免费版 (moneyflow_hsgt)

配置要求:
- 在 src/config.py 中设置 TUSHARE_TOKEN (可选)
- Tushare Pro 用户可获取个股北向资金明细
- 免费用户仅能获取市场整体数据

线程安全:
  - tushare 客户端非线程安全,通过 threading.local 保证每线程独立实例
"""
import pandas as pd
import logging
import threading
from datetime import datetime

logger = logging.getLogger(__name__)

_client_local = threading.local()


class TushareCollector:
    def __init__(self, db_ops, parquet_store, start_date: str, token: str = None):
        self.db_ops = db_ops
        self.parquet_store = parquet_store
        self.start_date = start_date
        self.token = token
        self._has_individual_api = False
        self._init_client()

    def _init_client(self):
        """初始化 Tushare 客户端"""
        try:
            import tushare as ts
            if self.token:
                ts.set_token(self.token)
                self._has_individual_api = True
                logger.info("[tushare] 使用 Tushare Pro 模式 (已配置token)")
            else:
                logger.info("[tushare] 使用 Tushare 免费模式 (无token)")
        except Exception as e:
            logger.warning(f"[tushare] 初始化失败: {e}")

    def _get_pro_api(self):
        """获取 Tushare Pro API 实例"""
        if not self.token:
            return None
        try:
            import tushare as ts
            pro = getattr(_client_local, "pro_api", None)
            if pro is None:
                pro = ts.pro_api(self.token)
                _client_local.pro_api = pro
            return pro
        except Exception as e:
            logger.warning(f"[tushare] 获取Pro API失败: {e}")
            return None

    def collect_northbound_flow(self, stock_code: str):
        """采集北向资金个股数据

        Tushare Pro 可用接口:
        - hsgt_top10_detail_em: 北向资金成交明细
        - hsgt_hold_stock_em: 北向资金持股明细

        免费版仅能获取市场整体数据,无法获取个股明细
        """
        if not self._has_individual_api:
            logger.debug(f"[tushare] 免费模式,跳过个股北向资金采集: {stock_code}")
            return

        pro = self._get_pro_api()
        if pro is None:
            return

        try:
            code = stock_code[2:]
            exchange = 'SH' if stock_code.startswith('sh') else 'SZ'

            logger.info(f"[tushare] 开始采集 {stock_code} 北向资金数据")

            df = None
            try:
                df = pro.hsgt_top10_detail_em(ts_code=f"{code}.{exchange}")
            except Exception:
                try:
                    df = pro.hsgt_hold_stock_em(ts_code=f"{code}.{exchange}")
                except Exception as e:
                    logger.warning(f"[tushare] {stock_code} 北向资金接口调用失败: {e}")
                    return

            if df is None or df.empty:
                logger.info(f"[tushare] {stock_code} 无北向资金数据(可能非沪深港通标的)")
                return

            logger.info(f"[tushare] {stock_code} 获取到 {len(df)} 条北向资金数据")

            df = self._normalize_northbound(df, stock_code)

            if df.empty:
                return

            today_fmt = datetime.now().strftime("%Y-%m-%d")
            try:
                with self.db_ops.transaction():
                    self.db_ops.conn.register("df_tb", df)
                    self.db_ops.conn.execute("""
                        INSERT INTO northbound_flow
                        (stock_code, trade_date, net_inflow, holding_shares, holding_value,
                         holding_ratio, inflow_5d, inflow_10d, inflow_30d)
                        SELECT stock_code, trade_date, net_inflow, holding_shares, holding_value,
                               holding_ratio, inflow_5d, inflow_10d, inflow_30d
                        FROM df_tb
                        ON CONFLICT (stock_code, trade_date) DO UPDATE SET
                            net_inflow = EXCLUDED.net_inflow,
                            holding_shares = EXCLUDED.holding_shares,
                            holding_value = EXCLUDED.holding_value,
                            holding_ratio = EXCLUDED.holding_ratio,
                            inflow_5d = EXCLUDED.inflow_5d,
                            inflow_10d = EXCLUDED.inflow_10d,
                            inflow_30d = EXCLUDED.inflow_30d
                    """)
                    self.db_ops.conn.unregister("df_tb")
                    self.db_ops.update_last_update_date(stock_code, "northbound", today_fmt)
                logger.info(f"[tushare] {stock_code} 北向资金完成,新增 {len(df)} 条")
            except Exception as e:
                logger.error(f"[tushare] {stock_code} 北向资金写入失败,已回滚: {e}")
                raise

        except Exception as e:
            msg = str(e)
            if "积分" in msg or "权限" in msg:
                logger.warning(f"[tushare] {stock_code} 北向资金采集失败(积分不足或权限不够): {e}")
            else:
                logger.error(f"[tushare] {stock_code} 北向资金采集失败: {e}")

    def _normalize_northbound(self, df: pd.DataFrame, stock_code: str) -> pd.DataFrame:
        """标准化北向资金数据格式"""
        df = df.copy()

        column_map = {
            "trade_date": "trade_date",
            "date": "trade_date",
            "持股日期": "trade_date",
            "net_amount": "net_inflow",
            "北向资金净流入": "net_inflow",
            "今日增持资金": "net_inflow",
            "hold_volume": "holding_shares",
            "持股数量": "holding_shares",
            "hold_amount": "holding_value",
            "持股市值": "holding_value",
            "hold_ratio": "holding_ratio",
            "持股比例": "holding_ratio",
            "持股数量占A股百分比": "holding_ratio",
        }

        df = df.rename(columns={k: v for k, v in column_map.items() if k in df.columns})

        if "trade_date" not in df.columns:
            logger.warning(f"[tushare] {stock_code} 缺少交易日期字段")
            return pd.DataFrame()

        df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.date
        df["stock_code"] = stock_code

        numeric_cols = ["net_inflow", "holding_shares", "holding_value", "holding_ratio"]
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        df = df.sort_values("trade_date").reset_index(drop=True)

        if "net_inflow" in df.columns:
            df["inflow_5d"] = df["net_inflow"].rolling(5, min_periods=1).sum()
            df["inflow_10d"] = df["net_inflow"].rolling(10, min_periods=1).sum()
            df["inflow_30d"] = df["net_inflow"].rolling(30, min_periods=1).sum()
        else:
            df["inflow_5d"] = None
            df["inflow_10d"] = None
            df["inflow_30d"] = None

        cols = ["stock_code", "trade_date", "net_inflow", "holding_shares",
                "holding_value", "holding_ratio", "inflow_5d", "inflow_10d", "inflow_30d"]
        df = df[[c for c in cols if c in df.columns]].copy()

        return df

    def close(self):
        """关闭连接"""
        pro = getattr(_client_local, "pro_api", None)
        if pro:
            try:
                pro.close()
            except Exception:
                pass
            _client_local.pro_api = None
