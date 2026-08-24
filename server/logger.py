import logging
import os

os.makedirs("logs", exist_ok=True)

logger = logging.getLogger("AOS")
logger.setLevel(logging.INFO)

file_handler = logging.FileHandler("logs/app.log")

formatter = logging.Formatter(
    "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)

file_handler.setFormatter(formatter)

logger.addHandler(file_handler)