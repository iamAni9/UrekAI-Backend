from fastapi import Request
from fastapi.responses import RedirectResponse
from app.config.settings import settings
import hmac
from urllib.parse import parse_qsl, urlencode, quote
from app.config.logger import get_logger
import hashlib

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

def verify_hmac_from_raw_query(raw_query: str, secret: str) -> bool:
    """
    Verify Shopify OAuth HMAC by removing only the 'hmac' pair
    from the raw, percent-encoded query string, preserving everything else.
    """
    # 1. Split on '&' to get each 'key=value' chunk (still percent-encoded)
    parts = raw_query.split('&')
    
    # 2. Filter out the 'hmac=' chunk but keep ordering & encoding intact
    filtered = [p for p in parts if not p.startswith('hmac=')]
    
    # 3. Rejoin to form the exact message Shopify used
    message = '&'.join(filtered)
    logger.info(f"HMAC message (raw): {message}")
    
    # 4. Compute hex-digest
    calculated_hmac = hmac.new(
        secret.encode('utf-8'),
        message.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    # 5. Extract Shopify's HMAC to compare
    #    Use parse_qsl just to grab the hmac; this does not affect the message
    hmac_from_shopify = dict(parse_qsl(raw_query, keep_blank_values=True)).get('hmac', '')
    logger.info(f"Calculated digest: {calculated_hmac}")
    logger.info(f"HMAC from Shopify: {hmac_from_shopify}")
    
    return hmac.compare_digest(calculated_hmac, hmac_from_shopify)

async def shopify_auth_callback(request: Request):
    params = dict(request.query_params)
    logger.info(f"The parameters - {params}")
    shop = params.get('shop')
    code = params.get('code')
    state = params.get('state', '')
    
    # Parse state to get host and embedded status
    state_parts = state.split('|') if state else []
    host = state_parts[0] if len(state_parts) > 0 else ''
    embedded = state_parts[1] if len(state_parts) > 1 else '0'
    
    if not shop or not code:
        return {"error": "Missing shop or code parameter"}, 400

    # Verify HMAC
    raw_query = request.url.query  # Use the raw query string
    if not verify_hmac_from_raw_query(raw_query, settings.SHOPIFY_CLIENT_SECRET):
        return {"error": "Invalid HMAC signature"}, 403

    # Exchange code for token (existing logic)
    # ... token exchange code ...

    # Redirect with proper CSP headers
    final_redirect_url = f"{settings.APP_URL}/shopify/dashboard?shop={shop}&host={host}&embedded={embedded}"
    logger.info(f"Redirecting to frontend dashboard at: {final_redirect_url}")
    
    response = RedirectResponse(url=final_redirect_url)
    response.headers["Content-Security-Policy"] = f"frame-ancestors https://{shop} https://admin.shopify.com;"
    
    return response