import json
import asyncio
import random
from typing import Dict, List, Optional, Any
from pydantic import BaseModel
from fastapi import HTTPException, Request, Response
from fastapi.responses import JSONResponse

from app.config.logger import get_logger
from app.config.database_config.postgres import database as db
from app.ai.gemini import query_ai
from app.utils.uniqueId import str_to_uuid
from app.config.constants import MAX_RETRY_ATTEMPTS, MAX_EVAL_ITERATION, INITIAL_RETRY_DELAY


class QueryClassification(BaseModel):
    type: str  # 'general' | 'data_no_chart' | 'data_with_chart'
    message: str

class QueryRequest(BaseModel):
    userQuery: str
    immediate: Optional[bool] = False

class QueryResponse(BaseModel):
    success: bool
    data: Optional[Dict[str, Any]] = None
    message: Optional[str] = None
    error: Optional[str] = None

logger = get_logger("API Logger")

# Helper functions
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
    """Clean JSON string for parsing"""
    # Extract JSON from code blocks
    import re
    json_match = re.search(r'```(?:json)?\s*(\{[\s\S]*?\})\s*```', json_str)
    if json_match:
        json_str = json_match.group(1)
    
    # Clean the JSON string
    json_str = (json_str
                .replace('\n', ' ')
                .replace('\r', ' ')
                .replace('  ', ' ')
                .strip())
    
    # Add quotes to unquoted property names
    json_str = re.sub(r'([{,]\s*)([a-zA-Z_][a-zA-Z0-9_]*)(\s*:)', r'\1"\2"\3', json_str)
    
    return json_str

async def classify_query(user_query: str) -> QueryClassification:
    """Classify user query"""
    from app.config.prompts.prompts import QUERY_CLASSIFICATION_PROMPT
    
    system_prompt = QUERY_CLASSIFICATION_PROMPT["systemPrompt"]
    user_prompt = f'Classify this query: "{user_query}"'
    
    async def classify_operation():
        classification_response = await query_ai(user_prompt, system_prompt)
        
        json_str = clean_json_string(str(classification_response))
        
        try:
            parsed = json.loads(json_str)
            logger.info(f"Parsed Classification Query: {parsed}")
            # Validate the response structure
            if not parsed.get('type') or not parsed.get('message'):
                raise ValueError('Invalid classification response structure')
            
            # Validate the type value
            # if parsed['type'] not in ['general', 'data_query_text', 'data_query_chart', 'data_query_combined', 'unsupported']:
            #     raise ValueError('Invalid classification type')
            
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
    """Generate SQL queries"""
    from app.config.prompts.prompts import SQL_GENERATION_PROMPT
    
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

async def generate_analysis(query_results: str, user_query: str, classification_type: str) -> Dict[str, Any]:
    """Generate analysis from query results"""
    from app.config.prompts.prompts import GENERATE_ANALYSIS_FOR_USER_QUERY_PROMPT
    
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
    """Evaluate analysis quality"""
    from app.config.prompts.prompts import ANALYSIS_EVAL_PROMPT
    
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

async def fetch_user_files(user_id: str) -> Optional[Dict[str, Any]]:
    """Fetch user files from database"""
    try:
        query = """
            SELECT file_name
            FROM analysis_data 
            WHERE id= :user_id
        """
        result = await db.fetch_all(query, {"user_id": user_id})
        logger.info(f"Checked user's files with id={user_id} successfully")
    except Exception as e:
        logger.error(f"Issue while checking user's file, userid={user_id}: {e}")
    finally:
        return {"rows": result} if result else None

async def fetch_user_metadata(user_id: str) -> Optional[List[Dict[str, Any]]]:
    """Fetch user metadata from database"""
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
    """Flatten and format data structure"""
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
        
        logger.info(f"Cleaned SQL queries: {queries}")
        for q in queries:
            if not q.get('query'):
                raise ValueError('Invalid query format')
            
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
    """Execute SQL query"""
    async def query_operation():
        result = await db.fetch_all(sql_query)
        return [dict(row) for row in result]
    
    return await retry_operation(query_operation, 'SQL Query Execution')

