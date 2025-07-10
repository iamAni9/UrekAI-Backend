import asyncpg
import asyncio
from app.config.settings import settings
from app.config.logger import get_logger
from app.config.constants import NO_OF_CSV_WORKER_TASKS, CONCURRENCY_LIMIT_FOR_CSV_WORKER_TAKS, CSV_NOTIFY_CHANNEL, EXCEL_NOTIFY_CHANNEL
from .csv_worker import csv_processing
from .excel_worker import excel_processing
from asyncpg.exceptions import ConnectionDoesNotExistError

logger = get_logger("Job Listener")
semaphore = asyncio.Semaphore(CONCURRENCY_LIMIT_FOR_CSV_WORKER_TAKS)

async def process_next_job(conn, file_type):
    try: 
        async with semaphore:
            if file_type == 'csv':  
                logger.info("Starting CSV processing")
                await csv_processing(conn)
            else:
                logger.info("Starting EXCEL processing")
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

async def periodic_pinger(conn, activity_event: asyncio.Event, idle_timeout: int = 180):
    while True:
        try:
            # Waiting for activity, with a timeout.
            await asyncio.wait_for(activity_event.wait(), timeout=idle_timeout)
            
            # If we get here, it means activity_event was set.
            activity_event.clear()  # Reset the event for the next wait.
            logger.info("Activity detected on listener connection. Resetting idle timer.")

        except asyncio.TimeoutError:
            # The wait timed out, meaning the connection was idle.
            logger.info(f"Connection idle for {idle_timeout}s. Pinging to keep alive.")
            try:
                await conn.execute("SELECT 1")
                activity_event.clear()
            except (ConnectionDoesNotExistError, ConnectionAbortedError):
                 logger.error("Listener connection lost while pinging. Stopping pinger.")
                 break
                 
        except asyncio.CancelledError:
            logger.info("Pinger task cancelled.")
            break
            
        except Exception as e:
            logger.error(f"Pinger encountered an error: {e}. Stopping.")
            break

async def notification_listener(conn, queue, activity_event: asyncio.Event):
    async def callback(conn, pid, channel, payload):
        logger.info(f"Received notification on '{channel}', pid: {pid}, payload: {payload}")
        activity_event.set()  # Signal that activity has occurred!
        await queue.put({"file_type": payload}) 
        
    await conn.add_listener(CSV_NOTIFY_CHANNEL, callback)
    await conn.add_listener(EXCEL_NOTIFY_CHANNEL, callback)
    
    logger.info(f"Listening to channel '{CSV_NOTIFY_CHANNEL}'...")
    logger.info(f"Listening to channel '{EXCEL_NOTIFY_CHANNEL}'...")

            
async def listen_and_process():
    try:
        listener_conn = await asyncpg.connect(
            dsn=settings.DATABASE_URL,
            # server_settings={'tcp_keepalives_idle': '60'} 
        )
        logger.info("Dedicated listener connection established with keepalives.")
        
         # Create the event that will be shared between the pinger and listener
        activity_event = asyncio.Event()
        
        # Starting the pinger as a background task
        # Pings every 3 minutes (180 seconds)
        pinger_task = asyncio.create_task(periodic_pinger(listener_conn, activity_event, 180))
        logger.info("Connection pinger started.")
        
        pool = await asyncpg.create_pool(dsn=settings.DATABASE_URL, min_size=5, max_size=10)
        logger.info("Workers database connection pool established.")

        # Creating a bounded queue for all the incoming jobs
        queue = asyncio.Queue(maxsize=100)  # Avoid unbounded memory use

        # Starting listener
        await notification_listener(listener_conn, queue, activity_event)

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
        raise
    finally:
        if pinger_task:
            pinger_task.cancel()
            logger.info("Pinger task cancelled.")
        if 'listener_conn' in locals() and not listener_conn.is_closed():
            await listener_conn.close()
            logger.info("Listener connection closed.")
        if 'pool' in locals():
            await pool.close()
            logger.info("Worker pool closed.")
            
        logger.info("Shutting down.")

if __name__ == "__main__":
    try:
        logger.info("Starting Workers")
        asyncio.run(listen_and_process())
    except KeyboardInterrupt:
        logger.info("Workers interrupted (Ctrl+C)")