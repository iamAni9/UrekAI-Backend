import time
import traceback
from app.workers.job_listener import listen_and_process
from app.config.logger import get_logger
import asyncio

logger = get_logger("Job Listener")

if __name__ == "__main__":
    while True:
        try:
            logger.info("Starting Workers")
            asyncio.run(listen_and_process())
        except Exception:
            logger.error("Workers crashed! Restarting in 5 seconds...")
            traceback.print_exc()
            time.sleep(5)
        except KeyboardInterrupt:
            logger.info("Workers interrupted by user (Ctrl+C)")
            break