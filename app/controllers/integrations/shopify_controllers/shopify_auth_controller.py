from fastapi import Request
from fastapi.responses import RedirectResponse
from app.config.settings import settings
import hmac
from app.utils.db_utils import save_token_to_db
from app.config.logger import get_logger
import hashlib
import httpx

logger = get_logger("Shopify Auth Controller")
            
async def shopify_auth_redirect(request: Request, shop: str, host: str):
    try:
        logger.info(f"Initiating Shopify auth for shop: {shop} with host: {host}")
        if not shop:
            return {"error": "Missing shop parameter"}, 400

        # Check if request is from embedded iframe
        embedded = request.query_params.get('embedded', '0')
        
        redirect_uri = f"{request.base_url}v2/api/integration/auth/shopify/callback"
        
        # Add state parameter for security
        state = f"{host}|{embedded}"
        
        permission_url = (
            f"https://{shop}/admin/oauth/authorize?"
            f"client_id={settings.SHOPIFY_CLIENT_ID}&"
            f"scope={settings.SHOPIFY_SCOPES}&"
            f"redirect_uri={redirect_uri}&"
            f"state={state}"
        )

        logger.info(f"permission_url: {permission_url}")
        
        # Create response with CSP headers
        response = RedirectResponse(url=permission_url)
        response.headers["Content-Security-Policy"] = f"frame-ancestors https://{shop} https://admin.shopify.com;"
        
        return response
    except Exception as e:
        logger.error(f"Error initiating Shopify auth: {str(e)}")
        return {"error": "Internal server error"}, 500

def verify_shopify_hmac(params: dict, secret: str) -> bool:
    hmac_from_shopify = params.pop("hmac", None)
    
    sorted_params = "&".join(
        f"{key}={value}" for key, value in sorted(params.items())
    )
    
    generated_hmac = hmac.new(
        secret.encode("utf-8"),
        sorted_params.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    
    logger.info(f"Generated HMAC: {generated_hmac}, HMAC from Shopify: {hmac_from_shopify}")
    return hmac.compare_digest(generated_hmac, hmac_from_shopify)

async def shopify_auth_callback(request: Request):
    params = dict(request.query_params)
    # logger.info(f"The parameters - {params}")
    code = params.get('code')
    hmac_value = params.get('hmac')
    host = params.get('host')
    shop = params.get('shop')
    state = params.get('state')
    timestamp = params.get('timestamp')
    
    if not all([code, hmac_value, host, shop, state, timestamp]):
        return {"error": "Missing some parameters"}, 400
    
    # Parsing state to get host and embedded status
    state_parts = state.split('|') if state else []
    host = state_parts[0] if len(state_parts) > 0 else ''
    embedded = state_parts[1] if len(state_parts) > 1 else '0'
    
    if not shop or not code:
        return {"error": "Missing shop or code parameter"}, 400

    if not verify_shopify_hmac(params.copy(), settings.SHOPIFY_CLIENT_SECRET):
        return {"error": "Invalid HMAC signature"}, 403

    access_token = None
    try:
        # 1. Preparing the request to Shopify's token endpoint
        token_url = f"https://{shop}/admin/oauth/access_token"
        payload = {
            "client_id": settings.SHOPIFY_CLIENT_ID,
            "client_secret": settings.SHOPIFY_CLIENT_SECRET,
            "code": code,
        }
        
        # 2. Making the POST request for access token
        async with httpx.AsyncClient() as client:
            response = await client.post(token_url, json=payload)
            response.raise_for_status() # Raise an exception for HTTP errors
            
            # 3. Processing the response
            data = response.json()
            access_token = data.get('access_token')
            if not access_token:
                return {"error": "Failed to obtain access token"}, 400
            logger.info(f"Successfully obtained access token for {shop}")
            
            shop_url = f"https://{shop}/admin/api/2023-01/shop.json"
            shop_res = await client.get(
                shop_url,
                headers={"X-Shopify-Access-Token": access_token},
            )
            shop_res.raise_for_status()
            shop_data = shop_res.json().get("shop", {})
            logger.info(f"Shop data retrieved: {shop_data}")
            email = shop_data.get("email")
            owner_name = shop_data.get("shop_owner")
            shop_name = shop_data.get("myshopify_domain")
            
            # 4. Saving the token and creating user if not exists
            await save_token_to_db(shop_name, access_token, email, owner_name, logger)

    except httpx.HTTPStatusError as e:
        logger.error(f"Error exchanging code for token: {e.response.text}")
        return {"error": "Could not retrieve access token from Shopify."}, 500
    except Exception as e:
        logger.error(f"An unexpected error occurred during token exchange: {str(e)}")
        return {"error": "Internal server error during token exchange."}, 500

    # Redirect with proper CSP headers
    final_redirect_url = f"{settings.APP_URL}/shopify/dashboard?shop={shop}&host={host}&embedded={embedded}"
    logger.info(f"Redirecting to frontend dashboard at: {final_redirect_url}")
    
    response = RedirectResponse(url=final_redirect_url)
    response.headers["Content-Security-Policy"] = f"frame-ancestors https://{shop} https://admin.shopify.com;"
    
    return response