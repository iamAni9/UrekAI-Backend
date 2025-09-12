from sqlalchemy import MetaData
from sqlalchemy.ext.declarative import declarative_base

# shared metadata for Alembic
metadata = MetaData()
Base = declarative_base(metadata=metadata)