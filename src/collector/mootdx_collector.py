"""mootdx 数据采集器 - TCP直连通达信服务器获取行情数据

优势: 零鉴权、不封IP、TCP二进制协议稳定
数据: 日线K线、实时行情

线程安全:
  - mootdx Quotes client 非线程安全,通过 threading.local 保证每线程独立实例
  - 写入通过 DatabaseOperations 的事务管理保证原子性
"""
import pandas as pd
import logging
import threading
from datetime import datetime, timedelta
from .base import BaseCollector, retry

logger = logging.getLogger(__name__)

# 模块级 threading.local: 每线程独立的 mootdx client
_client_local = threading.local()


class MootdxCollector(BaseCollector):
    def __init__(self, db_ops, parquet_store, start_date: str):
        super().__init__(db_ops, parquet_store, start_date)
        # 不再持有单例 _client,改用 threading.local

    # 通达信最新可用服务器列表(2025年更新)
    # 来源: 申银万国、国金证券、华西证券等券商公开地址
    DEFAULT_SERVERS = [
        ('222.73.235.23', 7709),    # 申银万国上海电信1
        ('222.73.235.29', 7709),    # 申银万国上海电信2
        ('125.64.39.61', 7709),     # 申银万国成都电信1
        ('222.73.56.72', 7709),     # 国金上海电信
        ('119.4.167.141', 7709),    # 华西联通L1
        ('121.36.199.182', 7711),   # 上海双线资讯主站(新)
        ('124.70.158.189', 7711),   # 上海双线资讯主站2(新)
        ('119.147.212.81', 7709),   # 旧地址备用
    ]

    def _get_client(self):
        """获取当前线程的 mootdx client(threading.local 保证线程独立)

        连接策略:
        1. 先尝试 bestip=True 让 mootdx 自动选优最快的可用服务器
        2. 失败后逐个尝试预设服务器列表(DEFAULT_SERVERS)
        3. 全部失败则抛出 ConnectionError 触发回退到 AKShare
        """
        client = getattr(_client_local, "client", None)
        if client is None:
            from mootdx.quotes import Quotes

            # 策略1: 尝试 bestip=True 自动选优
            try:
                logger.debug(f"[mootdx] 线程 {threading.get_ident()} 尝试 bestip=True 自动选优")
                client = Quotes.factory(market='std', timeout=30, bestip=True)
                test = client.bars(symbol='000001', frequency=4, start=0, offset=1)
                if test is not None and not test.empty:
                    logger.info(f"[mootdx] 线程 {threading.get_ident()} bestip=True 自动选优成功")
                    _client_local.client = client
                    return client
            except Exception as e:
                logger.debug(f"[mootdx] bestip=True 失败: {e}, 尝试预设服务器列表")

            # 策略2: 逐个尝试预设服务器列表
            for host, port in self.DEFAULT_SERVERS:
                try:
                    client = Quotes.factory(market='std', timeout=30,
                                            bestip=False, ip=host, port=port)
                    test = client.bars(symbol='000001', frequency=4, start=0, offset=1)
                    if test is not None and not test.empty:
                        logger.info(f"[mootdx] 线程 {threading.get_ident()} 连接服务器成功: {host}:{port}")
                        _client_local.client = client
                        return client
                except Exception as e:
                    logger.debug(f"[mootdx] {host}:{port} 连接失败: {e}")
                    continue

            # 全部失败
            logger.warning("[mootdx] 所有服务器连接失败, 将回退到AKShare")
            raise ConnectionError("所有服务器连接失败")

    def close(self):
        """关闭当前线程的 mootdx client"""
        client = getattr(_client_local, "client", None)
        if client:
            try:
                client.close()
            except Exception:
                pass
            _client_local.client = None

    def _fill_turnover_and_shares(self, df: pd.DataFrame, stock_code: str):
        """填充流通股本(outstanding_share)和换手率(turnover)

        用总股本近似流通股本(A股已基本全流通,误差通常<5%)
        换手率 = 成交量 / 流通股本 * 100
        """
        try:
            row = self.db_ops.conn.execute(
                "SELECT total_shares FROM stock_capital "
                "WHERE stock_code = ? ORDER BY record_date DESC LIMIT 1",
                [stock_code]
            ).fetchone()
            if row and row[0] and row[0] > 0:
                shares = int(row[0])
                df["outstanding_share"] = shares
                df["turnover"] = (df["volume"].astype(float) / shares * 100).round(6)
            else:
                df["outstanding_share"] = None
                df["turnover"] = None
                logger.debug(f"[mootdx] {stock_code} 无股本数据,turnover/outstanding_share 置空")
        except Exception as e:
            df["outstanding_share"] = None
            df["turnover"] = None
            logger.debug(f"[mootdx] {stock_code} 填充换手率失败: {e}")

    def collect_stock(self, stock_code: str):
        steps = [
            ("日线数据(mootdx)", self.collect_daily_data),
        ]
        for name, method in steps:
            try:
                method(stock_code)
            except Exception as e:
                logger.error(f"{stock_code} {name}采集失败: {e}")

    @retry(max_attempts=3, delay=2.0)
    def collect_daily_data(self, stock_code: str):
        """通过mootdx采集日线K线数据"""
        last_update = self.db_ops.get_last_update_date(stock_code, "daily", self.start_date)
        today = datetime.now().strftime("%Y%m%d")

        if last_update > today:
            logger.info(f"{stock_code} 日线数据已是最新")
            return

        logger.info(f"[mootdx] 开始采集 {stock_code} 日线数据")

        code = stock_code[2:]
        client = self._get_client()

        if client is None:
            logger.warning(f"[mootdx] {stock_code} 客户端初始化失败, 直接回退到AKShare")
            return self._fallback_akshare(stock_code)

        # mootdx frequency: 4=日线, 5=周线, 6=月线
        # offset=0 表示最新数据, 需要计算需要多少条
        # 先获取足够多的数据覆盖日期范围
        start_dt = datetime.strptime(self.start_date, "%Y%m%d")
        days_diff = (datetime.now() - start_dt).days
        offset = max(days_diff + 50, 8000)  # 多取一些确保覆盖

        df = client.bars(symbol=code, frequency=4, start=0, offset=offset)

        if df is None or df.empty:
            logger.warning(f"[mootdx] {stock_code} 未获取到数据，回退到AKShare")
            return self._fallback_akshare(stock_code)

        # mootdx返回的列: open, close, high, low, vol, amount, year, month, day, hour, minute, datetime, volume
        df = df.rename(columns={
            'vol': 'volume',
        })

        # 处理日期
        df['trade_date'] = pd.to_datetime(df['datetime']).dt.date

        # 过滤日期范围
        last_update_date = datetime.strptime(last_update, "%Y%m%d").date()
        df = df[df['trade_date'] >= last_update_date]

        if df.empty:
            logger.info(f"[mootdx] {stock_code} 没有新日线数据")
            return

        # 选择需要的列
        cols = ['trade_date', 'open', 'high', 'low', 'close', 'volume', 'amount']
        available_cols = [c for c in cols if c in df.columns]
        df = df[available_cols].copy()
        df["stock_code"] = stock_code

        # 去重
        df = df.loc[:, ~df.columns.duplicated(keep='last')]

        # 填充流通股本和换手率(用总股本近似流通股本,A股已基本全流通)
        self._fill_turnover_and_shares(df, stock_code)

        today_fmt = datetime.now().strftime("%Y-%m-%d")
        # 事务保证: 数据写入 + 水位更新 原子化
        # Parquet 写入非事务性,但已有去重逻辑兜底,失败重跑会覆盖
        try:
            with self.db_ops.transaction():
                self.db_ops.insert_dataframe("stock_daily", df, ["stock_code", "trade_date"])
                self.db_ops.update_last_update_date(stock_code, "daily", today_fmt)
            self.parquet_store.write_daily(df)
            logger.info(f"[mootdx] {stock_code} 日线数据完成，新增 {len(df)} 条")
            return True
        except Exception as e:
            logger.error(f"[mootdx] {stock_code} 日线写入失败,已回滚: {e}")
            raise

    def _fallback_akshare(self, stock_code: str):
        """AKShare回退方案"""
        try:
            import akshare as ak
            logger.info(f"[AKShare回退] 采集 {stock_code} 日线数据")

            last_update = self.db_ops.get_last_update_date(stock_code, "daily", self.start_date)
            today = datetime.now().strftime("%Y%m%d")

            code = stock_code[2:]
            is_etf = (stock_code.startswith('sh') and code.startswith('5')) or \
                     (stock_code.startswith('sz') and code.startswith('1'))

            if is_etf:
                try:
                    df = ak.fund_etf_hist_sina(symbol=stock_code)
                    df = df.rename(columns={"date": "trade_date"})
                except Exception:
                    df = ak.fund_etf_hist_em(
                        symbol=code, period='daily',
                        start_date=last_update, end_date=today, adjust='qfq'
                    )
                    df = df.rename(columns={
                        "日期": "trade_date", "开盘": "open", "收盘": "close",
                        "最高": "high", "最低": "low", "成交量": "volume",
                        "成交额": "amount", "振幅": "amplitude", "涨跌幅": "change_pct"
                    })
            else:
                df = ak.stock_zh_a_daily(
                    symbol=stock_code, start_date=last_update,
                    end_date=today, adjust="qfq"
                )
                df = df.rename(columns={"date": "trade_date"})

            if df.empty:
                return

            df = df.loc[:, ~df.columns.duplicated(keep='last')]
            df["stock_code"] = stock_code
            df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.date

            # 填充流通股本和换手率
            self._fill_turnover_and_shares(df, stock_code)

            today_fmt = datetime.now().strftime("%Y-%m-%d")
            # 事务保证: 数据写入 + 水位更新 原子化
            try:
                with self.db_ops.transaction():
                    self.db_ops.insert_dataframe("stock_daily", df, ["stock_code", "trade_date"])
                    self.db_ops.update_last_update_date(stock_code, "daily", today_fmt)
                self.parquet_store.write_daily(df)
                logger.info(f"[AKShare回退] {stock_code} 日线数据完成，新增 {len(df)} 条")
                return True
            except Exception as e:
                logger.error(f"[AKShare回退] {stock_code} 日线写入失败,已回滚: {e}")
                return False
        except Exception as e:
            logger.error(f"[AKShare回退] {stock_code} 日线数据也失败: {e}")
            return False
