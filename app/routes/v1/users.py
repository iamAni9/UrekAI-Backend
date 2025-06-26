from fastapi import APIRouter, Request, Response
from app.controllers import user_controller
from app.config.logger import logger

router = APIRouter()

@router.get("/")
async def hello_user():
    logger.info("Home route accessed")
    return {
        "status": "success",
        "message": "Welcome user."
        }

@router.post("/sign-in")
async def sign_in(request: Request, response: Response):
    return await user_controller.sign_in_user(request, response)

@router.post("/sign-up")
async def sign_up(request: Request, response: Response):
    return await user_controller.sign_up_user(request, response)

@router.get("/check-user")
async def check_user(request: Request):
    return await user_controller.check_user(request)

# @router.get("/get-user-data")
# async def get_user_data(request: Request):
#     return await user_controller.get_user_data(request)

@router.post("/auth/google")
async def google_auth(request: Request):
    return await user_controller.google_auth(request)

@router.post("/log-out")
async def log_out(request: Request):
    return await user_controller.sign_out_user(request)
