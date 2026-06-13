"""数据采集更新脚本 - 支持增量更新"""
import sys
import time
import logging
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.scheduler import Scheduler
from src.config import STOCK_CODES, DB_PATH, LOG_PATH

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(LOG_PATH, encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)


def run_update(stock_codes=None, force_full=False):
    """运行数据更新
    
    Args:
        stock_codes: 指定股票代码列表, None则使用配置中的全部
        force_full: 是否强制全量更新(忽略last_update_date)
    """
    if stock_codes is None:
        stock_codes = STOCK_CODES
    
    print("=" * 60)
    print(f"启动多数据源数据采集与指标计算")
    print(f"股票数量: {len(stock_codes)}")
    print(f"数据库: {DB_PATH}")
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    scheduler = Scheduler()
    
    start_time = time.time()
    
    try:
        scheduler.run(stock_codes)
        
        elapsed = time.time() - start_time
        print(f"\n{'='*60}")
        print(f"更新完成! 耗时: {elapsed:.1f}秒")
        print(f"{'='*60}")
        
    except Exception as e:
        elapsed = time.time() - start_time
        print(f"\n{'='*60}")
        print(f"更新失败! 耗时: {elapsed:.1f}秒")
        print(f"错误: {e}")
        print(f"{'='*60}")
        raise
    finally:
        scheduler.close()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='股票数据采集更新')
    parser.add_argument('--stocks', nargs='+', help='指定股票代码, 如 sh600519 sz002843')
    parser.add_argument('--full', action='store_true', help='强制全量更新')
    
    args = parser.parse_args()
    
    stocks = args.stocks if args.stocks else None
    run_update(stock_codes=stocks, force_full=args.full)
