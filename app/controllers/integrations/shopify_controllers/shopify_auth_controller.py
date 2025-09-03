from fastapi import Request
from fastapi.responses import RedirectResponse
from app.config.settings import settings
import httpx
import hmac
from urllib.parse import urlencode
from app.config.logger import get_logger
import hashlib

logger = get_logger("Shopify Auth Controller")
            
#  https://admin.shopify.com/store/urekai-testing-store/oauth/authorize?client_id=c570ea3494d0fe3360cc09582a3fa799&scope=read_products,write_products,read_orders&redirect_uri=https://ca739b8d07fd.ngrok-free.app//v2/api/integration/auth/shopify/callback&state=YWRtaW4uc2hvcGlmeS5jb20vc3RvcmUvdXJla2FpLXRlc3Rpbmctc3RvcmU

APP_URL = "http://192.168.56.1:5173"

async def shopify_auth_redirect(request: Request, shop: str, host: str):
    try:
        logger.info(f"Initiating Shopify auth for shop: {shop} with host: {host}")
        if not shop:
            return {"error": "Missing shop parameter"}, 400

        redirect_uri = f"{request.base_url}v2/api/integration/auth/shopify/callback"
        
        # The permission URL for the merchant to grant access
        permission_url = (
            f"https://{shop}/admin/oauth/authorize?"
            f"client_id={settings.SHOPIFY_CLIENT_ID}&"
            f"scope={settings.SHOPIFY_SCOPES}&"
            f"redirect_uri={redirect_uri}&"
            f"state={host}"
        )

        logger.info(f"permission_url: {permission_url}")
        # Redirect the merchant to the permission URL
        return RedirectResponse(url=permission_url)
    except Exception as e:
        logger.error(f"Error initiating Shopify auth: {str(e)}")
        return {"error": "Internal server error"}, 500

def verify_hmac(params: dict, secret: str) -> bool:
    """Verify the HMAC signature from Shopify."""
    hmac_from_shopify = params.pop('hmac', '')
    
    # Parameters are sorted lexicographically to create the message
    sorted_params = urlencode(sorted(params.items()))
    
    # Calculate our HMAC digest
    digest = hmac.new(secret.encode('utf-8'), sorted_params.encode('utf-8'), hashlib.sha256).hexdigest()
    
    return hmac.compare_digest(digest, hmac_from_shopify)

async def shopify_auth_callback(request: Request):
    """
    Endpoint to handle the callback from Shopify after authorization.
    This is where we exchange the authorization code for a permanent access token.
    """
    params = dict(request.query_params)
    shop = params.get('shop')
    code = params.get('code')
    host = params.get('state')
    
    if not shop or not code:
        return {"error": "Missing shop or code parameter"}, 400

    # 1. Verifying the HMAC signature to ensure the request is from Shopify
    if not verify_hmac(params.copy(), settings.SHOPIFY_CLIENT_SECRET):
        return {"error": "Invalid HMAC signature"}, 403

    # 2. Exchanging the authorization code for an access token
    token_url = f"https://{shop}/admin/oauth/access_token"
    payload = {
        "client_id": settings.SHOPIFY_CLIENT_ID,
        "client_secret": settings.SHOPIFY_CLIENT_SECRET,
        "code": code,
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(token_url, json=payload)
            response.raise_for_status()
            result = response.json()
            access_token = result.get("access_token")

            # **IMPORTANT**: Securely store the access_token and shop name
            # in your database, associated with the merchant/user.
            # This token is used to make all future API requests for this shop.
            # For this example, we'll just log it.
            print(f"Access Token for {shop}: {access_token}")

            # # Store shop in session to be used by the frontend later
            # request.session['shopify_shop'] = shop

        except httpx.HTTPStatusError as e:
            print(f"Error exchanging token: {e.response.text}")
            return {"error": "Could not retrieve access token"}, 500

    # 3. Redirecting the user back to the React app's dashboard page
    # The frontend will now be loaded inside the Shopify Admin iframe.
    final_redirect_url = f"{settings.APP_URL}/shopify/dashboard?shop={shop}&host={host}"
    logger.info(f"Redirecting to frontend dashboard at: {final_redirect_url}")
    return RedirectResponse(url=final_redirect_url)
