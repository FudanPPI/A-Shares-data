
import akshare as ak
import pandas as pd
import logging
from datetime import datetime
from .base import BaseCollector, retry

logger = logging.getLogger(__name__)


class EastmoneyCollector(BaseCollector):
    def __init__(self, db_ops, parquet_store, start_date: str):
        super().__init__(db_ops, parquet_store, start_date)
        self._init_column_metadata()

    def collect_stock(self, stock_code: str):
        steps = [
            ("日线数据", self.collect_daily_data),
            ("财务数据", self.collect_financial_data),
            ("财务字段补充", self._update_missing_financial_fields),
            ("股本数据", self.collect_capital_data),
            ("行业数据", self.collect_industry_data),
            ("分红数据", self.collect_dividend_data),
            ("公告数据", self.collect_announcements),
            ("北向资金", self.collect_northbound_flow),
            ("融资融券", self.collect_margin_trading),
            ("龙虎榜", self.collect_dragon_tiger),
        ]
        for name, method in steps:
            try:
                method(stock_code)
            except Exception as e:
                logger.error(f"{stock_code} {name}采集失败: {e}")

    @retry(max_attempts=3)
    def collect_daily_data(self, stock_code: str):
        last_update = self.db_ops.get_last_update_date(stock_code, "daily", self.start_date)
        today = datetime.now().strftime("%Y%m%d")

        if last_update > today:
            logger.info(f"{stock_code} 日线数据已是最新")
            return

        logger.info(f"开始采集 {stock_code} 日线数据")

        code = stock_code[2:]
        is_etf = (stock_code.startswith('sh') and code.startswith('5')) or \
                 (stock_code.startswith('sz') and code.startswith('1'))

        if is_etf:
            try:
                df = ak.fund_etf_hist_sina(symbol=stock_code)
                df = df.rename(columns={"date": "trade_date"})
            except Exception:
                df = ak.fund_etf_hist_em(
                    symbol=code,
                    period='daily',
                    start_date=last_update,
                    end_date=today,
                    adjust='qfq'
                )
                df = df.rename(columns={
                    "日期": "trade_date", "开盘": "open", "收盘": "close",
                    "最高": "high", "最低": "low", "成交量": "volume",
                    "成交额": "amount", "振幅": "amplitude", "涨跌幅": "change_pct"
                })
        else:
            df = ak.stock_zh_a_daily(
                symbol=stock_code,
                start_date=last_update,
                end_date=today,
                adjust="qfq"
            )
            df = df.rename(columns={"date": "trade_date"})

        if df.empty:
            logger.info(f"{stock_code} 没有新日线数据")
            return

        df = df.loc[:, ~df.columns.duplicated(keep='last')]
        df["stock_code"] = stock_code
        df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.date

        self.db_ops.insert_dataframe("stock_daily", df, ["stock_code", "trade_date"])
        self.parquet_store.write_daily(df)

        today_fmt = datetime.now().strftime("%Y-%m-%d")
        self.db_ops.update_last_update_date(stock_code, "daily", today_fmt)
        logger.info(f"{stock_code} 日线数据完成，新增 {len(df)} 条")

    def collect_financial_data(self, stock_code: str):
        last_update = self.db_ops.get_last_update_date(stock_code, "financial", self.start_date)
        today_fmt = datetime.now().strftime("%Y-%m-%d")

        logger.info(f"开始采集 {stock_code} 财务数据")
        income_df = ak.stock_financial_report_sina(stock=stock_code, symbol="利润表")
        balance_df = ak.stock_financial_report_sina(stock=stock_code, symbol="资产负债表")
        cashflow_df = ak.stock_financial_report_sina(stock=stock_code, symbol="现金流量表")

        income_df["报告日"] = pd.to_datetime(income_df["报告日"])
        balance_df["报告日"] = pd.to_datetime(balance_df["报告日"])
        cashflow_df["报告日"] = pd.to_datetime(cashflow_df["报告日"])

        merged = income_df[["报告日", "类型"]].drop_duplicates()

        income_map = income_df.set_index(["报告日", "类型"])
        balance_map = balance_df.set_index(["报告日", "类型"])
        cashflow_map = cashflow_df.set_index(["报告日", "类型"])

        announcement_date_map = {}
        for _, row in income_df.iterrows():
            key = (row["报告日"], row["类型"])
            announcement_date_map[key] = row.get("公告日期")

        financial_data = []
        for _, row in merged.iterrows():
            key = (row["报告日"], row["类型"])
            data = {
                "stock_code": stock_code,
                "report_date": key[0],
                "report_type": key[1],
                "total_revenue": None,
                "net_profit": None,
                "total_assets": None,
                "total_liabilities": None,
                "operating_cash_flow": None,
                "eps": None,
                "roe": None,
                "equity_parent": None,
                "announcement_date": None,
                "operating_cost": None,
                "net_profit_deducted": None,
                "inventory": None,
                "accounts_receivable": None,
                "accounts_payable": None,
                "capex": None,
                "interest_expense": None,
            }

            if key in income_map.index:
                ir = income_map.loc[key]
                data["total_revenue"] = self._safe_get(ir, "营业总收入")
                data["net_profit"] = self._safe_get(ir, "净利润")
                data["eps"] = self._safe_get(ir, "基本每股收益")
                data["operating_cost"] = self._safe_get(ir, "营业成本")
                if data["operating_cost"] is None:
                    data["operating_cost"] = self._safe_get(ir, "营业总成本")
                data["net_profit_deducted"] = self._safe_get(ir, "扣除非经常性损益后的净利润")
                data["interest_expense"] = self._safe_get(ir, "利息费用")
                if data["interest_expense"] is None:
                    data["interest_expense"] = self._safe_get(ir, "利息支出")

            if key in balance_map.index:
                br = balance_map.loc[key]
                data["total_assets"] = self._safe_get(br, "资产总计")
                data["total_liabilities"] = self._safe_get(br, "负债合计")
                data["equity_parent"] = self._safe_get(br, "归属于母公司股东权益合计")
                data["inventory"] = self._safe_get(br, "存货")
                data["accounts_receivable"] = self._safe_get(br, "应收账款")
                data["accounts_payable"] = self._safe_get(br, "应付账款")

            if key in cashflow_map.index:
                cr = cashflow_map.loc[key]
                data["operating_cash_flow"] = self._safe_get(cr, "经营活动产生的现金流量净额")
                data["capex"] = self._safe_get(cr, "购建固定资产、无形资产和其他长期资产支付的现金")

            if key in announcement_date_map:
                data["announcement_date"] = announcement_date_map[key]

            if data["total_assets"] and data["total_liabilities"]:
                equity = data["total_assets"] - data["total_liabilities"]
                if equity and equity != 0 and data["net_profit"]:
                    data["roe"] = round(data["net_profit"] / equity * 100, 4)

            financial_data.append(data)

        df = pd.DataFrame(financial_data)
        if df.empty:
            return

        df["report_date"] = pd.to_datetime(df["report_date"]).dt.date
        df["announcement_date"] = pd.to_datetime(df["announcement_date"], errors="coerce").dt.date

        self._upsert_financial(df)
        self.parquet_store.write_financial(df)
        self.db_ops.update_last_update_date(stock_code, "financial", today_fmt)
        logger.info(f"{stock_code} 财务数据完成，新增 {len(df)} 条")

    def _upsert_financial(self, df):
        conn = self.db_ops.conn
        conn.register("df", df)
        conn.execute("""
        INSERT INTO financial_statements 
        (stock_code, report_date, report_type, total_revenue, net_profit,
         total_assets, total_liabilities, operating_cash_flow, eps, roe, equity_parent, announcement_date,
         operating_cost, net_profit_deducted, inventory, accounts_receivable, accounts_payable, capex, interest_expense)
        SELECT stock_code, report_date, report_type, total_revenue, net_profit,
               total_assets, total_liabilities, operating_cash_flow, eps, roe, equity_parent, announcement_date,
               operating_cost, net_profit_deducted, inventory, accounts_receivable, accounts_payable, capex, interest_expense
        FROM df
        ON CONFLICT (stock_code, report_date, report_type) DO UPDATE SET
            total_revenue = EXCLUDED.total_revenue,
            net_profit = EXCLUDED.net_profit,
            total_assets = EXCLUDED.total_assets,
            total_liabilities = EXCLUDED.total_liabilities,
            operating_cash_flow = EXCLUDED.operating_cash_flow,
            eps = EXCLUDED.eps,
            roe = EXCLUDED.roe,
            equity_parent = EXCLUDED.equity_parent,
            announcement_date = EXCLUDED.announcement_date,
            operating_cost = EXCLUDED.operating_cost,
            net_profit_deducted = EXCLUDED.net_profit_deducted,
            inventory = EXCLUDED.inventory,
            accounts_receivable = EXCLUDED.accounts_receivable,
            accounts_payable = EXCLUDED.accounts_payable,
            capex = EXCLUDED.capex,
            interest_expense = EXCLUDED.interest_expense
        """)
        conn.unregister("df")

    def collect_capital_data(self, stock_code: str):
        logger.info(f"开始采集 {stock_code} 总股本")
        code = stock_code[2:]
        try:
            df = ak.stock_profile_cninfo(symbol=code)
            reg_cap = df['注册资金'].iloc[0]
            total_shares = int(float(reg_cap) * 10000)
        except Exception as e:
            logger.warning(f"{stock_code} 总股本采集失败(CNInfo): {e}")
            return

        today = datetime.now().strftime("%Y-%m-%d")
        self.db_ops.conn.execute("""
        INSERT INTO stock_capital (stock_code, record_date, total_shares)
        VALUES (?, ?, ?)
        ON CONFLICT (stock_code, record_date) DO UPDATE SET total_shares = EXCLUDED.total_shares
        """, (stock_code, today, total_shares))
        logger.info(f"{stock_code} 总股本完成: {total_shares}")

    def collect_industry_data(self, stock_code: str):
        logger.info(f"开始采集 {stock_code} 行业信息")
        code = stock_code[2:]
        try:
            df = ak.stock_profile_cninfo(symbol=code)
            industry_name = df['所属行业'].iloc[0]
        except Exception as e:
            logger.warning(f"{stock_code} 行业信息采集失败(CNInfo): {e}")
            return

        if not industry_name:
            logger.info(f"{stock_code} 未找到行业信息")
            return

        today = datetime.now().strftime("%Y-%m-%d")
        self.db_ops.conn.execute("""
        INSERT INTO stock_industry (stock_code, industry_name, industry_level, source, update_date)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT (stock_code) DO UPDATE SET
            industry_name = EXCLUDED.industry_name,
            update_date = EXCLUDED.update_date
        """, (stock_code, industry_name, "巨潮行业", "CNInfo", today))
        logger.info(f"{stock_code} 行业信息完成: {industry_name}")

    def collect_dividend_data(self, stock_code: str):
        logger.info(f"开始采集 {stock_code} 分红数据")
        code = stock_code[2:]
        try:
            df = ak.stock_history_dividend_detail(symbol=code, indicator="分红")
        except:
            return

        if df.empty:
            return

        dividend_data = []
        for _, row in df.iterrows():
            cash_per_share_raw = self._safe_get(row, '派息')
            if cash_per_share_raw is None or cash_per_share_raw == 0:
                continue
            progress = str(row.get('进度', ''))
            if '实施' not in progress:
                continue
            dividend_date = row.get('除权除息日')
            if pd.isna(dividend_date):
                continue
            dividend_date = pd.to_datetime(dividend_date).date()
            announcement_date = row.get('公告日期')
            if not pd.isna(announcement_date):
                announcement_date = pd.to_datetime(announcement_date).date()
            else:
                announcement_date = None
            cash_per_share = round(cash_per_share_raw / 10, 4)
            dividend_data.append({
                'stock_code': stock_code,
                'dividend_date': dividend_date,
                'cash_per_share': cash_per_share,
                'announcement_date': announcement_date
            })

        if not dividend_data:
            return

        df_div = pd.DataFrame(dividend_data)
        self.db_ops.insert_dataframe("dividends", df_div, ["stock_code", "dividend_date"])
        logger.info(f"{stock_code} 分红完成，新增 {len(df_div)} 条")

    @staticmethod
    def _safe_get(row, col_name):
        val = row.get(col_name) if hasattr(row, "get") else None
        if val is None:
            return None
        try:
            result = float(val)
            if pd.isna(result):
                return None
            return result
        except (ValueError, TypeError):
            return None

    def _init_column_metadata(self):
        conn = self.db_ops.conn
        metadata = [
            ("stock_daily", "stock_code", "股票代码", None),
            ("stock_daily", "trade_date", "交易日期", None),
            ("stock_daily", "open", "开盘价", "元"),
            ("stock_daily", "high", "最高价", "元"),
            ("stock_daily", "low", "最低价", "元"),
            ("stock_daily", "close", "收盘价", "元"),
            ("stock_daily", "volume", "成交量", "股"),
            ("stock_daily", "amount", "成交额", "元"),
            ("stock_daily", "adjust_factor", "复权因子", None),
            ("financial_statements", "stock_code", "股票代码", None),
            ("financial_statements", "report_date", "报告期", None),
            ("financial_statements", "report_type", "报告类型", None),
            ("financial_statements", "total_revenue", "营业收入", "元"),
            ("financial_statements", "net_profit", "净利润", "元"),
            ("financial_statements", "total_assets", "总资产", "元"),
            ("financial_statements", "total_liabilities", "总负债", "元"),
        ]

        for table_name, column_name, description, unit in metadata:
            try:
                conn.execute("""
                INSERT OR REPLACE INTO column_metadata 
                (table_name, column_name, description, unit)
                VALUES (?, ?, ?, ?)
                """, (table_name, column_name, description, unit))
            except Exception as e:
                logger.debug(f"元数据插入跳过: {e}")

    def _update_missing_financial_fields(self, stock_code: str):
        try:
            income_df = ak.stock_financial_report_sina(stock=stock_code, symbol="利润表")
            income_df["报告日"] = pd.to_datetime(income_df["报告日"]).dt.date

            for _, row in income_df.iterrows():
                rd = row["报告日"]
                rt = row["类型"]
                interest = self._safe_get(row, "利息费用")
                if interest is None:
                    interest = self._safe_get(row, "利息支出")
                if interest is not None:
                    self.db_ops.conn.execute("""
                        UPDATE financial_statements 
                        SET interest_expense = ? 
                        WHERE stock_code = ? AND report_date = ? AND report_type = ?
                    """, [interest, stock_code, rd, rt])
        except Exception as e:
            logger.warning(f"{stock_code} Sina利息支出补充采集失败：{e}")

        try:
            if stock_code.startswith('sh'):
                em_code = 'SH' + stock_code[2:]
            elif stock_code.startswith('sz'):
                em_code = 'SZ' + stock_code[2:]
            else:
                em_code = stock_code.upper()

            df = ak.stock_profit_sheet_by_report_em(symbol=em_code)
            df['report_date'] = pd.to_datetime(df['REPORT_DATE']).dt.date

            for _, row in df.iterrows():
                rd = row['report_date']

                deducted = row.get('DEDUCT_PARENT_NETPROFIT')
                if pd.notna(deducted):
                    self.db_ops.conn.execute("""
                        UPDATE financial_statements 
                        SET net_profit_deducted = ? 
                        WHERE stock_code = ? AND report_date = ?
                    """, [float(deducted), stock_code, rd])

                existing = self.db_ops.conn.execute("""
                    SELECT interest_expense FROM financial_statements 
                    WHERE stock_code = ? AND report_date = ?
                """, [stock_code, rd]).fetchone()

                if existing is None or existing[0] is None:
                    interest = row.get('INTEREST_EXPENSE')
                    if pd.isna(interest):
                        interest = row.get('FE_INTEREST_EXPENSE')
                    if pd.isna(interest):
                        interest = row.get('FINANCE_EXPENSE')
                    if pd.notna(interest):
                        self.db_ops.conn.execute("""
                            UPDATE financial_statements 
                            SET interest_expense = ? 
                            WHERE stock_code = ? AND report_date = ?
                        """, [float(interest), stock_code, rd])
        except Exception as e:
            logger.warning(f"{stock_code} 东方财富补充采集失败：{e}")

    def collect_announcements(self, stock_code: str):
        last_update = self.db_ops.get_last_update_date(stock_code, "announcement", self.start_date)
        today_ymd = datetime.now().strftime("%Y%m%d")

        if last_update > today_ymd:
            logger.info(f"{stock_code} 公告数据已是最新")
            return

        try:
            start_fmt = f"{last_update[:4]}-{last_update[4:6]}-{last_update[6:8]}"
            end_fmt = datetime.now().strftime("%Y-%m-%d")
            logger.info(f"开始采集 {stock_code} 公告数据")

            code = stock_code[2:]
            df = ak.stock_individual_notice_report(
                security=code,
                begin_date=start_fmt,
                end_date=end_fmt
            )

            if df.empty:
                logger.info(f"{stock_code} 没有新公告数据")
                return

            df = df.rename(columns={
                "公告标题": "title",
                "公告类型": "announcement_type",
                "公告日期": "announcement_date",
                "网址": "pdf_url"
            })
            df["stock_code"] = stock_code
            df["announcement_date"] = pd.to_datetime(df["announcement_date"]).dt.date

            self.db_ops.insert_dataframe("announcements", df, ["stock_code", "announcement_date", "title"])

            today_fmt = datetime.now().strftime("%Y-%m-%d")
            self.db_ops.update_last_update_date(stock_code, "announcement", today_fmt)
            logger.info(f"{stock_code} 公告数据完成，新增 {len(df)} 条")

        except Exception as e:
            logger.error(f"{stock_code} 公告数据采集失败：{str(e)}")

    def collect_northbound_flow(self, stock_code: str):
        try:
            logger.info(f"开始采集 {stock_code} 北向资金")

            code = stock_code[2:]
            df = ak.stock_hsgt_individual_em(symbol=code)

            if df.empty:
                logger.info(f"{stock_code} 没有北向资金数据")
                return

            df = df.rename(columns={
                "持股日期": "trade_date",
                "今日增持资金": "net_inflow",
                "持股数量": "holding_shares",
                "持股市值": "holding_value",
                "持股数量占A股百分比": "holding_ratio"
            })
            df['stock_code'] = stock_code
            df['trade_date'] = pd.to_datetime(df['trade_date']).dt.date

            self.db_ops.insert_dataframe("northbound_flow", df, ["stock_code", "trade_date"])

            today_fmt = datetime.now().strftime("%Y-%m-%d")
            self.db_ops.update_last_update_date(stock_code, "northbound", today_fmt)
            logger.info(f"{stock_code} 北向资金完成，新增 {len(df)} 条")

        except Exception as e:
            logger.error(f"{stock_code} 北向资金采集失败：{str(e)}")

    def collect_margin_trading(self, stock_code: str):
        try:
            logger.info(f"开始采集 {stock_code} 融资融券")

            code = stock_code[2:]
            today = datetime.now()
            margin_api = ak.stock_margin_detail_sse if stock_code.startswith('sh') else ak.stock_margin_detail_szse

            all_data = []
            for i in range(60):
                check_date = today - pd.Timedelta(days=i)
                date_str = check_date.strftime("%Y%m%d")
                try:
                    df = margin_api(date=date_str)
                    if df.empty:
                        continue
                    code_col = None
                    for c in ['标的证券代码', '标的代码', '证券代码']:
                        if c in df.columns:
                            code_col = c
                            break
                    df_filtered = df[df[code_col].astype(str) == code] if code_col else pd.DataFrame()
                    if not df_filtered.empty:
                        df_filtered = df_filtered.copy()
                        df_filtered['_trade_date'] = check_date.date()
                        all_data.append(df_filtered)
                except Exception:
                    continue

            if not all_data:
                logger.info(f"{stock_code} 没有融资融券数据")
                return

            df = pd.concat(all_data, ignore_index=True)
            df['trade_date'] = pd.to_datetime(df['_trade_date']).dt.date
            df = df.rename(columns={
                "融资余额": "rz_balance",
                "融券余额": "rq_balance"
            })
            df['stock_code'] = stock_code
            df = df.sort_values('trade_date').reset_index(drop=True)

            if 'rz_balance' in df.columns:
                df['rz_change'] = df['rz_balance'].diff()
                df['rz_change_pct'] = df['rz_change'] / df['rz_balance'].shift(1) * 100

            if 'rq_balance' in df.columns:
                df['rq_change'] = df['rq_balance'].diff()
                df['rq_change_pct'] = df['rq_change'] / df['rq_balance'].shift(1) * 100

            df['total_balance'] = df.get('rz_balance', 0) + df.get('rq_balance', 0)
            df['total_change'] = df.get('rz_change', 0) + df.get('rq_change', 0)
            df['total_change_pct'] = df['total_change'] / df['total_balance'].shift(1) * 100

            self.db_ops.insert_dataframe("margin_trading", df, ["stock_code", "trade_date"])

            today_fmt = datetime.now().strftime("%Y-%m-%d")
            self.db_ops.update_last_update_date(stock_code, "margin", today_fmt)
            logger.info(f"{stock_code} 融资融券完成，新增 {len(df)} 条")

        except Exception as e:
            logger.error(f"{stock_code} 融资融券采集失败：{str(e)}")

    def collect_dragon_tiger(self, stock_code: str):
        try:
            logger.info(f"开始采集 {stock_code} 龙虎榜")

            code = stock_code[2:]
            today = datetime.now().strftime("%Y%m%d")

            try:
                df_lhb = ak.stock_lhb_detail_em(start_date=today, end_date=today)

                if not df_lhb.empty:
                    df_lhb = df_lhb[df_lhb['代码'].astype(str) == code]

                    if not df_lhb.empty:
                        for _, row in df_lhb.iterrows():
                            try:
                                self.db_ops.conn.execute("""
                                INSERT INTO dragon_tiger 
                                (stock_code, trade_date, list_type, reason, buy_amount, sell_amount, net_amount)
                                VALUES (?, ?, ?, ?, ?, ?, ?)
                                ON CONFLICT (stock_code, trade_date, list_type) DO UPDATE SET
                                    reason = EXCLUDED.reason,
                                    buy_amount = EXCLUDED.buy_amount,
                                    sell_amount = EXCLUDED.sell_amount,
                                    net_amount = EXCLUDED.net_amount
                                """, (
                                    stock_code,
                                    pd.to_datetime(row['上榜日']).date(),
                                    '上榜',
                                    row.get('上榜原因'),
                                    self._safe_get(row, '龙虎榜买入额'),
                                    self._safe_get(row, '龙虎榜卖出额'),
                                    self._safe_get(row, '龙虎榜净买额')
                                ))
                            except Exception as e:
                                logger.error(f"{stock_code} 龙虎榜单条插入失败：{str(e)}")

                        logger.info(f"{stock_code} 龙虎榜数据完成")
            except Exception as e:
                logger.debug(f"获取龙虎榜详细数据失败：{str(e)}")

        except Exception as e:
            logger.error(f"{stock_code} 龙虎榜采集失败：{str(e)}")
