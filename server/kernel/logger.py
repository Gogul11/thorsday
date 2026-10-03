import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOG_DIR = Path(__file__).resolve().parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

logger = logging.getLogger("AOS")
logger.setLevel(logging.INFO)

file_handler = RotatingFileHandler(
    LOG_DIR / "app.log",
    encoding="utf-8",
    errors="replace",
    maxBytes=5 * 1024 * 1024,
    backupCount=3,
)

formatter = logging.Formatter(
    "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)

file_handler.setFormatter(formatter)

if not logger.handlers:
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

logger.propagate = False
