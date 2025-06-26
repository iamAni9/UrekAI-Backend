from fastapi import APIRouter, Request, Response
from app.controllers import chat_controller
from app.config.logger import logger

router = APIRouter()

@router.get("/")
async def hello_chat():
    logger.info("Chat route accessed")
    return {
        "status": "success",
        "message": "User can send chat."
        }

@router.post("/query")
async def sign_in(request: Request, response: Response):
    return await chat_controller.response_user_query(request, response)