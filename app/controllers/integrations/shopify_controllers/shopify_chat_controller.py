from fastapi import Request
from fastapi.responses import JSONResponse
from app.config.logger import get_logger
from app.utils.db_utils import get_token_from_db
from app.helper.query_analysis_helper import classify_query

logger = get_logger("Shopify Chat Controller")

async def response_shopify_query(request: Request):
    try:
        body = await request.json()
        logger.info(f"Received Shopify query request body: {body}")
        
        shop_name = body.get("shop_name")
        user_query = body.get("query")
        
        if not shop_name or not user_query:
            return {"error": "Missing shop_name or query in request body"}, 400
        
        classification = await classify_query(user_query)
        
        if classification.type in ['general', 'unsupported']:
             return JSONResponse(
                status_code=200,
                content={
                    "success": True,
                    "data": {
                        "type": classification.type,
                        "message": classification.message,
                    }
                }
            )
        
        # Check if the access token exists for the given shop
        access_token_exists = await get_token_from_db(shop_name, logger)
        if not access_token_exists:
            return {"error": f"No access token found for shop: {shop_name}"}, 404
        
        shopifyQL = await generate_shopifyQL(user_query)
        response_data = {
            "shop_name": shop_name,
            "query": user_query,
            "response": f"Processed query for shop {shop_name}: {user_query}"
        }
        
        logger.info(f"Shopify query response data: {response_data}")
        return response_data
    
    except Exception as e:
        logger.error(f"Error processing Shopify query: {str(e)}")
        return {"error": "Internal server error"}, 500