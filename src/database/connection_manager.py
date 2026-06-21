"""数据库连接管理器 - 读写分离 + 线程安全

设计原理:
  DuckDB 单连接非线程安全,但同一数据库文件可由多个连接并发访问。
  本管理器采用"1写N读"模型:
    - 主写连接: 全局唯一,通过 _write_lock 串行化所有写操作
    - 读连接池: 每个线程独立读连接,支持并发查询
    - 备份专用连接: 独立连接避免与采集流程冲突

线程安全保证:
  - 写操作(INSERT/UPDATE/DELETE/事务)全部通过 acquire_writer() 串行
  - 读操作(SELECT)通过 acquire_reader() 获取线程独立连接
  - 连接关闭时自动归还(通过 contextmanager)
"""
import duckdb
import logging
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class ConnectionManager:
    """数据库连接池: 1写N读,写连接加全局锁

    用法:
        cm = ConnectionManager(db_path)
        # 写操作
        with cm.acquire_writer() as conn:
            conn.execute("INSERT INTO ...")
        # 读操作
        with cm.acquire_reader() as conn:
            df = conn.execute("SELECT ...").fetchdf()
    """

    def __init__(self, db_path: Path, read_pool_size: int = 8):
        self.db_path = db_path
        self.read_pool_size = read_pool_size

        # 写连接: 全局唯一,加锁串行化
        self._write_conn: Optional[duckdb.DuckDBPyConnection] = None
        self._write_lock = threading.RLock()  # 可重入锁,支持嵌套事务
        self._in_transaction = False  # 事务状态标志

        # 读连接池: threading.local 保证每线程独立连接
        self._read_local = threading.local()
        self._read_conns = []  # 跟踪所有读连接,便于统一关闭
        self._read_conns_lock = threading.Lock()

        # 备份专用连接: 独立于采集流程
        self._backup_conn: Optional[duckdb.DuckDBPyConnection] = None

    def _get_write_conn(self) -> duckdb.DuckDBPyConnection:
        """获取写连接(惰性初始化)"""
        if self._write_conn is None:
            self._write_conn = duckdb.connect(str(self.db_path))
        return self._write_conn

    def _get_read_conn(self) -> duckdb.DuckDBPyConnection:
        """获取当前线程的读连接(threading.local 保证线程独立)

        注意: DuckDB 不允许同一数据库文件以不同配置(读写 vs 只读)打开多个连接,
        所以读连接也用读写模式打开,但仅用于 SELECT 查询。
        写操作仍通过写连接 + 写锁串行化。
        """
        conn = getattr(self._read_local, "conn", None)
        if conn is None:
            # 不能用 read_only=True,会与写连接配置冲突
            conn = duckdb.connect(str(self.db_path))
            self._read_local.conn = conn
            with self._read_conns_lock:
                self._read_conns.append(conn)
        return conn

    @contextmanager
    def acquire_writer(self):
        """获取写连接(加锁)

        所有写操作必须通过此方法获取连接,保证串行化。
        RLock 可重入,支持嵌套调用(如事务内调用其他写方法)。
        """
        self._write_lock.acquire()
        try:
            yield self._get_write_conn()
        finally:
            self._write_lock.release()

    @contextmanager
    def acquire_reader(self):
        """获取读连接(线程独立,不加锁)

        读连接通过 threading.local 保证每线程独立,可并发。
        """
        yield self._get_read_conn()

    @contextmanager
    def acquire_backup_conn(self):
        """获取备份专用连接

        独立于采集流程,避免备份时与采集连接冲突。
        """
        if self._backup_conn is None:
            self._backup_conn = duckdb.connect(str(self.db_path))
        try:
            yield self._backup_conn
        except Exception:
            # 备份连接异常时关闭重建,避免残留状态
            try:
                self._backup_conn.close()
            except Exception:
                pass
            self._backup_conn = None
            raise

    @property
    def write_lock(self):
        """暴露写锁,供 DatabaseOperations 事务使用"""
        return self._write_lock

    @property
    def write_conn(self):
        """暴露写连接,供 DatabaseOperations 直接访问"""
        return self._get_write_conn()

    @property
    def in_transaction(self):
        return self._in_transaction

    @in_transaction.setter
    def in_transaction(self, value: bool):
        self._in_transaction = value

    def checkpoint(self):
        """强制将 WAL 刷入主数据库文件

        备份前必须调用,否则备份文件可能缺少最近未 checkpoint 的数据。
        若当前在事务中,会先提交再 checkpoint,避免事务未提交导致数据不一致。
        """
        was_in_transaction = self._in_transaction
        with self._write_lock:
            conn = self._get_write_conn()
            if was_in_transaction:
                try:
                    conn.execute("COMMIT")
                except Exception:
                    pass
                self._in_transaction = False
            try:
                conn.execute("CHECKPOINT")
            finally:
                if was_in_transaction:
                    try:
                        conn.execute("BEGIN")
                    except Exception:
                        pass
                    self._in_transaction = True

    def close_all(self):
        """关闭所有连接(写连接 + 所有读连接 + 备份连接)

        关闭前若残留事务,回滚避免脏数据落盘。
        """
        # 关闭写连接
        if self._write_conn:
            if self._in_transaction:
                try:
                    self._write_conn.execute("ROLLBACK")
                except Exception:
                    pass
                self._in_transaction = False
            try:
                self._write_conn.close()
            except Exception:
                pass
            self._write_conn = None

        # 关闭所有读连接
        with self._read_conns_lock:
            for conn in self._read_conns:
                try:
                    conn.close()
                except Exception:
                    pass
            self._read_conns.clear()

        # 关闭备份连接
        if self._backup_conn:
            try:
                self._backup_conn.close()
            except Exception:
                pass
            self._backup_conn = None

    def close_writers(self):
        """仅关闭写连接(备份前调用,释放文件锁)

        读连接保持开启,因为备份后可能还需要查询校验。
        """
        if self._write_conn:
            if self._in_transaction:
                try:
                    self._write_conn.execute("ROLLBACK")
                except Exception:
                    pass
                self._in_transaction = False
            try:
                self._write_conn.close()
            except Exception:
                pass
            self._write_conn = None

    def close_readers(self):
        """关闭所有读连接(备份前调用,释放文件句柄)

        DuckDB 读连接也会持有数据库文件句柄,导致 shutil.copy 失败(WinError 32)。
        备份前必须关闭所有读连接,备份后由各线程按需重新建立。
        """
        with self._read_conns_lock:
            for conn in self._read_conns:
                try:
                    conn.close()
                except Exception:
                    pass
            self._read_conns.clear()
            # 清除 threading.local 中的缓存,下次 acquire_reader 会重建连接
            self._read_local = threading.local()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close_all()
