from fastapi import APIRouter, Request, BackgroundTasks, Query
from app.config.logger import get_logger
from app.controllers.integrations import whatsapp_controller
from app.controllers.integrations.shopify_controllers import shopify_auth_controller, shopify_chat_controller

logger = get_logger("API Logger")
router = APIRouter()

@router.get("/")
async def hello_integration():
    logger.info("Integration route accessed")
    return {
        "status": "success",
        "message": "You can access integrated facilities."
        }
    
@router.api_route("/whatsapp", methods=["GET", "POST"])
async def whatsapp_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
    hub_verify_token: str = Query(None, alias="hub.verify_token")
):
    """
    Endpoint to handle Meta WhatsApp webhooks.
    - GET: For webhook verification.
    - POST: For incoming message notifications.
    """
    return await whatsapp_controller.whatsapp_handler_meta(
        request,
        background_tasks,
        hub_mode,
        hub_challenge,
        hub_verify_token
    )

@router.get("/auth/shopify", tags=["Shopify Auth"])
async def initiate_shopify_auth(request: Request, shop: str, host: str):
    return await shopify_auth_controller.shopify_auth_redirect(request, shop, host)

@router.get("/auth/shopify/callback", tags=["Shopify Auth"])
async def shopify_auth_callback(request: Request):
    return await shopify_auth_controller.shopify_auth_callback(request)

@router.post("/shopify/query")
async def shopify_query_analysis(request: Request):
    return await shopify_chat_controller.response_shopify_query(request)