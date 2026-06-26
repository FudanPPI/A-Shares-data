"""数据缓存策略模块

提供智能缓存机制，根据数据类型差异化缓存时长：
- 日线行情: 5分钟
- 北向资金: 1天
- 财务数据: 7天
- 融资融券: 1天
- 估值PE/PB: 30分钟

特性：
- 智能跳过非交易日（周末、节假日）
- 支持强制刷新（bypass）
- 复用 update_log 表记录更新时间
"""
from datetime import datetime, timedelta, date
from functools import wraps
from typing import Optional, Callable
import logging

logger = logging.getLogger(__name__)

# 缓存配置（按数据类型差异化）
CACHE_CONFIG = {
    "daily": {"fresh_minutes": 5},
    "northbound": {"fresh_hours": 24},
    "financial": {"fresh_days": 7},
    "margin": {"fresh_hours": 24},
    "valuation": {"fresh_minutes": 30},
}

# A股交易日（简化版，实际应接入交易日历）
HOLIDAYS_2024 = {
    # 元旦
    date(2024, 1, 1),
    # 春节
    date(2024, 2, 9), date(2024, 2, 10), date(2024, 2, 12),
    date(2024, 2, 13), date(2024, 2, 14), date(2024, 2, 15),
    date(2024, 2, 16), date(2024, 2, 19),
    # 清明
    date(2024, 4, 4), date(2024, 4, 5), date(2024, 4, 6),
    # 劳动节
    date(2024, 5, 1), date(2024, 5, 2), date(2024, 5, 3), date(2024, 5, 4), date(2024, 5, 5),
    # 端午节
    date(2024, 6, 10), date(2024, 6, 11), date(2024, 6, 12),
    # 中秋节
    date(2024, 9, 15), date(2024, 9, 16), date(2024, 9, 17),
    # 国庆节
    date(2024, 10, 1), date(2024, 10, 2), date(2024, 10, 3),
    date(2024, 10, 4), date(2024, 10, 7),
}

HOLIDAYS_2026 = {
    # 元旦
    date(2026, 1, 1), date(2026, 1, 2), date(2026, 1, 3),
    # 春节
    date(2026, 2, 17), date(2026, 2, 18), date(2026, 2, 19),
    date(2026, 2, 20), date(2026, 2, 21), date(2026, 2, 23),
    date(2026, 2, 24),
    # 清明
    date(2026, 4, 4), date(2026, 4, 5), date(2026, 4, 6),
    # 劳动节
    date(2026, 5, 1), date(2026, 5, 2), date(2026, 5, 3), date(2026, 5, 4), date(2026, 5, 5),
    # 端午节
    date(2026, 6, 29), date(2026, 6, 30), date(2026, 7, 1),
    # 中秋节
    date(2026, 9, 25), date(2026, 9, 26), date(2026, 9, 27),
    # 国庆节
    date(2026, 10, 1), date(2026, 10, 2), date(2026, 10, 3),
    date(2026, 10, 5), date(2026, 10, 6), date(2026, 10, 7), date(2026, 10, 8),
}

ALL_HOLIDAYS = HOLIDAYS_2024 | HOLIDAYS_2026


def is_trading_day(d: date) -> bool:
    """判断是否为交易日（排除周末和节假日）"""
    if d.weekday() >= 5:  # 周六、周日
        return False
    if d in ALL_HOLIDAYS:
        return False
    return True


def get_last_trading_day(ref_date: date = None) -> date:
    """获取最近的交易日（向前追溯）"""
    if ref_date is None:
        ref_date = date.today()
    
    d = ref_date
    for _ in range(10):  # 最多回溯10天
        if is_trading_day(d):
            return d
        d = d - timedelta(days=1)
    
    return ref_date  # 兜底返回原日期


def get_next_trading_day(ref_date: date = None) -> date:
    """获取下一个交易日（向后查找）"""
    if ref_date is None:
        ref_date = date.today()
    
    d = ref_date + timedelta(days=1)
    for _ in range(10):  # 最多查找10天
        if is_trading_day(d):
            return d
        d = d + timedelta(days=1)
    
    return ref_date + timedelta(days=1)  # 兜底


