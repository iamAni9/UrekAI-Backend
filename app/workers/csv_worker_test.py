import asyncpg
import asyncio
from app.config.settings import settings
from app.config.logger import logger

def notification_handler(connection, pid, channel, payload):
    logger.info(f"Got NOTIFY: channel={channel}, payload={payload}")

async def listen_for_notifications():
    try:
        conn = await asyncpg.connect(settings.DATABASE_URL)
        logger.info("Database connection established.")

        # Set up the listener
        await conn.add_listener('new_csv_job', notification_handler)
        logger.info("Listening on channel 'new_csv_job'...")

        # This Event will keep the coroutine alive indefinitely.
        # It's better than sleep() because it expresses the intent to wait forever.
        stop_event = asyncio.Event()
        await stop_event.wait()

    except asyncio.CancelledError:
        logger.info("Listener task was cancelled.")
    except Exception as e:
        logger.error(f"An error occurred in the listener: {e}")
    finally:
        if 'conn' in locals() and not conn.is_closed():
            # Clean up by removing the listener and closing the connection
            await conn.remove_listener('new_csv_job', notification_handler)
            await conn.close()
            logger.info("Database connection closed.")

if __name__ == "__main__":
    try:
        asyncio.run(listen_for_notifications())
    except KeyboardInterrupt:
        logger.info("\nShutting down listener.")

