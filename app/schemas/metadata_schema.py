from sqlalchemy import Column, String, UUID, TIMESTAMP, func, ForeignKey, Index
from sqlalchemy.dialects.postgresql import JSONB
from app.config.database_config.db_base import Base

class AnalysisData(Base):
    __tablename__ = "analysis_data"

    id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    table_name = Column(String(255), primary_key=True)
    file_name = Column(String(255), nullable=False)
    schema = Column(JSONB, nullable=False)
    column_insights = Column(JSONB, nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("idx_analysis_data_id", "id"),
    )
