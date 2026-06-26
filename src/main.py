
import logging
import sys
import argparse
from pathlib import Path
from src.config import LOG_PATH, LOG_LEVEL
from src.scheduler import Scheduler


def setup_logging():
    log_dir = Path(LOG_PATH).parent
    log_dir.mkdir(parents=True, exist_ok=True)

    log_level = getattr(logging, LOG_LEVEL.upper(), logging.INFO)

    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(LOG_PATH, encoding="utf-8"),
            logging.StreamHandler(sys.stdout)
        ]
    )


def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description="A-Shares 数据采集与指标计算系统",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python -m src.main                          # 运行（使用缓存）
  python -m src.main --force                  # 强制刷新所有数据
  python -m src.main -f --stocks sh600519      # 强制刷新茅台
  python -m src.main --list-stocks            # 列出配置的股票
        """
    )
    
    parser.add_argument(
        "-f", "--force",
        action="store_true",
        help="强制刷新：跳过缓存，直接从网络获取所有数据"
    )
    
    parser.add_argument(
        "--stocks",
        nargs="+",
        help="指定采集的股票代码（不指定则使用配置中的所有股票）"
    )
    
    parser.add_argument(
        "--list-stocks",
        action="store_true",
        help="列出配置的股票代码"
    )
    
    return parser.parse_args()


def main():
    setup_logging()
    logger = logging.getLogger(__name__)

    args = parse_args()
    
    if args.list_stocks:
        from src.config import STOCK_CODES
        print("配置的股票代码:")
        for code in STOCK_CODES:
            print(f"  {code}")
        return

    try:
        scheduler = Scheduler()
        scheduler.run(stock_codes=args.stocks)
        scheduler.close()
        
        if args.force:
            logger.info("强制刷新模式运行完成")
        else:
            logger.info("运行完成（已启用智能缓存）")
            
    except Exception as e:
        logger.error("运行失败", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
