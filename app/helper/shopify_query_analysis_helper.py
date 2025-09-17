from app.helper.query_analysis_helper import *
from app.config.prompts.shopify_prompts import SHOPIFY_GRAPHQL_GENERATION_PROMPT
from app.config.logger import get_logger
from app.config.settings import settings
import httpx
import json

logger = get_logger("Shopify Logger")

async def generate_shopifyQL(user_query: str, llm_suggestions: Any) -> str:
    
    system_prompt = SHOPIFY_GRAPHQL_GENERATION_PROMPT["systemPrompt"]
    user_prompt = f"""
        {SHOPIFY_GRAPHQL_GENERATION_PROMPT["userPrompt"]}

        User Question:
        {user_query}

        LLM suggestions:
        {llm_suggestions}
    """
    
    async def generate_operation():
        return await query_ai(user_prompt, system_prompt)
    
    return await retry_operation(generate_operation, 'ShopifyQL Query Generation', logger=logger)

def parse_generated_shopify_queries(generated_queries_raw: Any) -> Optional[List[Dict[str, Any]]]:
    try:
        cleaned = (str(generated_queries_raw)
                  .replace('```json\n', '')
                  .replace('```', '')
                  .replace('\n', '')
                  .strip())
        
        queries = json.loads(cleaned)
        return queries
    except (json.JSONDecodeError, ValueError) as e:
        logger.error(f'Failed to parse LLM generated Shopify queries: {generated_queries_raw}')
        return None 
    
async def execute_shopify_queries(shopify_queries: List[Dict[str, Any]], shop: str, access_token: str) -> List[Dict[str, Any]]:
    SHOPIFY_API_URL = f"https://{shop}/admin/api/2025-01/graphql.json"
    results = []
    headers = {
        "Content-Type": "application/json",
        "X-Shopify-Access-Token": access_token,
    }
    timeout = httpx.Timeout(30.0, connect=10.0)
    transport = httpx.AsyncHTTPTransport(retries=3)
    async with httpx.AsyncClient(timeout=timeout, transport=transport) as client:
        for idx, item in enumerate(shopify_queries, start=1):
            gql_query = item.get("query")
            logger.info(f"Executing GraphQL query #{idx}")
            if not gql_query:
                logger.warning(f"Skipping empty query at index {idx}")
                continue

            payload = {"query": gql_query}
            logger.debug(f"Payload for query #{idx}: {payload}")

            try:
                resp = await client.post(SHOPIFY_API_URL, headers=headers, json=payload)
                resp.raise_for_status()
                data = resp.json()
                logger.info(f"Response for query #{idx}: {data}")
                if "errors" in data:
                    logger.error(f"GraphQL errors in query #{idx}: {data['errors']}")
                    results.append({
                        "query": gql_query,
                        "data": None,
                        "errors": data["errors"]
                    })
                else:
                    results.append({
                        "query": gql_query,
                        "data": data.get("data"),
                        "errors": None
                    })

            except httpx.TimeoutException as e:
                logger.error(f"Timeout on query #{idx}: {e}")
                results.append({
                    "query": gql_query,
                    "data": None,
                    "errors": [{"message": str(e), "type": "TimeoutException"}]
                })
            except httpx.HTTPStatusError as e:
                err_text = e.response.text
                status = e.response.status_code
                logger.error(f"HTTP error on query #{idx}: {status} {err_text}")
                results.append({
                    "query": gql_query,
                    "data": None,
                    "errors": [{"message": err_text, "status": status, "type": "HTTPStatusError"}]
                })
            except Exception as e:
                logger.error(f"Unexpected error on query #{idx}: {e}")
                results.append({
                    "query": gql_query,
                    "data": None,
                    "errors": [{"message": str(e), "type": "Exception"}]
                })

    return results