import logging
import sys

def get_logger(name: str):
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    
    # 🚫 Suppress excessive WebSocket logs
    logging.getLogger("websockets").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.protocols.websockets").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.error").setLevel(logging.INFO)  # Optional: reduce Uvicorn noise

    # Avoid adding duplicate handlers
    if not logger.hasHandlers():
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(
            "%(asctime)s - %(levelname)s - %(name)s - [%(message)s]"
        )
        handler.setFormatter(formatter)
        handler.stream.reconfigure(encoding='utf-8')
        logger.addHandler(handler)

    logger.propagate = False
    return logger