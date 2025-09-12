from ..logger import get_logger
from databases import Database
from ..settings import settings
from sqlalchemy import create_engine

logger = get_logger("API Logger")

DATABASE_URL = settings.DATABASE_URL

if not DATABASE_URL:
    raise Exception("Missing DATABASE_URL in environment variables.")

database = Database(DATABASE_URL)

SYNC_DATABASE_URL = DATABASE_URL.replace("+asyncpg", "")
engine = create_engine(SYNC_DATABASE_URL) # sync engine only for migrations or explicit usage


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