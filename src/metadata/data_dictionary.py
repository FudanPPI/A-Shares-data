"""
数据字典 - 所有表和字段的唯一权威定义

设计原则:
  - 任何字段的业务含义、数据来源、计算公式只在此定义
  - 可编程消费: API可用此生成文档, DDL可与此交叉校验
  - 数据血缘可追溯: 通过 source 和 calculation 字段自动生成血缘图

数据分类:
  - raw: 原始采集数据
  - derived_simple: 简单派生(涨跌幅、振幅等)
  - derived_technical: 技术指标
  - derived_financial: 财务指标
  - derived_valuation: 估值指标

数据来源:
  - mootdx: TCP直连通达信服务器
  - baostock: BaoStock免费证券数据
  - tencent: 腾讯财经
  - akshare_sina: AKShare 新浪接口
  - akshare_em: AKShare 东方财富接口
  - calculated: 内部计算派生
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


# =============================================================================
# 枚举定义
# =============================================================================

class DataSource(Enum):
    """数据来源"""
    MOOTDX = "mootdx"                     # TCP直连通达信(日线行情)
    BAOSTOCK = "baostock"                 # 免费证券数据(股本/行业/分红)
    TENCENT = "tencent"                   # 腾讯财经(估值PE/PB)
    AKSHARE_SINA = "akshare_sina"         # AKShare新浪接口(财务三大报表)
    AKSHARE_EM = "akshare_em"             # AKShare东方财富EM(补充字段)
    AKSHARE = "akshare"                   # AKShare(融资融券/公告/龙虎榜)
    CALCULATED = "calculated"             # 内部计算派生
    INTERNAL = "internal"                 # 系统内部元数据


class DataCategory(Enum):
    """数据分类"""
    RAW = "raw"                           # 原始采集
    DERIVED_SIMPLE = "derived_simple"     # 简单派生
    DERIVED_TECHNICAL = "derived_technical"  # 技术指标
    DERIVED_FINANCIAL = "derived_financial"  # 财务指标
    DERIVED_VALUATION = "derived_valuation"  # 估值指标
    METADATA = "metadata"                 # 元数据


# =============================================================================
# 字段定义
# =============================================================================

@dataclass
class FieldDef:
    """字段定义"""
    column_name: str                     # 数据库列名
    display_name: str                    # 中文显示名
    description: str                     # 业务含义
    data_type: str                       # 数据库类型
    nullable: bool = True
    source: DataSource = DataSource.CALCULATED
    category: DataCategory = DataCategory.RAW
    calculation: Optional[str] = None    # 计算公式(仅派生字段)
    unit: Optional[str] = None           # 单位
    example: Optional[str] = None        # 示例值


@dataclass
class TableDef:
    """表定义"""
    table_name: str                      # 数据库表名
    display_name: str                    # 中文表名
    description: str                     # 表用途说明
    primary_key: list                    # 主键列
    refresh_frequency: str               # 更新频率: daily/weekly/quarterly/on_demand
    fields: list                         # FieldDef 列表


# =============================================================================
# =========================== 表定义开始 ======================================
# =============================================================================

# ---- stock_daily: 日线行情 ----
STOCK_DAILY = TableDef(
    table_name="stock_daily",
    display_name="日线行情",
    description="每只股票每个交易日的OHLCV行情数据及简单派生指标。主源mootdx(TCP直连通达信)，备源AKShare。",
    primary_key=["stock_code", "trade_date"],
    refresh_frequency="daily",
    fields=[
        FieldDef("stock_code", "股票代码", "sh/sz + 6位数字", "VARCHAR(10)",
                 nullable=False, source=DataSource.MOOTDX, example="sh600519"),
        FieldDef("trade_date", "交易日期", "YYYY-MM-DD", "DATE",
                 nullable=False, source=DataSource.MOOTDX),
        FieldDef("open", "开盘价", "当日第一笔成交价", "DECIMAL(10,2)",
                 source=DataSource.MOOTDX, unit="元"),
        FieldDef("high", "最高价", "当日最高成交价", "DECIMAL(10,2)",
                 source=DataSource.MOOTDX, unit="元"),
        FieldDef("low", "最低价", "当日最低成交价", "DECIMAL(10,2)",
                 source=DataSource.MOOTDX, unit="元"),
        FieldDef("close", "收盘价", "当日最后一笔成交价", "DECIMAL(10,2)",
                 source=DataSource.MOOTDX, unit="元"),
        FieldDef("volume", "成交量", "当日成交股数", "BIGINT",
                 source=DataSource.MOOTDX, unit="股"),
        FieldDef("amount", "成交额", "当日成交金额", "DECIMAL(18,2)",
                 source=DataSource.MOOTDX, unit="元"),
        FieldDef("adjust_factor", "复权因子", "前复权因子，用于价格复权计算", "DECIMAL(10,6)",
                 source=DataSource.MOOTDX),
        FieldDef("prev_close", "前收盘价", "上一交易日收盘价", "DECIMAL(10,2)",
                 source=DataSource.CALCULATED, category=DataCategory.DERIVED_SIMPLE,
                 calculation="close.shift(1)", unit="元"),
        FieldDef("change_pct", "涨跌幅", "当日涨跌百分比", "DECIMAL(10,4)",
                 source=DataSource.CALCULATED, category=DataCategory.DERIVED_SIMPLE,
                 calculation="(close - prev_close) / prev_close * 100", unit="%"),
        FieldDef("amplitude", "振幅", "当日最高最低价波动幅度", "DECIMAL(10,4)",
                 source=DataSource.CALCULATED, category=DataCategory.DERIVED_SIMPLE,
                 calculation="(high - low) / prev_close * 100", unit="%"),
        FieldDef("body_size", "实体大小", "K线实体绝对值", "DECIMAL(10,4)",
                 source=DataSource.CALCULATED, category=DataCategory.DERIVED_SIMPLE,
                 calculation="abs(close - open)", unit="元"),
        FieldDef("upper_shadow", "上影线", "K线上影线长度", "DECIMAL(10,4)",
                 source=DataSource.CALCULATED, category=DataCategory.DERIVED_SIMPLE,
                 calculation="high - max(open, close)", unit="元"),
        FieldDef("lower_shadow", "下影线", "K线下影线长度", "DECIMAL(10,4)",
                 source=DataSource.CALCULATED, category=DataCategory.DERIVED_SIMPLE,
                 calculation="min(open, close) - low", unit="元"),
        FieldDef("high_20", "20日最高价", "近20个交易日最高价", "DECIMAL(10,2)",
                 source=DataSource.CALCULATED, category=DataCategory.DERIVED_SIMPLE,
                 calculation="rolling(20).max() of high", unit="元"),
        FieldDef("low_20", "20日最低价", "近20个交易日最低价", "DECIMAL(10,2)",
                 source=DataSource.CALCULATED, category=DataCategory.DERIVED_SIMPLE,
                 calculation="rolling(20).min() of low", unit="元"),
        FieldDef("high_60", "60日最高价", "近60个交易日最高价", "DECIMAL(10,2)",
                 source=DataSource.CALCULATED, category=DataCategory.DERIVED_SIMPLE,
                 calculation="rolling(60).max() of high", unit="元"),
        FieldDef("low_60", "60日最低价", "近60个交易日最低价", "DECIMAL(10,2)",
                 source=DataSource.CALCULATED, category=DataCategory.DERIVED_SIMPLE,
                 calculation="rolling(60).min() of low", unit="元"),
        FieldDef("turnover", "换手率", "当日成交量 / 流通股本(来自腾讯财经)", "DECIMAL(10,6)",
                 source=DataSource.TENCENT, unit="比率"),
        FieldDef("outstanding_share", "流通股本", "流通在外股份数", "DECIMAL(20,0)",
                 source=DataSource.BAOSTOCK, unit="股"),
    ]
)

# ---- financial_statements: 财务报表 ----
FINANCIAL_STATEMENTS = TableDef(
    table_name="financial_statements",
    display_name="财务报表",
    description="每只股票每个报告期的合并财务报表数据。主源AKShare新浪接口(三大报表合并)，补充字段来自东方财富EM。",
    primary_key=["stock_code", "report_date", "report_type"],
    refresh_frequency="quarterly",
    fields=[
        FieldDef("stock_code", "股票代码", "sh/sz + 6位数字", "VARCHAR(10)",
                 nullable=False, source=DataSource.AKSHARE_SINA),
        FieldDef("report_date", "报告日期", "财务报告截止日期", "DATE",
                 nullable=False, source=DataSource.AKSHARE_SINA),
        FieldDef("report_type", "报告类型", "Q1/Q2/Q3/FY(年报)", "VARCHAR(20)",
                 nullable=False, source=DataSource.AKSHARE_SINA),
        FieldDef("total_revenue", "营业总收入", "合并利润表营业总收入", "DECIMAL(18,2)",
                 source=DataSource.AKSHARE_SINA, unit="元"),
        FieldDef("net_profit", "归母净利润", "归属母公司股东的净利润", "DECIMAL(18,2)",
                 source=DataSource.AKSHARE_SINA, unit="元"),
        FieldDef("total_assets", "总资产", "合并资产负债表总资产", "DECIMAL(18,2)",
                 source=DataSource.AKSHARE_SINA, unit="元"),
        FieldDef("total_liabilities", "总负债", "合并资产负债表总负债", "DECIMAL(18,2)",
                 source=DataSource.AKSHARE_SINA, unit="元"),
        FieldDef("operating_cash_flow", "经营活动现金流", "合并现金流量表经营活动现金流净额", "DECIMAL(18,2)",
                 source=DataSource.AKSHARE_SINA, unit="元"),
        FieldDef("eps", "每股收益", "基本每股收益(合并口径)", "DECIMAL(10,4)",
                 source=DataSource.AKSHARE_SINA, unit="元/股"),
        FieldDef("roe", "净资产收益率", "加权平均ROE(合并口径)", "DECIMAL(10,4)",
                 source=DataSource.AKSHARE_SINA, unit="%"),
        FieldDef("equity_parent", "归母权益", "归属母公司股东权益合计", "DECIMAL(18,2)",
                 source=DataSource.AKSHARE_SINA, unit="元"),
        FieldDef("announcement_date", "公告日期", "财务报告正式公告日期", "DATE",
                 source=DataSource.AKSHARE_SINA),
        FieldDef("operating_cost", "营业总成本", "合并利润表营业总成本", "DECIMAL(18,2)",
                 source=DataSource.AKSHARE_SINA, unit="元"),
        FieldDef("net_profit_deducted", "扣非净利润", "归属母公司扣非净利润(来自东方财富EM补充)", "DECIMAL(18,2)",
                 source=DataSource.AKSHARE_EM, unit="元"),
        FieldDef("inventory", "存货", "合并资产负债表存货", "DECIMAL(18,2)",
                 source=DataSource.AKSHARE_SINA, unit="元"),
        FieldDef("accounts_receivable", "应收账款", "合并资产负债表应收账款", "DECIMAL(18,2)",
                 source=DataSource.AKSHARE_SINA, unit="元"),
        FieldDef("accounts_payable", "应付账款", "合并资产负债表应付账款", "DECIMAL(18,2)",
                 source=DataSource.AKSHARE_SINA, unit="元"),
        FieldDef("capex", "资本支出", "购建固定资产/无形资产现金支出", "DECIMAL(18,2)",
                 source=DataSource.AKSHARE_SINA, unit="元"),
        FieldDef("interest_expense", "利息支出", "财务费用中的利息支出(来自东方财富EM补充)", "DECIMAL(18,2)",
                 source=DataSource.AKSHARE_EM, unit="元"),
        FieldDef("current_assets", "流动资产合计", "合并资产负债表流动资产合计(来自东方财富EM补充)", "DECIMAL(18,2)",
                 source=DataSource.AKSHARE_EM, unit="元"),
        FieldDef("current_liabilities", "流动负债合计", "合并资产负债表流动负债合计(来自东方财富EM补充)", "DECIMAL(18,2)",
                 source=DataSource.AKSHARE_EM, unit="元"),
    ]
)

# ---- announcements: 公告 ----
ANNOUNCEMENTS = TableDef(
    table_name="announcements",
    display_name="公告",
    description="上市公司公告列表，包含标题和PDF链接。数据源AKShare。",
    primary_key=["stock_code", "announcement_date", "title"],
    refresh_frequency="daily",
    fields=[
        FieldDef("id", "公告ID", "自增主键", "INTEGER", nullable=False,
                 source=DataSource.INTERNAL, category=DataCategory.METADATA),
        FieldDef("stock_code", "股票代码", "sh/sz + 6位数字", "VARCHAR(10)",
                 nullable=False, source=DataSource.AKSHARE),
        FieldDef("announcement_date", "公告日期", "公告发布日期", "DATE",
                 nullable=False, source=DataSource.AKSHARE),
        FieldDef("title", "公告标题", "公告标题全文", "VARCHAR(255)",
                 source=DataSource.AKSHARE),
        FieldDef("pdf_url", "PDF链接", "公告PDF文件下载地址", "VARCHAR(255)",
                 source=DataSource.AKSHARE),
        FieldDef("announcement_type", "公告类型", "如: 年报/季报/临时公告", "VARCHAR(50)",
                 source=DataSource.AKSHARE),
    ]
)

# ---- update_log: 更新日志 ----
UPDATE_LOG = TableDef(
    table_name="update_log",
    display_name="更新日志",
    description="记录每只股票每种数据类型的最后更新时间，驱动增量采集。系统内部元数据表。",
    primary_key=["stock_code", "data_type"],
    refresh_frequency="on_demand",
    fields=[
        FieldDef("id", "日志ID", "自增主键", "INTEGER", nullable=False,
                 source=DataSource.INTERNAL, category=DataCategory.METADATA),
        FieldDef("stock_code", "股票代码", "sh/sz + 6位数字", "VARCHAR(10)",
                 nullable=False, source=DataSource.INTERNAL, category=DataCategory.METADATA),
        FieldDef("data_type", "数据类型", "daily/financial/valuation等", "VARCHAR(20)",
                 nullable=False, source=DataSource.INTERNAL, category=DataCategory.METADATA),
        FieldDef("last_update_date", "最后更新日期", "YYYY-MM-DD", "DATE",
                 nullable=False, source=DataSource.INTERNAL, category=DataCategory.METADATA),
        FieldDef("update_time", "更新时间", "记录写入时间戳", "TIMESTAMP",
                 source=DataSource.INTERNAL, category=DataCategory.METADATA),
    ]
)

# ---- technical_indicators: 技术指标 ----
TECHNICAL_INDICATORS = TableDef(
    table_name="technical_indicators",
    display_name="技术指标",
    description="基于日线行情数据计算的30+个技术分析指标。每次全量重算(DELETE + INSERT)。",
    primary_key=["stock_code", "trade_date"],
    refresh_frequency="daily",
    fields=[
        # ---- 均线类 ----
        FieldDef("stock_code", "股票代码", "sh/sz + 6位数字", "VARCHAR(10)",
                 nullable=False, source=DataSource.CALCULATED, category=DataCategory.DERIVED_TECHNICAL),
        FieldDef("trade_date", "交易日期", "YYYY-MM-DD", "DATE",
                 nullable=False, source=DataSource.CALCULATED, category=DataCategory.DERIVED_TECHNICAL),
        FieldDef("ma5", "5日均线", "收盘价5日简单移动平均", "DECIMAL(10,2)",
                 source=DataSource.CALCULATED, category=DataCategory.DERIVED_TECHNICAL,
                 calculation="close.rolling(5).mean()", unit="元"),
        FieldDef("ma10", "10日均线", "收盘价10日简单移动平均", "DECIMAL(10,2)",
                 source=DataSource.CALCULATED, category=DataCategory.DERIVED_TECHNICAL,
                 calculation="close.rolling(10).mean()", unit="元"),
        FieldDef("ma20", "20日均线", "收盘价20日简单移动平均", "DECIMAL(10,2)",
                 source=DataSource.CALCULATED, category=DataCategory.DERIVED_TECHNICAL,
                 calculation="close.rolling(20).mean()", unit="元"),
        FieldDef("ma60", "60日均线", "收盘价60日简单移动平均", "DECIMAL(10,2)",
                 source=DataSource.CALCULATED, category=DataCategory.DERIVED_TECHNICAL,
                 calculation="close.rolling(60).mean()", unit="元"),
        FieldDef("ema12", "12日EMA", "收盘价12日指数移动平均", "DECIMAL(10,4)",
                 source=DataSource.CALCULATED, category=DataCategory.DERIVED_TECHNICAL,
                 calculation="close.ewm(span=12).mean()", unit="元"),
        FieldDef("ema26", "26日EMA", "收盘价26日指数移动平均", "DECIMAL(10,4)",
                 source=DataSource.CALCULATED, category=DataCategory.DERIVED_TECHNICAL,
                 calculation="close.ewm(span=26).mean()", unit="元"),

        # ---- BOLL 布林带 ----
        FieldDef("boll_mid", "BOLL中轨", "20日均线(布林带中轨)", "DECIMAL(10,2)",
                 source=DataSource.CALCULATED, category=DataCategory.DERIVED_TECHNICAL,
                 calculation="close.rolling(20).mean()", unit="元"),
        FieldDef("boll_upper", "BOLL上轨", "中轨 + 2倍标准差", "DECIMAL(10,2)",
                 source=DataSource.CALCULATED, category=DataCategory.DERIVED_TECHNICAL,
                 calculation="boll_mid + 2 * rolling(20).std()", unit="元"),
        FieldDef("boll_lower", "BOLL下轨", "中轨 - 2倍标准差", "DECIMAL(10,2)",
                 source=DataSource.CALCULATED, category=DataCategory.DERIVED_TECHNICAL,
                 calculation="boll_mid - 2 * rolling(20).std()", unit="元"),

        # ---- MACD ----
        FieldDef("macd_dif", "MACD DIF", "EMA12 - EMA26", "DECIMAL(10,4)",
                 source=DataSource.CALCULATED, category=DataCategory.DERIVED_TECHNICAL,
                 calculation="ema12 - ema26"),
        FieldDef("macd_dea", "MACD DEA", "DIF的9日EMA", "DECIMAL(10,4)",
                 source=DataSource.CALCULATED, category=DataCategory.DERIVED_TECHNICAL,
                 calculation="macd_dif.ewm(span=9).mean()"),
        FieldDef("macd_hist", "MACD柱", "(DIF - DEA) × 2", "DECIMAL(10,4)",
                 source=DataSource.CALCULATED, category=DataCategory.DERIVED_TECHNICAL,
                 calculation="(macd_dif - macd_dea) * 2"),

        # ---- BIAS 乖离率 ----
        FieldDef("bias5", "5日乖离率", "(收盘价-5日均线)/5日均线×100", "DECIMAL(10,4)",
                 source=DataSource.CALCULATED, category=DataCategory.DERIVED_TECHNICAL,
                 calculation="(close - ma5) / ma5 * 100", unit="%"),
        FieldDef("bias10", "10日乖离率", "(收盘价-10日均线)/10日均线×100", "DECIMAL(10,4)",
                 source=DataSource.CALCULATED, category=DataCategory.DERIVED_TECHNICAL,
                 calculation="(close - ma10) / ma10 * 100", unit="%"),
        FieldDef("bias20", "20日乖离率", "(收盘价-20日均线)/20日均线×100", "DECIMAL(10,4)",
                 source=DataSource.CALCULATED, category=DataCategory.DERIVED_TECHNICAL,
                 calculation="(close - ma20) / ma20 * 100", unit="%"),
        FieldDef("bias60", "60日乖离率", "(收盘价-60日均线)/60日均线×100", "DECIMAL(10,4)",
                 source=DataSource.CALCULATED, category=DataCategory.DERIVED_TECHNICAL,
                 calculation="(close - ma60) / ma60 * 100", unit="%"),

        # ---- RSI 相对强弱 ----
        FieldDef("rsi6", "RSI(6)", "6日相对强弱指标", "DECIMAL(10,4)",
                 source=DataSource.CALCULATED, category=DataCategory.DERIVED_TECHNICAL,
                 calculation="100 - 100/(1+avg_gain_6/avg_loss_6)", unit="值"),
        FieldDef("rsi12", "RSI(12)", "12日相对强弱指标", "DECIMAL(10,4)",
                 source=DataSource.CALCULATED, category=DataCategory.DERIVED_TECHNICAL,
                 calculation="100 - 100/(1+avg_gain_12/avg_loss_12)", unit="值"),
        FieldDef("rsi24", "RSI(24)", "24日相对强弱指标", "DECIMAL(10,4)",
                 source=DataSource.CALCULATED, category=DataCategory.DERIVED_TECHNICAL,
                 calculation="100 - 100/(1+avg_gain_24/avg_loss_24)", unit="值"),

        # ---- KDJ 随机指标 ----
        FieldDef("kdj_k", "KDJ K值", "随机指标K值", "DECIMAL(10,4)",
                 source=DataSource.CALCULATED, category=DataCategory.DERIVED_TECHNICAL,
                 calculation="RSV的3日EMA(com=2)", unit="值"),
        FieldDef("kdj_d", "KDJ D值", "随机指标D值", "DECIMAL(10,4)",
                 source=DataSource.CALCULATED, category=DataCategory.DERIVED_TECHNICAL,
                 calculation="K的3日EMA(com=2)", unit="值"),
        FieldDef("kdj_j", "KDJ J值", "随机指标J值", "DECIMAL(10,4)",
                 source=DataSource.CALCULATED, category=DataCategory.DERIVED_TECHNICAL,
                 calculation="3*K - 2*D", unit="值"),

        # ---- CCI 商品通道 ----
        FieldDef("cci20", "CCI(20)", "20日商品通道指数", "DECIMAL(10,4)",
                 source=DataSource.CALCULATED, category=DataCategory.DERIVED_TECHNICAL,
                 calculation="(TP - MA_TP) / (0.015 * MD)", unit="值"),

        # ---- WR 威廉指标 ----
        FieldDef("wr14", "WR(14)", "14日威廉指标", "DECIMAL(10,4)",
                 source=DataSource.CALCULATED, category=DataCategory.DERIVED_TECHNICAL,
                 calculation="(high14 - close) / (high14 - low14) * 100", unit="值"),

        # ---- ATR 真实波幅 ----
        FieldDef("atr14", "ATR(14)", "14日平均真实波幅", "DECIMAL(10,4)",
                 source=DataSource.CALCULATED, category=DataCategory.DERIVED_TECHNICAL,
                 calculation="TR的14日简单移动平均", unit="元"),

        # ---- 波动率 ----
        FieldDef("std20", "20日标准差", "收盘价20日滚动标准差", "DECIMAL(10,4)",
                 source=DataSource.CALCULATED, category=DataCategory.DERIVED_TECHNICAL,
                 calculation="close.rolling(20).std()", unit="元"),

        # ---- 成交量均线 ----
        FieldDef("vol_ma5", "5日均量", "成交量5日简单移动平均", "DECIMAL(20,0)",
                 source=DataSource.CALCULATED, category=DataCategory.DERIVED_TECHNICAL,
                 calculation="volume.rolling(5).mean()", unit="股"),
        FieldDef("vol_ma10", "10日均量", "成交量10日简单移动平均", "DECIMAL(20,0)",
                 source=DataSource.CALCULATED, category=DataCategory.DERIVED_TECHNICAL,
                 calculation="volume.rolling(10).mean()", unit="股"),

        # ---- OBV 能量潮 ----
        FieldDef("obv", "OBV", "能量潮指标(累积量)", "DECIMAL(20,0)",
                 source=DataSource.CALCULATED, category=DataCategory.DERIVED_TECHNICAL,
                 calculation="成交量按涨跌方向累加", unit="股"),

        # ---- MFI 资金流量 ----
        FieldDef("mfi14", "MFI(14)", "14日资金流量指数", "DECIMAL(10,4)",
                 source=DataSource.CALCULATED, category=DataCategory.DERIVED_TECHNICAL,
                 calculation="100 - 100/(1+pos_flow_14/neg_flow_14)", unit="值"),

        # ---- VR 成交量变异率 ----
        FieldDef("vr", "VR", "24日成交量变异率", "DECIMAL(10,4)",
                 source=DataSource.CALCULATED, category=DataCategory.DERIVED_TECHNICAL,
                 calculation="(up_vol24 + flat_vol24/2) / (down_vol24 + flat_vol24/2) * 100", unit="值"),

        # ---- DMI 趋向指标 ----
        FieldDef("dmi_pdi", "DMI +DI", "上升动向指标", "DECIMAL(10,4)",
                 source=DataSource.CALCULATED, category=DataCategory.DERIVED_TECHNICAL,
                 calculation="100 * +DM14 / ATR14", unit="值"),
        FieldDef("dmi_mdi", "DMI -DI", "下降动向指标", "DECIMAL(10,4)",
                 source=DataSource.CALCULATED, category=DataCategory.DERIVED_TECHNICAL,
                 calculation="100 * -DM14 / ATR14", unit="值"),
        FieldDef("dmi_adx", "DMI ADX", "平均趋向指数", "DECIMAL(10,4)",
                 source=DataSource.CALCULATED, category=DataCategory.DERIVED_TECHNICAL,
                 calculation="DX的14日移动平均", unit="值"),
        FieldDef("dmi_adxr", "DMI ADXR", "评估ADX", "DECIMAL(10,4)",
                 source=DataSource.CALCULATED, category=DataCategory.DERIVED_TECHNICAL,
                 calculation="(ADX + ADX_14d_ago) / 2", unit="值"),

        # ---- SAR 抛物线 ----
        FieldDef("sar", "SAR", "抛物线转向指标", "DECIMAL(10,2)",
                 source=DataSource.CALCULATED, category=DataCategory.DERIVED_TECHNICAL,
                 calculation="递推算法,加速因子0.02~0.2", unit="元"),

        # ---- WVAD 威廉变异离散量 ----
        FieldDef("wvad", "WVAD", "威廉变异离散量", "DECIMAL(18,4)",
                 source=DataSource.CALCULATED, category=DataCategory.DERIVED_TECHNICAL,
                 calculation="(close-open)/(high-low) * volume", unit="值"),
    ]
)

# ---- valuation_indicators: 估值指标 ----
VALUATION_INDICATORS = TableDef(
    table_name="valuation_indicators",
    display_name="估值指标",
    description="基于日线行情+财务数据+股本数据计算的每日估值指标。每日计算，使用当时最新公告的财务数据。",
    primary_key=["stock_code", "trade_date"],
    refresh_frequency="daily",
    fields=[
        FieldDef("stock_code", "股票代码", "sh/sz + 6位数字", "VARCHAR(10)",
                 nullable=False, source=DataSource.CALCULATED, category=DataCategory.DERIVED_VALUATION),
        FieldDef("trade_date", "交易日期", "YYYY-MM-DD", "DATE",
                 nullable=False, source=DataSource.CALCULATED, category=DataCategory.DERIVED_VALUATION),
        FieldDef("pe_ttm", "市盈率(TTM)", "总市值 / 滚动12个月归母净利润", "DECIMAL(10,4)",
                 source=DataSource.CALCULATED, category=DataCategory.DERIVED_VALUATION,
                 calculation="close * total_shares / net_profit_ttm", unit="倍"),
        FieldDef("pb", "市净率", "总市值 / 归母权益", "DECIMAL(10,4)",
                 source=DataSource.CALCULATED, category=DataCategory.DERIVED_VALUATION,
                 calculation="close * total_shares / equity_parent", unit="倍"),
        FieldDef("ps_ttm", "市销率(TTM)", "总市值 / 滚动12个月营业总收入", "DECIMAL(10,4)",
                 source=DataSource.CALCULATED, category=DataCategory.DERIVED_VALUATION,
                 calculation="close * total_shares / total_revenue_ttm", unit="倍"),
        FieldDef("dividend_yield", "股息率", "近12个月每股现金分红 / 当前股价 × 100", "DECIMAL(10,4)",
                 source=DataSource.CALCULATED, category=DataCategory.DERIVED_VALUATION,
                 calculation="SUM(近一年cash_per_share) / close * 100", unit="%"),
        FieldDef("roe", "ROE", "净资产收益率(来自财务中间表)", "DECIMAL(10,4)",
                 source=DataSource.CALCULATED, category=DataCategory.DERIVED_VALUATION,
                 calculation="取自 financial_intermediate.roe_ttm", unit="%"),
        FieldDef("pe_annual", "市盈率(静态)", "总市值 / 最近一期年报归母净利润", "DECIMAL(10,4)",
                 source=DataSource.CALCULATED, category=DataCategory.DERIVED_VALUATION,
                 calculation="close * total_shares / net_profit_annual", unit="倍"),
        FieldDef("ps_annual", "市销率(静态)", "总市值 / 最近一期年报营业总收入", "DECIMAL(10,4)",
                 source=DataSource.CALCULATED, category=DataCategory.DERIVED_VALUATION,
                 calculation="close * total_shares / total_revenue_annual", unit="倍"),
        FieldDef("roe_ttm", "ROE(TTM)", "滚动12个月ROE(来自财务中间表)", "DECIMAL(10,4)",
                 source=DataSource.CALCULATED, category=DataCategory.DERIVED_VALUATION,
                 calculation="取自 financial_intermediate.roe_ttm", unit="%"),
        FieldDef("roe_annual", "ROE(年度)", "年度ROE(来自财务中间表)", "DECIMAL(10,4)",
                 source=DataSource.CALCULATED, category=DataCategory.DERIVED_VALUATION,
                 calculation="取自 financial_intermediate.roe_annual", unit="%"),
        FieldDef("used_report_date", "使用报告期", "计算估值时使用的财务报告截止日期", "DATE",
                 source=DataSource.CALCULATED, category=DataCategory.DERIVED_VALUATION),
        FieldDef("used_announcement_date", "使用公告日", "计算估值时使用的财务报告公告日期", "DATE",
                 source=DataSource.CALCULATED, category=DataCategory.DERIVED_VALUATION),
    ]
)

# ---- stock_capital: 股本 ----
STOCK_CAPITAL = TableDef(
    table_name="stock_capital",
    display_name="股本",
    description="每只股票的总股本历史记录。主源BaoStock(盈利能力接口)，备源腾讯财经。",
    primary_key=["stock_code", "record_date"],
    refresh_frequency="quarterly",
    fields=[
        FieldDef("stock_code", "股票代码", "sh/sz + 6位数字", "VARCHAR(10)",
                 nullable=False, source=DataSource.BAOSTOCK),
        FieldDef("record_date", "记录日期", "股本数据记录日期", "DATE",
                 nullable=False, source=DataSource.BAOSTOCK),
        FieldDef("total_shares", "总股本", "总股本数(股)", "DECIMAL(20,0)",
                 source=DataSource.BAOSTOCK, unit="股"),
    ]
)

# ---- dividends: 分红 ----
DIVIDENDS = TableDef(
    table_name="dividends",
    display_name="分红",
    description="每只股票的历史现金分红记录。数据源BaoStock。",
    primary_key=["stock_code", "dividend_date"],
    refresh_frequency="on_demand",
    fields=[
        FieldDef("stock_code", "股票代码", "sh/sz + 6位数字", "VARCHAR(10)",
                 nullable=False, source=DataSource.BAOSTOCK),
        FieldDef("dividend_date", "除权除息日", "分红除权除息日期", "DATE",
                 nullable=False, source=DataSource.BAOSTOCK),
        FieldDef("cash_per_share", "每股派息", "税前每股现金分红金额", "DECIMAL(10,4)",
                 source=DataSource.BAOSTOCK, unit="元/股"),
        FieldDef("announcement_date", "公告日期", "分红方案公告日期", "DATE",
                 source=DataSource.BAOSTOCK),
    ]
)

# ---- financial_intermediate: 财务中间指标 ----
FINANCIAL_INTERMEDIATE = TableDef(
    table_name="financial_intermediate",
    display_name="财务中间指标",
    description="基于财务报表数据计算的中间指标，包括: 单季度拆分(Q结算)、TTM汇总、同比环比、杜邦分析、营运能力、现金流分析。是估值计算的输入。",
    primary_key=["stock_code", "report_date", "report_type"],
    refresh_frequency="quarterly",
    fields=[
        # ---- 基础字段(从financial_statements透传) ----
        FieldDef("stock_code", "股票代码", "sh/sz + 6位数字", "VARCHAR(10)",
                 nullable=False, source=DataSource.CALCULATED, category=DataCategory.DERIVED_FINANCIAL),
        FieldDef("report_date", "报告日期", "财务报告截止日期", "DATE",
                 nullable=False, source=DataSource.CALCULATED, category=DataCategory.DERIVED_FINANCIAL),
        FieldDef("report_type", "报告类型", "Q1/Q2/Q3/FY(年报)", "VARCHAR(20)",
                 nullable=False, source=DataSource.CALCULATED, category=DataCategory.DERIVED_FINANCIAL),
        FieldDef("eps", "每股收益", "透视自 financial_statements", "DECIMAL(10,4)",
                 source=DataSource.AKSHARE_SINA, unit="元/股"),
        FieldDef("bvps", "每股净资产", "归母权益 / 总股本", "DECIMAL(10,4)",
                 source=DataSource.CALCULATED, category=DataCategory.DERIVED_FINANCIAL,
                 calculation="equity_parent / total_shares", unit="元/股"),
        FieldDef("revenue_per_share", "每股营收", "营业总收入 / 总股本", "DECIMAL(10,4)",
                 source=DataSource.CALCULATED, category=DataCategory.DERIVED_FINANCIAL,
                 calculation="total_revenue / total_shares", unit="元/股"),
        FieldDef("net_profit", "归母净利润", "透视自 financial_statements", "DECIMAL(18,2)",
                 source=DataSource.AKSHARE_SINA, unit="元"),
        FieldDef("total_revenue", "营业总收入", "透视自 financial_statements", "DECIMAL(18,2)",
                 source=DataSource.AKSHARE_SINA, unit="元"),
        FieldDef("equity", "净资产", "总资产 - 总负债", "DECIMAL(18,2)",
                 source=DataSource.CALCULATED, category=DataCategory.DERIVED_FINANCIAL,
                 calculation="total_assets - total_liabilities", unit="元"),
        FieldDef("equity_parent", "归母权益", "透视自 financial_statements", "DECIMAL(18,2)",
                 source=DataSource.AKSHARE_SINA, unit="元"),
        FieldDef("total_assets", "总资产", "透视自 financial_statements", "DECIMAL(18,2)",
                 source=DataSource.AKSHARE_SINA, unit="元"),
        FieldDef("total_shares", "总股本", "来自 stock_capital(最新)", "DECIMAL(20,0)",
                 source=DataSource.BAOSTOCK, unit="股"),
        FieldDef("announcement_date", "公告日期", "透视自 financial_statements", "DATE",
                 source=DataSource.AKSHARE_SINA),
        FieldDef("operating_cost", "营业总成本", "透视自 financial_statements", "DECIMAL(18,2)",
                 source=DataSource.AKSHARE_SINA, unit="元"),
        FieldDef("net_profit_deducted", "扣非净利润", "透视自 financial_statements", "DECIMAL(18,2)",
                 source=DataSource.AKSHARE_EM, unit="元"),
        FieldDef("inventory", "存货", "透视自 financial_statements", "DECIMAL(18,2)",
                 source=DataSource.AKSHARE_SINA, unit="元"),
        FieldDef("accounts_receivable", "应收账款", "透视自 financial_statements", "DECIMAL(18,2)",
                 source=DataSource.AKSHARE_SINA, unit="元"),
        FieldDef("accounts_payable", "应付账款", "透视自 financial_statements", "DECIMAL(18,2)",
                 source=DataSource.AKSHARE_SINA, unit="元"),
        FieldDef("capex", "资本支出", "透视自 financial_statements", "DECIMAL(18,2)",
                 source=DataSource.AKSHARE_SINA, unit="元"),
        FieldDef("interest_expense", "利息支出", "透视自 financial_statements", "DECIMAL(18,2)",
                 source=DataSource.AKSHARE_EM, unit="元"),
        FieldDef("operating_cash_flow", "经营活动现金流", "透视自 financial_statements", "DECIMAL(18,2)",
                 source=DataSource.AKSHARE_SINA, unit="元"),

        # ---- 单季度拆分(Q结算) ----
        FieldDef("net_profit_q", "归母净利润(单季)", "单季度归母净利润(从累计值拆分)", "DECIMAL(18,2)",
                 source=DataSource.CALCULATED, category=DataCategory.DERIVED_FINANCIAL,
                 calculation="Q1单季=Q1累计; Q2单季=Q2累计-Q1; Q3单季=Q3累计-Q2; FY单季=FY-Q3", unit="元"),
        FieldDef("total_revenue_q", "营业总收入(单季)", "单季度营业总收入", "DECIMAL(18,2)",
                 source=DataSource.CALCULATED, category=DataCategory.DERIVED_FINANCIAL,
                 calculation="同净利润拆分逻辑", unit="元"),
        FieldDef("eps_q", "EPS(单季)", "单季度每股收益", "DECIMAL(10,4)",
                 source=DataSource.CALCULATED, category=DataCategory.DERIVED_FINANCIAL,
                 calculation="单季度拆分的EPS", unit="元/股"),
        FieldDef("operating_cost_q", "营业成本(单季)", "单季度营业总成本", "DECIMAL(18,2)",
                 source=DataSource.CALCULATED, category=DataCategory.DERIVED_FINANCIAL,
                 calculation="同净利润拆分逻辑", unit="元"),
        FieldDef("net_profit_deducted_q", "扣非净利润(单季)", "单季度扣非净利润", "DECIMAL(18,2)",
                 source=DataSource.CALCULATED, category=DataCategory.DERIVED_FINANCIAL,
                 calculation="同净利润拆分逻辑", unit="元"),
        FieldDef("operating_cash_flow_q", "经营现金流(单季)", "单季度经营活动现金流净额", "DECIMAL(18,2)",
                 source=DataSource.CALCULATED, category=DataCategory.DERIVED_FINANCIAL,
                 calculation="同净利润拆分逻辑", unit="元"),
        FieldDef("capex_q", "资本支出(单季)", "单季度资本支出", "DECIMAL(18,2)",
                 source=DataSource.CALCULATED, category=DataCategory.DERIVED_FINANCIAL,
                 calculation="同净利润拆分逻辑", unit="元"),

        # ---- TTM 汇总(滚动12个月) ----
        FieldDef("net_profit_ttm", "归母净利润(TTM)", "最近4个季度归母净利润之和", "DECIMAL(18,2)",
                 source=DataSource.CALCULATED, category=DataCategory.DERIVED_FINANCIAL,
                 calculation="SUM(最近4个报告期单季净利润)", unit="元"),
        FieldDef("total_revenue_ttm", "营业总收入(TTM)", "最近4个季度营业总收入之和", "DECIMAL(18,2)",
                 source=DataSource.CALCULATED, category=DataCategory.DERIVED_FINANCIAL,
                 calculation="SUM(最近4个报告期单季营收)", unit="元"),
        FieldDef("eps_ttm", "EPS(TTM)", "最近4个季度EPS之和", "DECIMAL(10,4)",
                 source=DataSource.CALCULATED, category=DataCategory.DERIVED_FINANCIAL,
                 calculation="SUM(最近4个报告期单季EPS)", unit="元/股"),
        FieldDef("operating_cost_ttm", "营业成本(TTM)", "最近4个季度营业总成本之和", "DECIMAL(18,2)",
                 source=DataSource.CALCULATED, category=DataCategory.DERIVED_FINANCIAL,
                 calculation="SUM(最近4个报告期单季)", unit="元"),
        FieldDef("net_profit_deducted_ttm", "扣非净利润(TTM)", "最近4个季度扣非净利润之和", "DECIMAL(18,2)",
                 source=DataSource.CALCULATED, category=DataCategory.DERIVED_FINANCIAL,
                 calculation="SUM(最近4个报告期单季)", unit="元"),
        FieldDef("operating_cash_flow_ttm", "经营现金流(TTM)", "最近4个季度经营现金流净额之和", "DECIMAL(18,2)",
                 source=DataSource.CALCULATED, category=DataCategory.DERIVED_FINANCIAL,
                 calculation="SUM(最近4个报告期单季)", unit="元"),
        FieldDef("capex_ttm", "资本支出(TTM)", "最近4个季度资本支出之和", "DECIMAL(18,2)",
                 source=DataSource.CALCULATED, category=DataCategory.DERIVED_FINANCIAL,
                 calculation="SUM(最近4个报告期单季)", unit="元"),
        FieldDef("interest_expense_ttm", "利息支出(TTM)", "最近4个季度利息支出之和", "DECIMAL(18,2)",
                 source=DataSource.CALCULATED, category=DataCategory.DERIVED_FINANCIAL,
                 calculation="SUM(最近4个报告期单季)", unit="元"),

        # ---- 平均值(用于比率计算) ----
        FieldDef("avg_equity_parent", "平均归母权益(年度)", "年初与年末归母权益平均值", "DECIMAL(18,2)",
                 source=DataSource.CALCULATED, category=DataCategory.DERIVED_FINANCIAL,
                 calculation="(期初 + 期末) / 2", unit="元"),
        FieldDef("avg_total_assets", "平均总资产(年度)", "年初与年末总资产平均值", "DECIMAL(18,2)",
                 source=DataSource.CALCULATED, category=DataCategory.DERIVED_FINANCIAL,
                 calculation="(期初 + 期末) / 2", unit="元"),
        FieldDef("avg_inventory", "平均存货(年度)", "年初与年末存货平均值", "DECIMAL(18,2)",
                 source=DataSource.CALCULATED, category=DataCategory.DERIVED_FINANCIAL,
                 calculation="(期初 + 期末) / 2", unit="元"),
        FieldDef("avg_accounts_receivable", "平均应收账款(年度)", "年初与年末应收账款平均值", "DECIMAL(18,2)",
                 source=DataSource.CALCULATED, category=DataCategory.DERIVED_FINANCIAL,
                 calculation="(期初 + 期末) / 2", unit="元"),
        FieldDef("avg_accounts_payable", "平均应付账款(年度)", "年初与年末应付账款平均值", "DECIMAL(18,2)",
                 source=DataSource.CALCULATED, category=DataCategory.DERIVED_FINANCIAL,
                 calculation="(期初 + 期末) / 2", unit="元"),
        FieldDef("avg_equity_parent_ttm", "平均归母权益(TTM)", "4个季度前与当前归母权益平均值", "DECIMAL(18,2)",
                 source=DataSource.CALCULATED, category=DataCategory.DERIVED_FINANCIAL,
                 calculation="(4Q前 + 当前) / 2", unit="元"),
        FieldDef("avg_total_assets_ttm", "平均总资产(TTM)", "4个季度前与当前总资产平均值", "DECIMAL(18,2)",
                 source=DataSource.CALCULATED, category=DataCategory.DERIVED_FINANCIAL,
                 calculation="(4Q前 + 当前) / 2", unit="元"),
        FieldDef("avg_inventory_ttm", "平均存货(TTM)", "4个季度前与当前存货平均值", "DECIMAL(18,2)",
                 source=DataSource.CALCULATED, category=DataCategory.DERIVED_FINANCIAL,
                 calculation="(4Q前 + 当前) / 2", unit="元"),
        FieldDef("avg_accounts_receivable_ttm", "平均应收账款(TTM)", "4个季度前与当前应收账款平均值", "DECIMAL(18,2)",
                 source=DataSource.CALCULATED, category=DataCategory.DERIVED_FINANCIAL,
                 calculation="(4Q前 + 当前) / 2", unit="元"),
        FieldDef("avg_accounts_payable_ttm", "平均应付账款(TTM)", "4个季度前与当前应付账款平均值", "DECIMAL(18,2)",
                 source=DataSource.CALCULATED, category=DataCategory.DERIVED_FINANCIAL,
                 calculation="(4Q前 + 当前) / 2", unit="元"),

        # ---- 盈利能力(年度) ----
        FieldDef("roe_annual", "ROE(年度)", "年度净资产收益率", "DECIMAL(10,4)",
                 source=DataSource.CALCULATED, category=DataCategory.DERIVED_FINANCIAL,
                 calculation="net_profit / avg_equity_parent * 100", unit="%"),
        FieldDef("roa_annual", "ROA(年度)", "年度总资产收益率", "DECIMAL(10,4)",
                 source=DataSource.CALCULATED, category=DataCategory.DERIVED_FINANCIAL,
                 calculation="net_profit / avg_total_assets * 100", unit="%"),
        FieldDef("gross_margin_annual", "毛利率(年度)", "年度毛利率", "DECIMAL(10,4)",
                 source=DataSource.CALCULATED, category=DataCategory.DERIVED_FINANCIAL,
                 calculation="(total_revenue - operating_cost) / total_revenue * 100", unit="%"),
        FieldDef("net_margin_parent_annual", "净利率(年度)", "年度归母净利率", "DECIMAL(10,4)",
                 source=DataSource.CALCULATED, category=DataCategory.DERIVED_FINANCIAL,
                 calculation="net_profit / total_revenue * 100", unit="%"),
        FieldDef("net_margin_deducted_annual", "扣非净利率(年度)", "年度扣非净利率", "DECIMAL(10,4)",
                 source=DataSource.CALCULATED, category=DataCategory.DERIVED_FINANCIAL,
                 calculation="net_profit_deducted / total_revenue * 100", unit="%"),

        # ---- 盈利能力(TTM) ----
        FieldDef("roe_ttm", "ROE(TTM)", "滚动12个月净资产收益率", "DECIMAL(10,4)",
                 source=DataSource.CALCULATED, category=DataCategory.DERIVED_FINANCIAL,
                 calculation="net_profit_ttm / avg_equity_parent_ttm * 100", unit="%"),
        FieldDef("roa_ttm", "ROA(TTM)", "滚动12个月总资产收益率", "DECIMAL(10,4)",
                 source=DataSource.CALCULATED, category=DataCategory.DERIVED_FINANCIAL,
                 calculation="net_profit_ttm / avg_total_assets_ttm * 100", unit="%"),
        FieldDef("gross_margin_ttm", "毛利率(TTM)", "滚动12个月毛利率", "DECIMAL(10,4)",
                 source=DataSource.CALCULATED, category=DataCategory.DERIVED_FINANCIAL,
                 calculation="(total_revenue_ttm - operating_cost_ttm) / total_revenue_ttm * 100", unit="%"),
        FieldDef("net_margin_parent_ttm", "净利率(TTM)", "滚动12个月归母净利率", "DECIMAL(10,4)",
                 source=DataSource.CALCULATED, category=DataCategory.DERIVED_FINANCIAL,
                 calculation="net_profit_ttm / total_revenue_ttm * 100", unit="%"),
        FieldDef("net_margin_deducted_ttm", "扣非净利率(TTM)", "滚动12个月扣非净利率", "DECIMAL(10,4)",
                 source=DataSource.CALCULATED, category=DataCategory.DERIVED_FINANCIAL,
                 calculation="net_profit_deducted_ttm / total_revenue_ttm * 100", unit="%"),

        # ---- 成长性 ----
        FieldDef("revenue_yoy_annual", "营收同比(年度)", "年度营收同比增速", "DECIMAL(10,4)",
                 source=DataSource.CALCULATED, category=DataCategory.DERIVED_FINANCIAL,
                 calculation="(revenue_current - revenue_prev) / revenue_prev * 100", unit="%"),
        FieldDef("net_profit_yoy_annual", "净利润同比(年度)", "年度净利润同比增速", "DECIMAL(10,4)",
                 source=DataSource.CALCULATED, category=DataCategory.DERIVED_FINANCIAL,
                 calculation="(np_current - np_prev) / np_prev * 100", unit="%"),
        FieldDef("revenue_yoy_qoq", "营收同比(单季)", "单季度营收同比增速", "DECIMAL(10,4)",
                 source=DataSource.CALCULATED, category=DataCategory.DERIVED_FINANCIAL,
                 calculation="(rev_q_current - rev_q_prev_year) / rev_q_prev_year * 100", unit="%"),
        FieldDef("net_profit_yoy_qoq", "净利润同比(单季)", "单季度净利润同比增速", "DECIMAL(10,4)",
                 source=DataSource.CALCULATED, category=DataCategory.DERIVED_FINANCIAL,
                 calculation="(np_q_current - np_q_prev_year) / np_q_prev_year * 100", unit="%"),
        FieldDef("revenue_yoy_ttm", "营收同比(TTM)", "TTM营收同比增速", "DECIMAL(10,4)",
                 source=DataSource.CALCULATED, category=DataCategory.DERIVED_FINANCIAL,
                 calculation="(rev_ttm - rev_ttm_prev) / rev_ttm_prev * 100", unit="%"),
        FieldDef("net_profit_yoy_ttm", "净利润同比(TTM)", "TTM净利润同比增速", "DECIMAL(10,4)",
                 source=DataSource.CALCULATED, category=DataCategory.DERIVED_FINANCIAL,
                 calculation="(np_ttm - np_ttm_prev) / np_ttm_prev * 100", unit="%"),
        FieldDef("revenue_cagr_3y", "营收3年CAGR", "3年营收复合增长率", "DECIMAL(10,4)",
                 source=DataSource.CALCULATED, category=DataCategory.DERIVED_FINANCIAL,
                 calculation="(revenue/revenue_3y)^(1/3)-1 * 100", unit="%"),
        FieldDef("net_profit_cagr_3y", "净利润3年CAGR", "3年净利润复合增长率", "DECIMAL(10,4)",
                 source=DataSource.CALCULATED, category=DataCategory.DERIVED_FINANCIAL,
                 calculation="(np/np_3y)^(1/3)-1 * 100", unit="%"),
        FieldDef("net_profit_deducted_cagr_3y", "扣非净利润3年CAGR", "3年扣非净利润复合增长率", "DECIMAL(10,4)",
                 source=DataSource.CALCULATED, category=DataCategory.DERIVED_FINANCIAL,
                 calculation="(npd/npd_3y)^(1/3)-1 * 100", unit="%"),

        # ---- 杜邦分析(年度) ----
        FieldDef("dupont_net_margin_annual", "杜邦净利率(年度)", "净利率 = 净利润/营收", "DECIMAL(10,4)",
                 source=DataSource.CALCULATED, category=DataCategory.DERIVED_FINANCIAL,
                 calculation="net_profit / total_revenue * 100", unit="%"),
        FieldDef("dupont_asset_turnover_annual", "杜邦资产周转率(年度)", "资产周转率 = 营收/平均总资产", "DECIMAL(10,4)",
                 source=DataSource.CALCULATED, category=DataCategory.DERIVED_FINANCIAL,
                 calculation="total_revenue / avg_total_assets", unit="次"),
        FieldDef("dupont_equity_multiplier_annual", "杜邦权益乘数(年度)", "权益乘数 = 总资产/权益", "DECIMAL(10,4)",
                 source=DataSource.CALCULATED, category=DataCategory.DERIVED_FINANCIAL,
                 calculation="total_assets / equity_parent", unit="倍"),

        # ---- 杜邦分析(TTM) ----
        FieldDef("dupont_net_margin_ttm", "杜邦净利率(TTM)", "TTM净利率", "DECIMAL(10,4)",
                 source=DataSource.CALCULATED, category=DataCategory.DERIVED_FINANCIAL,
                 calculation="net_profit_ttm / total_revenue_ttm * 100", unit="%"),
        FieldDef("dupont_asset_turnover_ttm", "杜邦资产周转率(TTM)", "TTM资产周转率", "DECIMAL(10,4)",
                 source=DataSource.CALCULATED, category=DataCategory.DERIVED_FINANCIAL,
                 calculation="total_revenue_ttm / avg_total_assets_ttm", unit="次"),
        FieldDef("dupont_equity_multiplier_ttm", "杜邦权益乘数(TTM)", "TTM权益乘数", "DECIMAL(10,4)",
                 source=DataSource.CALCULATED, category=DataCategory.DERIVED_FINANCIAL,
                 calculation="total_assets / equity_parent", unit="倍"),

        # ---- 营运能力(年度) ----
        FieldDef("inventory_turnover_annual", "存货周转率(年度)", "营业成本 / 平均存货", "DECIMAL(18,4)",
                 source=DataSource.CALCULATED, category=DataCategory.DERIVED_FINANCIAL,
                 calculation="operating_cost / avg_inventory", unit="次"),
        FieldDef("inventory_days_annual", "存货周转天数(年度)", "365 / 存货周转率", "DECIMAL(18,4)",
                 source=DataSource.CALCULATED, category=DataCategory.DERIVED_FINANCIAL,
                 calculation="365 / inventory_turnover_annual", unit="天"),
        FieldDef("accounts_receivable_turnover_annual", "应收账款周转率(年度)", "营收 / 平均应收账款", "DECIMAL(18,4)",
                 source=DataSource.CALCULATED, category=DataCategory.DERIVED_FINANCIAL,
                 calculation="total_revenue / avg_accounts_receivable", unit="次"),
        FieldDef("accounts_receivable_days_annual", "应收账款周转天数(年度)", "365 / 应收账款周转率", "DECIMAL(18,4)",
                 source=DataSource.CALCULATED, category=DataCategory.DERIVED_FINANCIAL,
                 calculation="365 / accounts_receivable_turnover_annual", unit="天"),
        FieldDef("accounts_payable_turnover_annual", "应付账款周转率(年度)", "营业成本 / 平均应付账款", "DECIMAL(18,4)",
                 source=DataSource.CALCULATED, category=DataCategory.DERIVED_FINANCIAL,
                 calculation="operating_cost / avg_accounts_payable", unit="次"),
        FieldDef("accounts_payable_days_annual", "应付账款周转天数(年度)", "365 / 应付账款周转率", "DECIMAL(18,4)",
                 source=DataSource.CALCULATED, category=DataCategory.DERIVED_FINANCIAL,
                 calculation="365 / accounts_payable_turnover_annual", unit="天"),
        FieldDef("cash_cycle_annual", "现金周期(年度)", "存货天数 + 应收天数 - 应付天数", "DECIMAL(18,4)",
                 source=DataSource.CALCULATED, category=DataCategory.DERIVED_FINANCIAL,
                 calculation="inv_days + ar_days - ap_days", unit="天"),

        # ---- 营运能力(TTM) ----
        FieldDef("inventory_turnover_ttm", "存货周转率(TTM)", "TTM营业成本 / TTM平均存货", "DECIMAL(18,4)",
                 source=DataSource.CALCULATED, category=DataCategory.DERIVED_FINANCIAL,
                 calculation="operating_cost_ttm / avg_inventory_ttm", unit="次"),
        FieldDef("inventory_days_ttm", "存货周转天数(TTM)", "365 / TTM存货周转率", "DECIMAL(18,4)",
                 source=DataSource.CALCULATED, category=DataCategory.DERIVED_FINANCIAL,
                 calculation="365 / inventory_turnover_ttm", unit="天"),
        FieldDef("accounts_receivable_turnover_ttm", "应收账款周转率(TTM)", "TTM营收 / TTM平均应收账款", "DECIMAL(18,4)",
                 source=DataSource.CALCULATED, category=DataCategory.DERIVED_FINANCIAL,
                 calculation="total_revenue_ttm / avg_accounts_receivable_ttm", unit="次"),
        FieldDef("accounts_receivable_days_ttm", "应收账款周转天数(TTM)", "365 / TTM应收账款周转率", "DECIMAL(18,4)",
                 source=DataSource.CALCULATED, category=DataCategory.DERIVED_FINANCIAL,
                 calculation="365 / accounts_receivable_turnover_ttm", unit="天"),
        FieldDef("accounts_payable_turnover_ttm", "应付账款周转率(TTM)", "TTM营业成本 / TTM平均应付账款", "DECIMAL(18,4)",
                 source=DataSource.CALCULATED, category=DataCategory.DERIVED_FINANCIAL,
                 calculation="operating_cost_ttm / avg_accounts_payable_ttm", unit="次"),
        FieldDef("accounts_payable_days_ttm", "应付账款周转天数(TTM)", "365 / TTM应付账款周转率", "DECIMAL(18,4)",
                 source=DataSource.CALCULATED, category=DataCategory.DERIVED_FINANCIAL,
                 calculation="365 / accounts_payable_turnover_ttm", unit="天"),
        FieldDef("cash_cycle_ttm", "现金周期(TTM)", "TTM存货天数 + 应收天数 - 应付天数", "DECIMAL(18,4)",
                 source=DataSource.CALCULATED, category=DataCategory.DERIVED_FINANCIAL,
                 calculation="inv_days_ttm + ar_days_ttm - ap_days_ttm", unit="天"),

        # ---- 现金流分析(TTM) ----
        FieldDef("cash_profit_coverage_ttm", "现金流利润覆盖(TTM)", "经营现金流 / 净利润(TTM)", "DECIMAL(18,4)",
                 source=DataSource.CALCULATED, category=DataCategory.DERIVED_FINANCIAL,
                 calculation="operating_cash_flow_ttm / net_profit_ttm", unit="倍"),
        FieldDef("fcf_ttm", "自由现金流(TTM)", "经营现金流 - 资本支出(TTM)", "DECIMAL(18,2)",
                 source=DataSource.CALCULATED, category=DataCategory.DERIVED_FINANCIAL,
                 calculation="operating_cash_flow_ttm - capex_ttm", unit="元"),
        FieldDef("fcf_profit_coverage_ttm", "自由现金流利润覆盖(TTM)", "自由现金流 / 净利润(TTM)", "DECIMAL(18,4)",
                 source=DataSource.CALCULATED, category=DataCategory.DERIVED_FINANCIAL,
                 calculation="fcf_ttm / net_profit_ttm", unit="倍"),
        FieldDef("cash_interest_coverage_ttm", "现金流利息覆盖(TTM)", "经营现金流 / 利息支出(TTM)", "DECIMAL(18,4)",
                 source=DataSource.CALCULATED, category=DataCategory.DERIVED_FINANCIAL,
                 calculation="operating_cash_flow_ttm / interest_expense_ttm", unit="倍"),
        FieldDef("current_ratio", "流动比率", "流动资产 / 流动负债", "DECIMAL(10,4)",
                 source=DataSource.CALCULATED, category=DataCategory.DERIVED_FINANCIAL,
                 calculation="current_assets / current_liabilities", unit="倍"),
        FieldDef("quick_ratio", "速动比率", "(流动资产 - 存货) / 流动负债", "DECIMAL(10,4)",
                 source=DataSource.CALCULATED, category=DataCategory.DERIVED_FINANCIAL,
                 calculation="(current_assets - inventory) / current_liabilities", unit="倍"),
    ]
)

# ---- northbound_flow: 北向资金 ----
NORTHBOUND_FLOW = TableDef(
    table_name="northbound_flow",
    display_name="北向资金",
    description="沪深港通北向资金每日净流入及持仓数据。含累计计算(5/10/30日)。主源AKShare(stock_hsgt_individual_em),数据停更至2024年8月;回退源Tushare Pro(需积分权限)。",
    primary_key=["stock_code", "trade_date"],
    refresh_frequency="daily",
    fields=[
        FieldDef("stock_code", "股票代码", "sh/sz + 6位数字", "VARCHAR(10)",
                 nullable=False, source=DataSource.AKSHARE),
        FieldDef("trade_date", "交易日期", "YYYY-MM-DD", "DATE",
                 nullable=False, source=DataSource.AKSHARE),
        FieldDef("net_inflow", "当日净流入", "北向资金当日净买入金额", "DECIMAL(18,2)",
                 source=DataSource.AKSHARE, unit="元"),
        FieldDef("holding_shares", "持仓股数", "北向资金累计持仓股数", "DECIMAL(20,0)",
                 source=DataSource.AKSHARE, unit="股"),
        FieldDef("holding_value", "持仓市值", "北向资金累计持仓市值", "DECIMAL(18,2)",
                 source=DataSource.AKSHARE, unit="元"),
        FieldDef("holding_ratio", "持仓比例", "持仓股数 / 总股本", "DECIMAL(10,4)",
                 source=DataSource.AKSHARE, unit="比率"),
        FieldDef("inflow_5d", "5日净流入", "近5日北向资金累计净流入", "DECIMAL(18,2)",
                 source=DataSource.CALCULATED, category=DataCategory.DERIVED_SIMPLE,
                 calculation="net_inflow.rolling(5).sum()", unit="元"),
        FieldDef("inflow_10d", "10日净流入", "近10日北向资金累计净流入", "DECIMAL(18,2)",
                 source=DataSource.CALCULATED, category=DataCategory.DERIVED_SIMPLE,
                 calculation="net_inflow.rolling(10).sum()", unit="元"),
        FieldDef("inflow_30d", "30日净流入", "近30日北向资金累计净流入", "DECIMAL(18,2)",
                 source=DataSource.CALCULATED, category=DataCategory.DERIVED_SIMPLE,
                 calculation="net_inflow.rolling(30).sum()", unit="元"),
    ]
)

# ---- margin_trading: 融资融券 ----
MARGIN_TRADING = TableDef(
    table_name="margin_trading",
    display_name="融资融券",
    description="每只股票每日融资融券余额及变化。数据源AKShare。",
    primary_key=["stock_code", "trade_date"],
    refresh_frequency="daily",
    fields=[
        FieldDef("stock_code", "股票代码", "sh/sz + 6位数字", "VARCHAR(10)",
                 nullable=False, source=DataSource.AKSHARE),
        FieldDef("trade_date", "交易日期", "YYYY-MM-DD", "DATE",
                 nullable=False, source=DataSource.AKSHARE),
        FieldDef("rz_balance", "融资余额", "融资余额(融资买入-融资偿还)", "DECIMAL(18,2)",
                 source=DataSource.AKSHARE, unit="元"),
        FieldDef("rz_change", "融资变化额", "当日融资净买入额", "DECIMAL(18,2)",
                 source=DataSource.AKSHARE, unit="元"),
        FieldDef("rz_change_pct", "融资变化率", "融资变化额 / 前日融资余额 × 100", "DECIMAL(10,4)",
                 source=DataSource.AKSHARE, unit="%"),
        FieldDef("rq_balance", "融券余额", "融券余量 × 收盘价", "DECIMAL(18,2)",
                 source=DataSource.AKSHARE, unit="元"),
        FieldDef("rq_change", "融券变化额", "当日融券净卖出额", "DECIMAL(18,2)",
                 source=DataSource.AKSHARE, unit="元"),
        FieldDef("rq_change_pct", "融券变化率", "融券变化额 / 前日融券余额 × 100", "DECIMAL(10,4)",
                 source=DataSource.AKSHARE, unit="%"),
        FieldDef("total_balance", "两融余额", "融资余额 + 融券余额", "DECIMAL(18,2)",
                 source=DataSource.CALCULATED, category=DataCategory.DERIVED_SIMPLE,
                 calculation="rz_balance + rq_balance", unit="元"),
        FieldDef("total_change", "两融变化额", "融资变化额 + 融券变化额", "DECIMAL(18,2)",
                 source=DataSource.CALCULATED, category=DataCategory.DERIVED_SIMPLE,
                 calculation="rz_change + rq_change", unit="元"),
        FieldDef("total_change_pct", "两融变化率", "两融变化额 / 前日总余额 × 100", "DECIMAL(10,4)",
                 source=DataSource.CALCULATED, category=DataCategory.DERIVED_SIMPLE,
                 calculation="total_change / 前日total_balance * 100", unit="%"),
    ]
)

# ---- dragon_tiger: 龙虎榜 ----
DRAGON_TIGER = TableDef(
    table_name="dragon_tiger",
    display_name="龙虎榜",
    description="个股龙虎榜上榜记录(每日涨跌幅/换手率/振幅等异常个股)。数据源AKShare。",
    primary_key=["stock_code", "trade_date", "list_type"],
    refresh_frequency="daily",
    fields=[
        FieldDef("id", "记录ID", "自增主键", "INTEGER", nullable=False,
                 source=DataSource.INTERNAL, category=DataCategory.METADATA),
        FieldDef("stock_code", "股票代码", "sh/sz + 6位数字", "VARCHAR(10)",
                 nullable=False, source=DataSource.AKSHARE),
        FieldDef("trade_date", "上榜日期", "龙虎榜上榜日期", "DATE",
                 nullable=False, source=DataSource.AKSHARE),
        FieldDef("list_type", "上榜类型", "如: 日涨幅偏离值达7%/日换手率达20%等", "VARCHAR(50)",
                 source=DataSource.AKSHARE),
        FieldDef("reason", "上榜原因", "上榜具体原因描述", "VARCHAR(255)",
                 source=DataSource.AKSHARE),
        FieldDef("buy_amount", "买入金额", "龙虎榜买入总金额", "DECIMAL(18,2)",
                 source=DataSource.AKSHARE, unit="元"),
        FieldDef("sell_amount", "卖出金额", "龙虎榜卖出总金额", "DECIMAL(18,2)",
                 source=DataSource.AKSHARE, unit="元"),
        FieldDef("net_amount", "净买入金额", "买入金额 - 卖出金额", "DECIMAL(18,2)",
                 source=DataSource.CALCULATED, category=DataCategory.DERIVED_SIMPLE,
                 calculation="buy_amount - sell_amount", unit="元"),
        FieldDef("institution_buy_ratio", "机构买入占比", "机构专用席位买入占比", "DECIMAL(10,4)",
                 source=DataSource.CALCULATED, category=DataCategory.DERIVED_SIMPLE,
                 calculation="机构买入 / 总买入 * 100", unit="%"),
        FieldDef("institution_sell_ratio", "机构卖入占比", "机构专用席位卖出占比", "DECIMAL(10,4)",
                 source=DataSource.CALCULATED, category=DataCategory.DERIVED_SIMPLE,
                 calculation="机构卖出 / 总卖出 * 100", unit="%"),
        FieldDef("institution_net_ratio", "机构净买卖占比", "机构净买卖占总成交比例", "DECIMAL(10,4)",
                 source=DataSource.CALCULATED, category=DataCategory.DERIVED_SIMPLE,
                 calculation="机构净买卖 / 总成交 * 100", unit="%"),
    ]
)

# ---- dragon_tiger_detail: 龙虎榜明细 ----
DRAGON_TIGER_DETAIL = TableDef(
    table_name="dragon_tiger_detail",
    display_name="龙虎榜明细",
    description="龙虎榜各营业部/机构买入卖出明细。与dragon_tiger通过dragon_tiger_id关联。数据源AKShare。",
    primary_key=["id"],
    refresh_frequency="daily",
    fields=[
        FieldDef("id", "明细ID", "自增主键", "INTEGER", nullable=False,
                 source=DataSource.INTERNAL, category=DataCategory.METADATA),
        FieldDef("dragon_tiger_id", "龙虎榜ID", "关联 dragon_tiger.id", "INTEGER", nullable=False,
                 source=DataSource.AKSHARE),
        FieldDef("seat_name", "席位名称", "券商营业部或机构名称", "VARCHAR(255)",
                 source=DataSource.AKSHARE),
        FieldDef("seat_type", "席位类型", "机构专用/券商营业部/游资等", "VARCHAR(50)",
                 source=DataSource.AKSHARE),
        FieldDef("buy_amount", "买入金额", "该席位买入金额", "DECIMAL(18,2)",
                 source=DataSource.AKSHARE, unit="元"),
        FieldDef("sell_amount", "卖出金额", "该席位卖出金额", "DECIMAL(18,2)",
                 source=DataSource.AKSHARE, unit="元"),
        FieldDef("net_amount", "净买卖金额", "买入 - 卖出", "DECIMAL(18,2)",
                 source=DataSource.CALCULATED, category=DataCategory.DERIVED_SIMPLE,
                 calculation="buy_amount - sell_amount", unit="元"),
        FieldDef("rank", "排名", "营业部买入排名", "INTEGER",
                 source=DataSource.AKSHARE),
    ]
)

# ---- stock_industry: 行业分类 ----
STOCK_INDUSTRY = TableDef(
    table_name="stock_industry",
    display_name="行业分类",
    description="股票行业分类信息。主源BaoStock(证监会行业分类)，备源AKShare/巨潮。注意: 当前只存最新分类，不含历史快照。",
    primary_key=["stock_code"],
    refresh_frequency="quarterly",
    fields=[
        FieldDef("stock_code", "股票代码", "sh/sz + 6位数字", "VARCHAR(10)",
                 nullable=False, source=DataSource.BAOSTOCK),
        FieldDef("industry_name", "行业名称", "如: 白酒/新能源/医药等", "VARCHAR(100)",
                 source=DataSource.BAOSTOCK),
        FieldDef("industry_level", "行业分类层级", "证监会行业分类代码/级别", "VARCHAR(20)",
                 source=DataSource.BAOSTOCK),
        FieldDef("source", "数据来源", "BaoStock / CNInfo(巨潮)", "VARCHAR(50)",
                 source=DataSource.BAOSTOCK),
        FieldDef("update_date", "更新日期", "行业分类更新时间", "DATE", nullable=False,
                 source=DataSource.BAOSTOCK),
    ]
)

# ---- column_metadata: 字段元数据 ----
COLUMN_METADATA = TableDef(
    table_name="column_metadata",
    display_name="字段元数据",
    description="数据库中所有字段的中文描述和单位信息。系统内部元数据表，供数据消费方查阅。",
    primary_key=["table_name", "column_name"],
    refresh_frequency="on_demand",
    fields=[
        FieldDef("table_name", "表名", "所属数据库表名", "VARCHAR(50)", nullable=False,
                 source=DataSource.INTERNAL, category=DataCategory.METADATA),
        FieldDef("column_name", "列名", "数据库列名", "VARCHAR(50)", nullable=False,
                 source=DataSource.INTERNAL, category=DataCategory.METADATA),
        FieldDef("description", "字段描述", "字段业务含义说明", "VARCHAR(255)",
                 source=DataSource.INTERNAL, category=DataCategory.METADATA),
        FieldDef("unit", "单位", "字段数值单位", "VARCHAR(20)",
                 source=DataSource.INTERNAL, category=DataCategory.METADATA),
    ]
)


# =============================================================================
# =========================== 汇总导出 ========================================
# =============================================================================

# 所有表定义列表
ALL_TABLES: list[TableDef] = [
    STOCK_DAILY,
    FINANCIAL_STATEMENTS,
    ANNOUNCEMENTS,
    UPDATE_LOG,
    TECHNICAL_INDICATORS,
    VALUATION_INDICATORS,
    STOCK_CAPITAL,
    DIVIDENDS,
    FINANCIAL_INTERMEDIATE,
    NORTHBOUND_FLOW,
    MARGIN_TRADING,
    DRAGON_TIGER,
    DRAGON_TIGER_DETAIL,
    STOCK_INDUSTRY,
    COLUMN_METADATA,
]

# 按数据来源分组的索引: source -> [(table, field), ...]
SOURCE_INDEX: dict[DataSource, list[tuple[str, str, str]]] = {}
for table in ALL_TABLES:
    for field in table.fields:
        source = field.source
        if source not in SOURCE_INDEX:
            SOURCE_INDEX[source] = []
        SOURCE_INDEX[source].append((table.table_name, field.column_name, field.display_name))

# 按表名快速查找
TABLE_MAP: dict[str, TableDef] = {t.table_name: t for t in ALL_TABLES}

# 所有原始采集字段(非计算派生)
RAW_FIELDS = [
    (t.table_name, f.column_name, f.display_name, f.source.value)
    for t in ALL_TABLES
    for f in t.fields
    if f.category in (DataCategory.RAW, DataCategory.METADATA)
]

# 所有派生计算字段
DERIVED_FIELDS = [
    (t.table_name, f.column_name, f.display_name, f.calculation)
    for t in ALL_TABLES
    for f in t.fields
    if f.category not in (DataCategory.RAW, DataCategory.METADATA)
]