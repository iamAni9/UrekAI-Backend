from fastapi import WebSocket
import asyncio
import re
import json
import random
from pydantic import BaseModel
from app.config.postgres import database as db
from app.config.constants import MAX_RETRY_ATTEMPTS, INITIAL_RETRY_DELAY
from app.config.logger import get_logger
from app.config.prompts_v2 import QUERY_CLASSIFICATION_PROMPT, SQL_GENERATION_PROMPT, GENERATE_ANALYSIS_FOR_USER_QUERY_PROMPT, ANALYSIS_EVAL_PROMPT
from typing import Dict, List, Optional, Any
from app.models.gemini import query_ai

logger = get_logger("API Logger")

class QueryClassification(BaseModel):
    type: str 
    message: str
    user_message: str
    
class QueryRequest(BaseModel):
    userQuery: str
    immediate: Optional[bool] = False

class QueryResponse(BaseModel):
    success: bool
    data: Optional[Dict[str, Any]] = None
    message: Optional[str] = None
    error: Optional[str] = None

async def send_socket_message(websocket: WebSocket, type: str, content: any):
    await websocket.send_json({"type": type, "content": content})
    
async def sleep_ms(ms: int):
    """Sleep for milliseconds"""
    await asyncio.sleep(ms / 1000.0)

async def retry_operation(
    operation,
    operation_name: str,
    max_retries: int = MAX_RETRY_ATTEMPTS,
    initial_delay: int = INITIAL_RETRY_DELAY
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

async def fetch_user_metadata(user_id: str) -> Optional[List[Dict[str, Any]]]:
    try:
        query = """
            SELECT table_name, file_name, schema, column_insights
            FROM analysis_data 
            WHERE id= :user_id
        """
        result = await db.fetch_all(query, {"user_id": user_id})
        logger.info(f"Successfully fetched user's metadata with id={user_id}")
    except Exception as e:
        logger.error(f"Issue while fetching user's metadata, userid={user_id}: {e}")
        result = None
    finally:
        return [dict(record) for record in result] if result else None

def flatten_and_format(data: Any, indent: int = 0) -> str:
    output = ''
    indent_str = '  ' * indent
    
    if isinstance(data, dict):
        for key, value in data.items():
            if isinstance(value, (dict, list)):
                output += f'{indent_str}{key}:\n{flatten_and_format(value, indent + 1)}\n'
            else:
                output += f'{indent_str}{key}: {value}\n'
    elif isinstance(data, list):
        for item in data:
            if isinstance(item, (dict, list)):
                output += f'{indent_str}- {flatten_and_format(item, indent + 1)}\n'
            else:
                output += f'{indent_str}- {item}\n'
    else:
        output += f'{indent_str}{data}\n'
    
    return output.strip()

async def classify_query(user_query: str) -> QueryClassification:   

    system_prompt = QUERY_CLASSIFICATION_PROMPT["systemPrompt"]
    user_prompt = f'Classify this query: "{user_query}"'
    
    async def classify_operation():
        classification_response = await query_ai(user_prompt, system_prompt)
        
        json_str = clean_json_string(str(classification_response))
        
        try:
            parsed = json.loads(json_str)
            logger.info(f"Parsed Classification Query: {parsed}")
            # Validating the response structure
            if not parsed.get('type') or not parsed.get('message'):
                raise ValueError('Invalid classification response structure')
            
            return QueryClassification(**parsed)
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f'Failed to parse classification response: {json_str}, {e}')
            # Return default classification
            return QueryClassification(
                type='general',
                message='Unable to parse classification, defaulting to general query'
            )
    
    return await retry_operation(classify_operation, 'Query Classification')

async def generate_sql_queries(
    user_query: str, 
    classification_type: str, 
    structured_metadata: str, 
    llm_suggestions: Any
) -> str:
        
    system_prompt = SQL_GENERATION_PROMPT["systemPrompt"]
    user_prompt = f"""
        {SQL_GENERATION_PROMPT["userPrompt"]}

        Table Metadata:
        {structured_metadata}

        Classification Type:
        {classification_type}

        User Question:
        {user_query}

        LLM suggestions:
        {llm_suggestions}
    """
    
    async def generate_operation():
        return await query_ai(user_prompt, system_prompt)
    
    return await retry_operation(generate_operation, 'SQL Multi-Query Generation')

