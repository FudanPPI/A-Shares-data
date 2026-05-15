
import logging
import sys
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


def main():
    setup_logging()
    logger = logging.getLogger(__name__)

    try:
        scheduler = Scheduler()
        scheduler.run()
        scheduler.close()
    except Exception as e:
        logger.error("运行失败", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
