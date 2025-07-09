from fastapi import APIRouter, WebSocket
from app.controllers import chat_controller_v2
from app.config.logger import get_logger

logger = get_logger("API Logger")
router = APIRouter()

@router.get("/")
async def hello_chat():
    logger.info("Chat route accessed")
    return {
        "status": "success",
        "message": "User can send chat."
        }

@router.websocket("/ws/query")
async def query_analysis(websocket: WebSocket):
    return await chat_controller_v2.websocket_endpoint(websocket)