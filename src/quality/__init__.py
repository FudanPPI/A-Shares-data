"""
数据质量监控模块

检查维度:
  - freshness:    数据新鲜度(最新日期距今天数)
  - completeness: 数据完整性(行数单调性/空表检测)
  - null_ratio:   字段空值率
  - range:        数值字段合法范围检查

用法:
    from src.quality import QualityChecker
    checker = QualityChecker("data/stock_data.duckdb")
    report = checker.run_all()
    print(f"质量评分: {report['score']}%")
"""

from .checker import QualityChecker