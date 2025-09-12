from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

class ChatRequest(BaseModel):
    """Request model for a new chat message."""
    source_id: str = Field(..., description="The ID of the data source to chat with.")
    query: str = Field(..., description="The user's question or message.")
    chat_history: Optional[List[Dict[str, Any]]] = Field(None, description="Previous conversation history.")

class ChatResponse(BaseModel):
    """Response model for a chat message reply."""
    answer: str = Field(..., description="The AI-generated answer.")
    visualization_spec: Optional[Dict[str, Any]] = Field(None, description="Vega-Lite spec for chart visualization.")
    data: Optional[List[Dict[str, Any]]] = Field(None, description="The data used for the visualization.")
    query_result: Optional[List[Dict[str, Any]]] = Field(None, description="The raw result from the data query.")