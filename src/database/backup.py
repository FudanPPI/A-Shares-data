import duckdb
import logging
import shutil
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)


class BackupManager:
    """数据库备份管理器

    关键改进:
      - 备份前强制 CHECKPOINT,确保 WAL 数据已刷入主文件,否则备份文件不完整
      - 文件名使用时间戳(精确到秒),避免同一天多次运行只保留最后一次
      - 保留策略: 按文件数量上限 + 按天数双重清理
    """

    def __init__(self, db_path: Path, backup_dir: Path, retention_days: int = 30,
                 max_backups: int = 50):
        self.db_path = db_path
        self.backup_dir = backup_dir
        self.retention_days = retention_days
        self.max_backups = max_backups  # 防止高频运行导致备份爆炸

    def create_backup(self, conn=None):
        """创建数据库备份

        Args:
            conn: 可选的活跃连接,用于执行 CHECKPOINT。
                  若不传,会临时新建连接执行 CHECKPOINT。
                  推荐传入采集流程的写连接,保证备份时数据一致。
        """
        # 关键: 备份前强制把 WAL 刷入主文件
        # DuckDB 写入会先写 WAL,不 CHECKPOINT 直接 copy 文件会丢最近数据
        self._do_checkpoint(conn)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = self.backup_dir / f"stock_data_{timestamp}.duckdb"

        shutil.copy2(self.db_path, backup_file)
        logger.info(f"数据库备份完成: {backup_file}")

        self._cleanup_old_backups()
        return backup_file

    def _do_checkpoint(self, conn=None):
        """执行 CHECKPOINT,将 WAL 数据刷入主数据库文件"""
        if conn is not None:
            try:
                conn.execute("CHECKPOINT")
                return
            except Exception as e:
                logger.warning(f"通过传入连接 CHECKPOINT 失败,尝试独立连接: {e}")

        # 临时连接执行 CHECKPOINT
        # 注意: 此时主连接必须已关闭或已提交事务,否则会锁冲突
        tmp_conn = None
        try:
            tmp_conn = duckdb.connect(str(self.db_path))
            tmp_conn.execute("CHECKPOINT")
        except Exception as e:
            logger.warning(f"独立连接 CHECKPOINT 失败: {e}")
        finally:
            if tmp_conn:
                tmp_conn.close()

    def _cleanup_old_backups(self):
        """清理过期备份: 按天数 + 按数量双重策略"""
        now = datetime.now()
        cutoff = now - timedelta(days=self.retention_days)

        backups = []
        for backup_file in self.backup_dir.glob("stock_data_*.duckdb"):
            try:
                # 文件名格式: stock_data_YYYYMMDD_HHMMSS.duckdb
                file_date_str = backup_file.stem.split("_")[-2]  # YYYYMMDD 部分
                file_date = datetime.strptime(file_date_str, "%Y%m%d")
                age_days = (now - file_date).days
                backups.append((backup_file, file_date, age_days))
            except (ValueError, IndexError) as e:
                logger.debug(f"跳过无法解析的备份文件 {backup_file}: {e}")
                continue

        # 策略1: 删除超过保留期的备份
        for backup_file, file_date, age_days in backups:
            if age_days > self.retention_days:
                try:
                    backup_file.unlink()
                    logger.info(f"删除过期备份(>{self.retention_days}天): {backup_file}")
                except Exception as e:
                    logger.warning(f"删除备份失败 {backup_file}: {e}")

        # 策略2: 若剩余数量仍超上限,删除最旧的
        remaining = []
        for backup_file in self.backup_dir.glob("stock_data_*.duckdb"):
            try:
                file_date_str = backup_file.stem.split("_")[-2]
                file_date = datetime.strptime(file_date_str, "%Y%m%d")
                remaining.append((backup_file, file_date))
            except Exception:
                continue

        remaining.sort(key=lambda x: x[1])  # 按日期升序
        while len(remaining) > self.max_backups:
            backup_file, _ = remaining.pop(0)  # 删最旧的
            try:
                backup_file.unlink()
                logger.info(f"删除超额备份(>{self.max_backups}个): {backup_file}")
            except Exception as e:
                logger.warning(f"删除超额备份失败 {backup_file}: {e}")

    def check_integrity(self, conn) -> bool:
        """数据完整性检查: 表存在性 + 记录数

        注意: 此检查较浅层,深度质量检查请使用 src/quality/checker.py 的 QualityChecker
        """
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
