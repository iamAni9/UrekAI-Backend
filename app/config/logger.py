import logging
import sys

logger = logging.getLogger("api_logger")
logger.setLevel(logging.INFO)

# Avoid adding multiple handlers during reload
if not logger.hasHandlers():
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter(
        "%(asctime)s - %(levelname)s - %(name)s - [%(message)s]"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)

# This ensures logs won't be swallowed by parent handlers
logger.propagate = False