import duckdb
import logging
import shutil
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)


class BackupManager:
    def __init__(self, db_path: Path, backup_dir: Path, retention_days: int = 30):
        self.db_path = db_path
        self.backup_dir = backup_dir
        self.retention_days = retention_days

    def create_backup(self):
        timestamp = datetime.now().strftime("%Y%m%d")
        backup_file = self.backup_dir / f"stock_data_{timestamp}.duckdb"

        shutil.copy2(self.db_path, backup_file)
        logger.info(f"数据库备份完成: {backup_file}")

        self._cleanup_old_backups()

    def _cleanup_old_backups(self):
        cutoff = datetime.now() - timedelta(days=self.retention_days)

        for backup_file in self.backup_dir.glob("stock_data_*.duckdb"):
            try:
                file_date_str = backup_file.stem.split("_")[-1]
                file_date = datetime.strptime(file_date_str, "%Y%m%d")

                if file_date < cutoff:
                    backup_file.unlink()
                    logger.info(f"删除过期备份: {backup_file}")
            except Exception as e:
                logger.warning(f"清理备份失败 {backup_file}: {e}")

    def check_integrity(self, conn) -> bool:
        try:
            tables = [
                "stock_daily", "financial_statements", "announcements",
                "update_log", "technical_indicators", "valuation_indicators",
                "stock_capital", "dividends", "financial_intermediate",
                "northbound_flow", "margin_trading", "dragon_tiger",
                "dragon_tiger_detail", "column_metadata"
            ]

            for table in tables:
                try:
                    count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                    logger.info(f"{table}: {count} 条记录")
                except Exception:
                    logger.info(f"{table}: 表不存在或无法访问")

            return True
        except Exception as e:
            logger.error(f"数据完整性检查失败: {e}")
            return False