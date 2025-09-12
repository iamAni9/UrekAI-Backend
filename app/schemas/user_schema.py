from sqlalchemy import Column, String, UUID, TIMESTAMP, func, Text, ForeignKey, Index
import uuid
from app.config.database_config.db_base import Base

class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False)
    email = Column(String(255), nullable=False, unique=True, index=True)
    password = Column(String(255), nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)  

    # __table_args__ = (
    #     Index("idx_user_email", "email"),
    # )
    
class RegisteredNumber(Base):
    __tablename__ = "registered_number"

    id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    number = Column(Text, primary_key=True)
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # __table_args__ = (
    #     Index("idx_registered_number", "number"),
    # )
    
class RegisteredShopifyStore(Base):
    __tablename__ = "registered_shopify_store"

    id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    store_name = Column(Text, primary_key=True, nullable=False)
    access_token = Column(Text, unique=True, nullable=False)
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # __table_args__ = (
    #     Index("idx_registered_store", "store_name"),
    # )