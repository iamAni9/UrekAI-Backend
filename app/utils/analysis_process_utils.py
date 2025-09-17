import asyncio
import random
import re
from app.config.constants import MAX_RETRY_ATTEMPTS, INITIAL_RETRY_DELAY

async def sleep_ms(ms: int):
    """Sleep for milliseconds"""
    await asyncio.sleep(ms / 1000.0)

async def retry_operation(
    operation,
    operation_name: str,
    max_retries: int = MAX_RETRY_ATTEMPTS,
    initial_delay: int = INITIAL_RETRY_DELAY,
    logger = None
):
    """Retry operation with exponential backoff"""
    last_error = None
    
    for attempt in range(1, max_retries + 1):
        try:
            return await operation()
        except Exception as error:
            last_error = error
            # Exponential backoff + jitter
            delay = min(
                initial_delay * (2 ** (attempt - 1)) + random.randint(0, 1000),
                30000  # Max 30s delay
            )
            
            logger.warning(f"{operation_name} failed (attempt {attempt}/{max_retries}): {str(error)}")
            
            if attempt < max_retries:
                logger.info(f"Retrying {operation_name} in {delay}ms...")
                await sleep_ms(delay)
    
    raise Exception(f"{operation_name} failed after {max_retries} attempts. Last error: {str(last_error)}")

def clean_json_string(json_str: str) -> str:
    json_match = re.search(r'```(?:json)?\s*(\{[\s\S]*?\})\s*```', json_str)
    
    if json_match:
        json_str = json_match.group(1)
    
    
    json_str = (json_str
                .replace('\n', ' ')
                .replace('\r', ' ')
                .replace('  ', ' ')
                .strip())
    
    # Adding quotes to unquoted property names
    json_str = re.sub(r'([{,]\s*)([a-zA-Z_][a-zA-Z0-9_]*)(\s*:)', r'\1"\2"\3', json_str)
    
    return json_str