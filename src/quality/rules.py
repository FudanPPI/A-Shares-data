"""
质量检查规则定义

每条规则包含:
  - rule_id:      规则唯一标识
  - description:  规则描述(中文)
  - severity:     严重程度: error(必须修复) / warning(建议修复) / info(参考)
  - check_sql:    DuckDB 查询,返回违规记录
"""
from dataclasses import dataclass


@dataclass
class QualityRule:
    rule_id: str
    description: str
    severity: str  # "error" / "warning" / "info"
    check_sql: str  # DuckDB 查询,违规行数 > 0 即告警


RULES: list[QualityRule] = [
    # ==================== 新鲜度检查 ====================

    QualityRule(
        rule_id="freshness_daily",
        description="日线行情最新日期距今天不应超过2个自然日",
        severity="error",
        check_sql="""
            SELECT stock_code,
                   MAX(trade_date) AS latest,
                   DATEDIFF('day', MAX(trade_date), CURRENT_DATE) AS days_behind
            FROM stock_daily
            GROUP BY stock_code
            HAVING DATEDIFF('day', MAX(trade_date), CURRENT_DATE) > 2
        """,
    ),
    QualityRule(
        rule_id="freshness_northbound",
        description="北向资金最新日期距今天不应超过90个自然日",
        severity="warning",
        check_sql="""
            SELECT stock_code,
                   MAX(trade_date) AS latest,
                   DATEDIFF('day', MAX(trade_date), CURRENT_DATE) AS days_behind
            FROM northbound_flow
            GROUP BY stock_code
            HAVING DATEDIFF('day', MAX(trade_date), CURRENT_DATE) > 90
        """,
    ),
    QualityRule(
        rule_id="freshness_financial",
        description="财务报表最新报告期距今不应超过6个月",
        severity="warning",
        check_sql="""
            SELECT stock_code,
                   MAX(report_date) AS latest,
                   DATEDIFF('day', MAX(report_date), CURRENT_DATE) AS days_behind
            FROM financial_statements
            GROUP BY stock_code
            HAVING DATEDIFF('day', MAX(report_date), CURRENT_DATE) > 183
        """,
    ),

    # ==================== 完整性检查 ====================

    QualityRule(
        rule_id="completeness_dragon",
        description="龙虎榜表行数不应为零",
        severity="info",
        check_sql="""
            SELECT 'dragon_tiger' AS table_name, COUNT(*) AS row_count
            FROM dragon_tiger
            HAVING COUNT(*) = 0
        """,
    ),
    QualityRule(
        rule_id="completeness_stock_capital",
        description="每只股票至少应有1条股本数据",
        severity="warning",
        check_sql="""
            SELECT d.stock_code
            FROM (SELECT DISTINCT stock_code FROM stock_daily) d
            LEFT JOIN (SELECT DISTINCT stock_code FROM stock_capital) c
              ON d.stock_code = c.stock_code
            WHERE c.stock_code IS NULL
        """,
    ),
    QualityRule(
        rule_id="completeness_valuation",
        description="日线表与估值指标表的股票应一一对应",
        severity="warning",
        check_sql="""
            SELECT d.stock_code
            FROM (SELECT DISTINCT stock_code FROM stock_daily) d
            LEFT JOIN (SELECT DISTINCT stock_code FROM valuation_indicators) v
              ON d.stock_code = v.stock_code
            WHERE v.stock_code IS NULL
        """,
    ),

    # ==================== 取值范围检查 ====================

    QualityRule(
        rule_id="range_change_pct",
        description="近30日涨跌幅应在-21%~+21%范围内",
        severity="warning",
        check_sql="""
            SELECT stock_code, trade_date, change_pct
            FROM stock_daily
            WHERE trade_date >= CURRENT_DATE - INTERVAL 30 DAY
              AND (change_pct > 21 OR change_pct < -21)
        """,
    ),
    QualityRule(
        rule_id="range_pe_ttm",
        description="近30日PE_TTM应在0~500范围内(负值/极端值需关注)",
        severity="info",
        check_sql="""
            SELECT stock_code, trade_date, pe_ttm
            FROM valuation_indicators
            WHERE trade_date >= CURRENT_DATE - INTERVAL 30 DAY
              AND pe_ttm IS NOT NULL
              AND (pe_ttm < 0 OR pe_ttm > 500)
        """,
    ),
    QualityRule(
        rule_id="range_volume",
        description="成交量不应为负数或零",
        severity="error",
        check_sql="""
            SELECT stock_code, trade_date, volume
            FROM stock_daily
            WHERE trade_date >= CURRENT_DATE - INTERVAL 30 DAY
              AND volume <= 0
        """,
    ),

    # ==================== 空值率检查 ====================

    QualityRule(
        rule_id="null_turnover",
        description="换手率字段空值率不应超过50%",
        severity="warning",
        check_sql="""
            SELECT stock_code,
                   COUNT(*) AS total,
                   SUM(CASE WHEN turnover IS NULL THEN 1 ELSE 0 END) AS nulls,
                   ROUND(SUM(CASE WHEN turnover IS NULL THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) AS null_pct
            FROM stock_daily
            GROUP BY stock_code
            HAVING SUM(CASE WHEN turnover IS NULL THEN 1 ELSE 0 END) * 100.0 / COUNT(*) > 50
        """,
    ),
    QualityRule(
        rule_id="null_adjust_factor",
        description="复权因子不应为空",
        severity="error",
        check_sql="""
            SELECT stock_code, COUNT(*) AS null_count
            FROM stock_daily
            WHERE adjust_factor IS NULL
            GROUP BY stock_code
        """,
    ),
]