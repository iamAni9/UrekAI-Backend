from fastapi import APIRouter, Request, Response
from app.controllers import chat_controller
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

@router.post("/query")
async def query_analysis(request: Request, response: Response):
    return await chat_controller.response_user_query(request, response)