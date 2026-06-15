"""
质量检查执行器

功能:
  - 按规则逐一执行检查,生成汇总报告
  - 将报告持久化到 quality_report 表
  - 支持获取最近一次报告
"""
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import duckdb

from .rules import RULES

logger = logging.getLogger(__name__)


class QualityChecker:
    """数据质量检查器"""

    def __init__(self, db_path: str):
        """
        Args:
            db_path: DuckDB 数据库文件路径
        """
        self.db_path = db_path

    def run_all(self) -> dict[str, Any]:
        """
        执行所有质量检查规则,返回汇总报告

        Returns:
            {
                "check_time": "2025-...",
                "total_rules": 12,
                "passed": 10,
                "failed": 1,
                "errors": 1,
                "score": 83.3,
                "results": [...]
            }
        """
        conn = duckdb.connect(self.db_path, read_only=True)
        try:
            results = self._execute_rules(conn)

            report: dict[str, Any] = {
                "check_time": datetime.now().isoformat(timespec="seconds"),
                "total_rules": len(RULES),
                "passed": sum(1 for r in results if r.get("status") == "pass"),
                "failed": sum(1 for r in results if r.get("status") == "fail"),
                "errors": sum(1 for r in results if r.get("status") == "error"),
                "score": round(
                    sum(1 for r in results if r.get("status") == "pass") / max(len(RULES), 1) * 100, 1
                ),
                "results": results,
            }
        finally:
            conn.close()

        # 使用独立连接持久化(避免 read_only 连接冲突)
        self._save_report(report)

        return report

    def _execute_rules(self, conn: duckdb.DuckDBPyConnection) -> list[dict[str, Any]]:
        """执行所有规则,返回结果列表"""
        results = []
        for rule in RULES:
            try:
                rows = conn.execute(rule.check_sql).fetchall()
                violations = len(rows)
                columns = [desc[0] for desc in conn.description]

                result = {
                    "rule_id": rule.rule_id,
                    "severity": rule.severity,
                    "description": rule.description,
                    "violations": violations,
                    "status": "pass" if violations == 0 else "fail",
                }

                if violations > 0 and columns:
                    result["details"] = []
                    for row in rows[:5]:
                        detail = {}
                        for i, col in enumerate(columns):
                            val = row[i]
                            detail[col] = str(val) if val is not None else None
                        result["details"].append(detail)

                results.append(result)

            except Exception as e:
                logger.warning(f"规则 '{rule.rule_id}' 执行失败: {e}")
                results.append({
                    "rule_id": rule.rule_id,
                    "severity": rule.severity,
                    "description": rule.description,
                    "violations": 0,
                    "status": "error",
                    "error": str(e),
                })

        return results

    def _save_report(self, report: dict[str, Any]) -> None:
        """持久化质量报告到 quality_report 表"""
        conn = duckdb.connect(self.db_path)
        try:
            # 先创建序列,再创建表
            conn.execute("CREATE SEQUENCE IF NOT EXISTS seq_quality_report_id")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS quality_report (
                    id INTEGER PRIMARY KEY DEFAULT nextval('seq_quality_report_id'),
                    check_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    score DECIMAL(5,1),
                    passed_count INTEGER,
                    failed_count INTEGER,
                    error_count INTEGER,
                    report_json TEXT
                )
            """)

            conn.execute(
                """
                INSERT INTO quality_report (check_time, score, passed_count, failed_count, error_count, report_json)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    report["check_time"],
                    report["score"],
                    report["passed"],
                    report["failed"],
                    report["errors"],
                    json.dumps(report, ensure_ascii=False, default=str),
                ),
            )
            logger.info(f"质量报告已保存: 评分 {report['score']}%")
        finally:
            conn.close()

    def get_latest_report(self) -> Optional[dict[str, Any]]:
        """获取最近一次质量检查报告"""
        conn = duckdb.connect(self.db_path, read_only=True)
        try:
            row = conn.execute(
                "SELECT report_json FROM quality_report ORDER BY check_time DESC LIMIT 1"
            ).fetchone()
            if row and row[0]:
                return json.loads(row[0])
        except Exception:
            pass
        finally:
            conn.close()
        return None

    def get_report_history(self, limit: int = 30) -> list[dict[str, Any]]:
        """获取历史质量报告摘要列表"""
        conn = duckdb.connect(self.db_path, read_only=True)
        try:
            rows = conn.execute(
                "SELECT check_time, score, passed_count, failed_count, error_count "
                "FROM quality_report ORDER BY check_time DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [
                {
                    "check_time": str(r[0]),
                    "score": r[1],
                    "passed": r[2],
                    "failed": r[3],
                    "errors": r[4],
                }
                for r in rows
            ]
        except Exception:
            return []
        finally:
            conn.close()