class CacheChecker:
    """缓存新鲜度检查器
    
    复用 update_log 表判断本地数据是否足够新鲜。
    """

    def __init__(self, db_ops, force_refresh: bool = False):
        self.db_ops = db_ops
        self.force_refresh = force_refresh

    def is_fresh(self, stock_code: str, data_type: str) -> bool:
        """判断数据是否足够新鲜
        
        Returns:
            True: 数据足够新鲜，跳过网络请求
            False: 数据过期，需要重新获取
        """
        if self.force_refresh:
            logger.debug(f"[cache] 强制刷新模式，跳过缓存检查")
            return False

        config = CACHE_CONFIG.get(data_type, {})
        if not config:
            return False

        last_update = self._get_last_update(stock_code, data_type)
        if last_update is None:
            logger.debug(f"[cache] {stock_code} {data_type} 无缓存记录")
            return False

        now = datetime.now()

        # 检查缓存是否在有效期内
        if "fresh_minutes" in config:
            threshold = now - timedelta(minutes=config["fresh_minutes"])
            is_fresh = last_update >= threshold
            if not is_fresh:
                logger.debug(f"[cache] {stock_code} {data_type} 缓存过期(>{config['fresh_minutes']}分钟)")
            return is_fresh

        if "fresh_hours" in config:
            threshold = now - timedelta(hours=config["fresh_hours"])
            is_fresh = last_update >= threshold
            if not is_fresh:
                logger.debug(f"[cache] {stock_code} {data_type} 缓存过期(>{config['fresh_hours']}小时)")
            return is_fresh

        if "fresh_days" in config:
            threshold = now - timedelta(days=config["fresh_days"])
            is_fresh = last_update >= threshold
            if not is_fresh:
                logger.debug(f"[cache] {stock_code} {data_type} 缓存过期(>{config['fresh_days']}天)")
            return is_fresh

        return False

    def is_data_current(self, stock_code: str, data_type: str) -> bool:
        """判断数据是否为当前最新（智能交易日判断）
        
        用于日更新的数据（如北向资金），检查本地数据是否已是最新交易日的数据。
        """
        last_update = self._get_last_update_date_only(stock_code, data_type)
        if last_update is None:
            return False

        today = date.today()
        
        if is_trading_day(today):
            # 交易日：检查是否已有今天的数据
            if last_update >= today:
                logger.debug(f"[cache] {stock_code} {data_type} 已是今天({today})数据")
                return True
        else:
            # 非交易日：检查是否有最近交易日的数据
            last_trading = get_last_trading_day(today)
            if last_update >= last_trading:
                logger.debug(f"[cache] {stock_code} {data_type} 已是最近交易日({last_trading})数据")
                return True

        return False

    def _get_last_update(self, stock_code: str, data_type: str) -> Optional[datetime]:
        """获取最后更新时间（带时间）"""
        try:
            result = self.db_ops.conn.execute("""
                SELECT update_time FROM update_log
                WHERE stock_code = ? AND data_type = ?
                ORDER BY update_time DESC LIMIT 1
            """, [stock_code, data_type]).fetchone()
            
            if result and result[0]:
                if isinstance(result[0], str):
                    return datetime.strptime(result[0], "%Y-%m-%d %H:%M:%S")
                return result[0]
        except Exception as e:
            logger.debug(f"[cache] 查询缓存失败: {e}")
        return None

    def _get_last_update_date_only(self, stock_code: str, data_type: str) -> Optional[date]:
        """获取最后更新日期（仅日期）"""
        try:
            result = self.db_ops.conn.execute("""
                SELECT last_update_date FROM update_log
                WHERE stock_code = ? AND data_type = ?
                ORDER BY last_update_date DESC LIMIT 1
            """, [stock_code, data_type]).fetchone()
            
            if result and result[0]:
                if isinstance(result[0], str):
                    return datetime.strptime(result[0], "%Y-%m-%d").date()
                return result[0]
        except Exception as e:
            logger.debug(f"[cache] 查询缓存失败: {e}")
        return None


def cached_source(data_type: str):
    """缓存装饰器
    
    用于标记需要缓存的数据采集方法。
    配合 CacheChecker 使用。
    
    Example:
        @cached_source("northbound")
        def collect_northbound(self, stock_code):
            ...
    """
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(self, stock_code: str, force_refresh: bool = False, **kwargs):
            checker = getattr(self, '_cache_checker', None)
            
            # 如果有checker且不禁用缓存，先检查新鲜度
            if checker and not force_refresh:
                if checker.is_fresh(stock_code, data_type):
                    logger.info(f"[cache] {stock_code} {data_type} 数据新鲜，跳过采集")
                    return
                
                # 对于日更新数据，检查是否已是最新交易日数据
                if checker.is_data_current(stock_code, data_type):
                    logger.info(f"[cache] {stock_code} {data_type} 已是最新交易日数据，跳过采集")
                    return
            
            # 执行实际采集
            return func(self, stock_code, **kwargs)
        
        return wrapper
    return decorator


# 便捷函数
def should_skip_fetch(db_ops, stock_code: str, data_type: str, 
                       force_refresh: bool = False) -> bool:
    """判断是否应跳过网络获取
    
    Returns:
        True: 应跳过，使用本地缓存
        False: 需要网络获取
    """
    if force_refresh:
        return False
    
    checker = CacheChecker(db_ops, force_refresh)
    
    # 先检查缓存新鲜度
    if checker.is_fresh(stock_code, data_type):
        return True
    
    # 对于日更新数据，检查是否已是最新交易日
    if data_type == "northbound":
        if checker.is_data_current(stock_code, data_type):
            return True
    
    return False