def parse_generated_queries(generated_queries_raw: Any) -> Optional[List[Dict[str, Any]]]:
    """Parse generated SQL queries"""
    try:
        cleaned = (str(generated_queries_raw)
                  .replace('```json\n', '')
                  .replace('```', '')
                  .replace('\n', '')
                  .strip())
        
        queries = json.loads(cleaned)
        
        if isinstance(queries, dict) and queries.get("error"):
            print("Unsupported")
            return queries
        
        # logger.info(f"Cleaned SQL queries: {queries}")
        for q in queries:
            if not isinstance(q, dict) or "query" not in q:
                continue
            
            # Basic SQL validation
            if 'select' not in q['query'].lower():
                raise ValueError('Invalid SQL query: missing SELECT statement')
            
            # Adding LIMIT 100 if not present and not an aggregate query
            query_lower = q['query'].lower()
            if 'limit' not in query_lower and 'group by' not in query_lower:
                q['query'] = q['query'].rstrip(';') + ' LIMIT 100'
            
            # Adding error handling for ID lookups
            if 'where' in query_lower and 'id' in query_lower:
                q['query'] = q['query'].rstrip(';') + ' OR 1=0'
        
        return queries
    except (json.JSONDecodeError, ValueError) as e:
        logger.error(f'Failed to parse or validate LLM multi-query response: {generated_queries_raw}')
        return None
    
async def execute_query(sql_query: str) -> List[Dict[str, Any]]:
    async def query_operation():
        result = await db.fetch_all(sql_query)
        return [dict(row) for row in result]
    
    return await retry_operation(query_operation, 'SQL Query Execution')

async def execute_parsed_queries(queries_with_charts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    results = []
    for i, query_item in enumerate(queries_with_charts):
        sql_query = query_item.get('query')
        if not sql_query:
            continue
        try:
            query_results = await execute_query(sql_query)
            results.append({
                'query': sql_query,
                'results': query_results,
            })
        except Exception as err:
            logger.error(f"Error executing query {i+1}: {err}")
            results.append({
                'query': sql_query,
                'results': None,
                'error': 'Query execution failed',
            })
    
    return results

async def generate_analysis(query_results: str, user_query: str, classification_type: str) -> Dict[str, Any]:    
    system_prompt = GENERATE_ANALYSIS_FOR_USER_QUERY_PROMPT["systemPrompt"]
    user_prompt = f"""
        Context:
        - Query Results: {json.dumps(query_results)}
        - Original User Question: {user_query}
        - Query Classification Message: {classification_type}

        {GENERATE_ANALYSIS_FOR_USER_QUERY_PROMPT["userPrompt"]}
    """
    
    async def analysis_operation():
        analysis_response = await query_ai(user_prompt, system_prompt)
        dirty_string = str(analysis_response)
        
        try:
            # Try to extract JSON from code blocks
            import re
            match = re.search(r'```json\s*([\s\S]*?)\s*```', dirty_string)
            extracted_json = match.group(1) if match else dirty_string
            return json.loads(extracted_json)
        except json.JSONDecodeError:
            # Try to repair JSON
            logger.warning('Standard JSON parsing failed, attempting to repair...')
            try:
                # Simple JSON repair (you might want to use a library like jsonrepair if available)
                cleaned = (dirty_string
                          .replace('```json', '')
                          .replace('```', '')
                          .replace('\\"', '"')
                          .strip())
                return json.loads(cleaned)
            except json.JSONDecodeError:
                logger.error(f'Failed to parse analysis response: {dirty_string}')
                raise Exception('Failed to parse analysis response after attempting repair')
    
    return await retry_operation(analysis_operation, 'LLM Analysis Generation')

async def analysis_evaluation(analysis_data: Any, query_results: str, user_query: str, llm_suggestions) -> Dict[str, Any]:
    system_prompt = ANALYSIS_EVAL_PROMPT["systemPrompt"]
    user_prompt = f"""
        - Original User Question: {user_query}
        - Query and their Results: {query_results}
        - Analysis over data: {analysis_data}
        - LLM suggestion from past evaluation: {llm_suggestions}
    """
    
    async def eval_operation():
        analysis_response = await query_ai(user_prompt, system_prompt)
        
        # Handle different response types
        if isinstance(analysis_response, bytes):
            raw_text = analysis_response.decode('utf-8')
        elif isinstance(analysis_response, str):
            raw_text = analysis_response
        elif isinstance(analysis_response, dict):
            logger.info(f"Analysis Response is already an object: {analysis_response}")
            return analysis_response
        else:
            raise Exception('Unexpected analysis response type')
        
        # Clean extra markdown code blocks
        cleaned = (raw_text
                  .replace('```json\n', '')
                  .replace('```json', '')
                  .replace('```', '')
                  .replace('\\"', '"')
                  .strip())
        
        try:
            logger.info(f"Cleaned Response: {cleaned}")
            return json.loads(cleaned)
        except json.JSONDecodeError:
            logger.error(f"Failed to parse analysis response: {cleaned}")
            raise Exception('Failed to parse analysis response')
    
    return await retry_operation(eval_operation, 'LLM Answer Evaluation')