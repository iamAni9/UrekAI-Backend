from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional

class DataSourceResponse(BaseModel):
    """Response model for a single data source."""
    source_id: str = Field(..., description="Unique identifier for the data source.")
    source_name: str = Field(..., description="Name of the data source file.")
    status: str = Field(..., description="Processing status of the data source.")
    created_at: str = Field(..., description="Timestamp of creation.")

class AllDataSourcesResponse(BaseModel):
    """Response model for a list of all data sources for a user."""
    sources: List[DataSourceResponse]

class SchemaResponse(BaseModel):
    """Response model for the schema of a data source."""
    source_id: str
    schema: Dict[str, Any]

class UploadResponse(BaseModel):
    """Response model for a successful file upload."""
    job_id: str
    filename: str
    message: str