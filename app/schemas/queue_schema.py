from sqlalchemy import Column, UUID, TIMESTAMP, func, Index, Text, SmallInteger, Integer
from app.config.database_config.db_base import Base

class CsvQueue(Base):
    __tablename__ = "csv_queue"

    id = Column(Integer, primary_key=True, autoincrement=True)
    upload_id = Column(UUID(as_uuid=True), unique=True, nullable=False)
    user_id = Column(Text, nullable=False)
    table_name = Column(Text, nullable=False)
    file_path = Column(Text, nullable=False)
    original_file_name = Column(Text, nullable=False)
    status = Column(Text, nullable=False, server_default="pending")
    progress = Column(SmallInteger, nullable=False, server_default="0")
    medium = Column(Text, nullable=True)
    receiver_no = Column(Text, nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("idx_csv_queue_status_upload_id_progress", "status", "upload_id", "progress"),
        # {"postgresql_unlogged": True},  # mark as UNLOGGED
    )

class ExcelQueue(Base):
    __tablename__ = "excel_queue"

    id = Column(Integer, primary_key=True, autoincrement=True)
    upload_id = Column(UUID(as_uuid=True), unique=True, nullable=False)
    user_id = Column(Text, nullable=False)
    table_name = Column(Text, nullable=False)
    file_path = Column(Text, nullable=False)
    original_file_name = Column(Text, nullable=False)
    status = Column(Text, nullable=False, server_default="pending")
    progress = Column(SmallInteger, nullable=False, server_default="0")
    medium = Column(Text, nullable=True)
    receiver_no = Column(Text, nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("idx_excel_queue_status_upload_id_progress", "status", "upload_id", "progress"),
        # {"postgresql_unlogged": True},  # mark as UNLOGGED
    )
