import logging
from databases import Database
from .settings import settings

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

DATABASE_URL = settings.DATABASE_URL

if not DATABASE_URL:
    raise Exception("Missing DATABASE_URL in environment variables.")

database = Database(DATABASE_URL)

async def verify_db_connection():
    try:
        await database.connect()
        await database.execute("SELECT 1")
        logger.info("✅ Database connection successful")
    except Exception as e:
        logger.critical("❌ Database connection failed: %s", e)
        raise
    finally:
        await database.disconnect()
