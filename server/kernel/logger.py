import logging
from pathlib import Path

LOG_DIR = Path(__file__).resolve().parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

logger = logging.getLogger("AOS")
logger.setLevel(logging.INFO)

file_handler = logging.FileHandler(
    LOG_DIR / "app.log",
    encoding="utf-8",
    errors="replace",
)

formatter = logging.Formatter(
    "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)

file_handler.setFormatter(formatter)

if not logger.handlers:
    logger.addHandler(file_handler)