async def execute_parsed_queries(queries_with_charts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Execute parsed queries"""
    results = []
    for i, query_item in enumerate(queries_with_charts):
        sql_query = query_item['query']
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

# Main endpoint function
async def response_user_query(request: Request, response: Response) -> JSONResponse:
    try:
        body = await request.json()
        user_query = body.get("userQuery")
        is_immediate = body.get("immediate", False)
        
        if not user_query:
            raise HTTPException(status_code=400, detail="userQuery is required")
        
        user = request.session.get("user")
        if not user:
            raise HTTPException(status_code=401, detail="Unauthorized")
        
        user_id = str_to_uuid(user.get("id"))
        logger.info(f"Processing query request for user: {user_id}, query: {user_query}")
        
        # 1. Classify user query
        classification = await classify_query(user_query)
        logger.info(f"Query classification: {classification.dict()}")
        
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
        
        # Check if user has files
        user_files = await fetch_user_files(user_id)
        if not user_files:
            raise HTTPException(status_code=404, detail="Add files first")
        
        # 2. Fetch metadata
        user_metadata = await fetch_user_metadata(user_id)
        if not user_metadata:
            raise HTTPException(
                status_code=404, 
                detail="Either user not exist or data is not present"
            )
        
        structured_metadata = flatten_and_format(user_metadata)
        # logger.info(f"Metadata: {structured_metadata}")
        
        # 3. Generate and evaluate queries with retry
        analysis_results = None
        llm_suggestions = None
        
        for attempt in range(1, MAX_EVAL_ITERATION + 1):
            logger.info(f"Attempt {attempt} to generate and evaluate SQL queries")
            
            generated_queries_raw = await generate_sql_queries(
                user_query, classification.type, structured_metadata, llm_suggestions
            )      
                              
            parsed_queries = parse_generated_queries(generated_queries_raw)
            if not parsed_queries:
                logger.warning('Failed to parse generated queries')
                continue
            
            if isinstance(parsed_queries, dict) and parsed_queries.get("error"):
                logger.error("Unsupported query based on data available in uploaded files.")
                logger.info(parsed_queries)
                return JSONResponse(
                    status_code=200,
                    content={
                        "success": True,
                        "data": {
                            "type": "Unsupported",
                            "reason": parsed_queries['unsupported_reason'],
                            "suggestions": parsed_queries['suggestions']
                        }
                    }
                )
                
            logger.info(f"Generated queries: {parsed_queries}")
            
            query_results = await execute_parsed_queries(parsed_queries)
            logger.info("Query executed successfully")
            
            if query_results and query_results[0] and query_results[0].get('results'):
                logger.info("Executing in loop")
                structured_result = '\n'.join([
                    f"Query {i + 1}:\n{val['query']}\nResults:\n{json.dumps(val['results'], indent=2, default=str)}\n"
                    if val.get('results') else
                    f"Query {i + 1}:\n{val['query']}\nError:\n{val.get('error', 'No results and no error message.')}\n"
                    for i, val in enumerate(query_results)
                ])
                logger.info(f"Queries and results: {structured_result}")
                
                analysis_results = await generate_analysis(structured_result, user_query, classification.message)
                
                if not analysis_results:
                    logger.warning('Generated analysis failed evaluation')
                    continue
                
                if is_immediate:
                    logger.info("Immediate response is required.")
                    return JSONResponse(
                        status_code=200,
                        content={"success": True, "data": analysis_results}
                    )
                
                evaluation = await analysis_evaluation(
                    json.dumps(analysis_results), structured_result, user_query, llm_suggestions
                )
                
                if evaluation.get('good_result') == 'Yes':
                    logger.info("The evaluation is GOOD to send")
                    break
                
                llm_suggestions = evaluation.get('required')
        
        if not analysis_results:
            raise HTTPException(
                status_code=500,
                detail="Failed to generate good analysis after multiple attempts"
            )
        
        # logger.info(f"Analysis summary: {analysis_results['analysis']}")
        # logger.info(f"Table data: {analysis_results['table_data']}")
        # logger.info(f"Graph data: {analysis_results['graph_data']}")
        return JSONResponse(
            status_code=200,
            content={"success": True, "data": analysis_results}
        )
        
    except HTTPException:
        raise
    except Exception as error:
        logger.error(f"Error in response_user_query: {error}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "data": "An error occured while generating analysis. Try again."}
        )