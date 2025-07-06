import asyncpg
import asyncio
from app.config.settings import settings
from app.config.logger import get_logger
from app.config.constants import NO_OF_CSV_WORKER_TASKS, CONCURRENCY_LIMIT_FOR_CSV_WORKER_TAKS, CSV_NOTIFY_CHANNEL, EXCEL_NOTIFY_CHANNEL
from .csv_worker import csv_processing
from .excel_worker import excel_processing

logger = get_logger("Job Listener")
semaphore = asyncio.Semaphore(CONCURRENCY_LIMIT_FOR_CSV_WORKER_TAKS)

async def process_next_job(conn, file_type):
    try: 
        async with semaphore:
            if file_type == 'csv':  
                logger.info("Starting CSV processing")
                await csv_processing(conn)
            else:
                logger.info("Startin EXCEL processing")
                await excel_processing(conn)
    except Exception as e:
        logger.error(f"Task processing failed while executing pending job: {e}")

async def process_next_job_worker(pool, queue):
    while True:
        job_payload = await queue.get() # worker will wait here if queue is empty, 
        file_type = job_payload["file_type"] # All workers will wait here, once job get add execution will resume in FIFO order.
        try:
            async with pool.acquire() as conn:
                await process_next_job(conn, file_type)
        except Exception as e:
            logger.exception(f"Failed to process job: {e}")
        finally:
            queue.task_done()

async def notification_listener(conn, queue):
    async def callback(conn, pid, channel, payload):
        logger.info(f"Received notification on '{channel}', pid: {pid}, payload: {payload}")
        await queue.put({"file_type": payload}) 
        
    await conn.add_listener(CSV_NOTIFY_CHANNEL, callback)
    await conn.add_listener(EXCEL_NOTIFY_CHANNEL, callback)
    
    logger.info(f"Listening to channel '{CSV_NOTIFY_CHANNEL}'...")
    logger.info(f"Listening to channel '{EXCEL_NOTIFY_CHANNEL}'...")

async def listen_and_process():
    try:
        pool = await asyncpg.create_pool(dsn=settings.DATABASE_URL, min_size=5, max_size=10)
        logger.info("Database connection established.")

        # Creating a bounded queue for all the incoming jobs
        queue = asyncio.Queue(maxsize=100)  # Avoid unbounded memory use

        # Starting listener
        conn = await pool.acquire()
        await notification_listener(conn, queue)

        # Start worker pool
        workers = [
            asyncio.create_task(process_next_job_worker(pool, queue))
            for _ in range(NO_OF_CSV_WORKER_TASKS)
        ]

        stop_event = asyncio.Event()
        await stop_event.wait()

    except asyncio.CancelledError:
        logger.info("Listener task was cancelled.")
    except Exception as e:
        logger.error(f"Encountered error: {e}")
    finally:
        if 'conn' in locals() and not conn.is_closed():
            await conn.close()
        if 'pool' in locals():
            await pool.close()
            # await pool.wait_closed()
            
        logger.info("Shutting down.")


if __name__ == "__main__":
    try:
        logger.info("Starting Workers")
        asyncio.run(listen_and_process())
    except KeyboardInterrupt:
        logger.info("Workers interrupted (Ctrl+C)")