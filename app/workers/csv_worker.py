import asyncpg
import asyncio
from app.config.logger import logger
from app.config.settings import settings
from app.config.constants import CONCURRENCY_LIMIT_FOR_CSV_WORKER_TAKS, NO_OF_CSV_WORKER_TASKS, MAX_UPLOAD_RETRIES, SAMPLE_ROW_LIMIT
import os, math
from app.utils.db_utils import remove_analysis, delete_temp_table, create_table_from_schema
from app.utils.schema_generation import generate_table_schema
# from app.helper.csv_worker_helper import get_sample_rows, add_data_into_table_from_csv
from app.helper.csv_worker_helper_new import get_sample_rows, add_data_into_table_from_csv

# job_event = asyncio.Event()
semaphore = asyncio.Semaphore(CONCURRENCY_LIMIT_FOR_CSV_WORKER_TAKS)

NOTIFY_CHANNEL = "new_csv_job"
NO_OF_CSV_WORKER_TASKS = 2

async def fetch_next_csv_job(conn):
    try:
        async with conn.transaction():
            row = await conn.fetchrow("""
                UPDATE csv_queue
                SET status = 'processing'
                WHERE id = (
                    SELECT id FROM csv_queue
                    WHERE status = 'pending'
                    ORDER BY created_at
                    FOR UPDATE SKIP LOCKED
                    LIMIT 1
                )
                RETURNING *
            """)
            return row
        logger.info("Checking job successful.")
    except Exception as e:
        logger.error(f"Error while updating the csv queue, {e}")
        raise

async def process_next_job_worker(pool, queue):
    while True:
        job_payload = await queue.get()
        try:
            async with pool.acquire() as conn:
                await process_next_job(conn, job_payload)
        except Exception as e:
            logger.exception(f"Failed to process job: {e}")
        finally:
            queue.task_done()

async def notification_listener(conn, queue):
    async def callback(conn, pid, channel, payload):
        logger.info(f"Received notification on '{channel}': {payload}")
        await queue.put(payload)  # Use payload if needed for job ID or data

    await conn.add_listener(NOTIFY_CHANNEL, callback)
    logger.info(f"Listening to channel '{NOTIFY_CHANNEL}'...")
        
async def process_next_job(conn, pay_load):
    try: 
        async with semaphore:  
            job = await fetch_next_csv_job(conn)
            if job:
                await handle_job(dict(job), conn)
    except Exception as e:
        logger.error(f"Task processing failed while executing pending job: {e}")

async def listen_and_process():
    try:
        pool = await asyncpg.create_pool(dsn=settings.DATABASE_URL, min_size=5, max_size=10)
        logger.info("Database connection established.")

        # Create a bounded queue
        queue = asyncio.Queue(maxsize=100)  # Avoid unbounded memory use

        # Start listener
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
            await pool.wait_closed()
            
        logger.info("Shutting down.")

async def handle_job(job, conn):
    try:
        file_path = job["file_path"]
        table_name = job["table_name"]
        userid = job["user_id"]
        email = job["email"]
        upload_id = job["upload_id"]
        original_file_name = job["original_file_name"]
        
        for attempt in range(1, MAX_UPLOAD_RETRIES + 1):
            table_created = False
            analysis_done = False
            try:
                logger.info(f"Starting CSV processing attempt {attempt}/{MAX_UPLOAD_RETRIES} || File Path: {file_path}, Upload Id: {upload_id}")

                # Step 1: Getting sample data from uploaded file
                sample_rows = await get_sample_rows(file_path, SAMPLE_ROW_LIMIT)
                logger.info(f"Sample rows extracted {sample_rows['row01']}")

                # Step 2: Generating schema using LLM
                table_schema = await generate_table_schema(conn, userid, table_name, original_file_name, sample_rows)
                if not table_schema:
                    raise Exception("Schema generation returned None")
                
                analysis_done = True
                
                schema = table_schema["schema"]
                contain_columns = table_schema["contain_columns"]
                # logger.info(f"Schema: {schema}")
                # logger.info(f"Contain Column: {contain_columns}")
                
                # Step 3: Creating DB table using schema generated by LLM                
                await create_table_from_schema(conn, table_name, schema)
                table_created = True

                # Step 4: Insert full CSV into DB table
                await add_data_into_table_from_csv(conn, file_path, table_name, schema, contain_columns["contain_column"])

                logger.info(f"CSV processing completed successfully for upload {upload_id}")
                return  

            except Exception as e:
                logger.error(f"CSV processing attempt {attempt} failed for upload_id {upload_id}, {e}")
                
                if analysis_done:
                    await remove_analysis(conn, userid, table_name)
                
                if table_created:
                    await delete_temp_table(conn, table_name)
                
            if attempt == MAX_UPLOAD_RETRIES:
                logger.error(f"All {MAX_UPLOAD_RETRIES} attempts failed for upload {upload_id}")
                raise

            # Retry delay (exponential backoff)
            wait_time = math.pow(2, attempt)
            logger.info(f"Retrying after {wait_time:.1f} seconds")
            await asyncio.sleep(wait_time)

            # Cleanup if partially created
            if table_created:
                await delete_temp_table(conn, table_name)

        # Deleting file received
        os.remove(file_path)
        logger.info(f"Temporary CSV file deleted: {file_path}")
    except Exception as e:
        raise

if __name__ == "__main__":
    try:
        logger.info("Starting CSV Worker")
        asyncio.run(listen_and_process())
    except KeyboardInterrupt:
        logger.info("Worker interrupted (Ctrl+C)")