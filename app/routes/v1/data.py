from fastapi import APIRouter, Request, File, UploadFile
from app.controllers import data_controller
from typing import List
from app.config.logger import get_logger

logger = get_logger("API Logger")
router = APIRouter()

@router.get("/")
async def hello_data():
    logger.info("Data route accessed")
    return {
        "status": "success",
        "message": "You can upload data."
        }
    
@router.post("/upload-file")
async def upload_file(request: Request, files: List[UploadFile] = File(...)):
    return await data_controller.file_upload_handler(request, files)

@router.get("/upload-status")
async def check_upload_status(request: Request):
    return await data_controller.upload_status_check(request)