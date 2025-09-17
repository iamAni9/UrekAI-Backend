from fastapi import WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState
from app.utils.uniqueId import str_to_uuid
from app.config.logger import get_logger
from app.helper.query_analysis_helper import *
import asyncio
from app.config.constants import MAX_EVAL_ITERATION

logger = get_logger("API Logger")

async def process_user_query(websocket: WebSocket, user_query: str, user_id: str):
    try:
        # 1. Classify user query
        await send_socket_message(websocket, 'thinking', 'Classifying your query...')
        classification = await classify_query(user_query)
        
        if classification.type in ['general', 'unsupported']:
            await send_socket_message(websocket, classification.type, classification.message)
            return
        else:
            await send_socket_message(websocket, 'thinking', classification.user_message)
        
        await send_socket_message(websocket, 'thinking', 'Fetching necessary data...')
        user_metadata = await fetch_user_metadata(user_id)
        if not user_metadata:
            await send_socket_message(websocket, 'error', 'Data is not present. Upload it first')
            return
        
        structured_metadata = flatten_and_format(user_metadata)
        
        # 3. Generate and evaluate queries
        llm_suggestions = None
        analysis_results = None
        for attempt in range(1, MAX_EVAL_ITERATION + 1):
            await send_socket_message(websocket, 'thinking', f'Generating insights (Attempt {attempt})...')
            logger.info(f"Attempt {attempt} to generate and evaluate SQL queries")
            
            generated_queries_raw = await generate_sql_queries(
                user_query, classification.type, structured_metadata, llm_suggestions
            )
            
            # logger.info(f"Queries by LLM: {parse_generated_queries}")
            
            parsed_queries = parse_generated_queries(generated_queries_raw)
            if not parsed_queries:
                await send_socket_message(websocket, 'thinking', 'An error occur while parsing queries')
                logger.error('Failed to parse generated queries')
                continue 
            
            if isinstance(parsed_queries, dict) and parsed_queries.get("error"):
                await send_socket_message(websocket, 'unsupported', f"Data is not sufficient. {parsed_queries['suggestions'][0]}")
                logger.error("Unsupported query based on data available in uploaded files.")
                logger.info(parsed_queries)
                return
            
            logger.info(f"Generated queries: {parsed_queries}")
            await send_socket_message(websocket, 'thinking', parsed_queries[-1].get('user_message'))

            query_results = await execute_parsed_queries(parsed_queries)
            await send_socket_message(websocket, 'thinking', 'Executed SQL queries successfully.')
            logger.info("Query executed successfully")
            
            if query_results and query_results[0] and query_results[0].get('results'):
                logger.info("Executing in loop")
                
                structured_result_lines = []
                for i, val in enumerate(query_results):
                    if val.get('results'):
                        result_str = (
                            f"Query {i + 1}:\n{val['query']}\nResults:\n"
                            f"{json.dumps(val['results'], indent=2, default=str)}\n"
                        )
                        await send_socket_message(websocket, 'thinking', f"Result {i + 1}: {val['results']}")
                    else:
                        result_str = (
                            f"Query {i + 1}:\n{val['query']}\nError:\n"
                            f"{val.get('error', 'No results and no error message.')}\n"
                        )
                        await send_socket_message(websocket, 'thinking', f"Result {i + 1}: Gives error")

                    structured_result_lines.append(result_str)

                structured_result = "\n".join(structured_result_lines)
                logger.info(f"Queries and results: {structured_result}")
                await send_socket_message(websocket, 'thinking', 'Analyzing results...')
                
                analysis_results = await generate_analysis(structured_result, user_query, classification.message)

                if not analysis_results:
                    await send_socket_message(websocket, 'thinking', 'There is some issue occurred while generating analysis. Retrying...')
                    logger.warning('Generated analysis failed evaluation')
                    continue
                
                evaluation = await analysis_evaluation(
                    json.dumps(analysis_results), structured_result, user_query, llm_suggestions
                )
                
                if evaluation.get('good_result') == 'Yes':
                    await send_socket_message(websocket, 'analysis', analysis_results)
                    break

                llm_suggestions = evaluation.get('required')
                await send_socket_message(websocket, 'thinking', llm_suggestions)
                
        if not analysis_results:
            await send_socket_message(websocket, 'error', 'Failed to generate a good analysis after multiple attempts. Try again.')
            return
            
    except Exception as e:
        logger.error(f"Error processing query for user {user_id}: {e}")
        await send_socket_message(websocket, 'error', 'An unexpected error occurred.')

# Main entry point
async def websocket_endpoint(websocket):
    try:
            session = websocket.scope.get("session")
            if not session or "user" not in session:
                if websocket.client_state != WebSocketState.DISCONNECTED:
                    await websocket.close(code=4001, reason="Unauthorized")
                return None
            
            user = session.get("user")
            user_id = str_to_uuid(user.get("id"))
            if not user_id:
                if websocket.client_state != WebSocketState.DISCONNECTED:
                    await websocket.close(code=4001, reason="User ID missing in session")
                return None
            
            await websocket.accept()
            logger.info(f"WebSocket connection accepted for user: {user_id}")
            
            try:
                # while True:
                data = await websocket.receive_json()
                user_query = data.get("userQuery")

                if not user_query:
                    await send_socket_message(websocket, 'error', 'userQuery is required.')
                    # continue
                else:
                    await process_user_query(websocket, user_query, user_id)
                
                await asyncio.sleep(1)
                await websocket.close(code=1000, reason="Done processing")
            except WebSocketDisconnect:
                logger.info(f"WebSocket disconnected for user: {user_id}")
            except Exception as e:
                logger.error(f"WebSocket Error: {e}")
                await send_socket_message(websocket, 'error', 'A connection error occurred.')
    except Exception as e:
        logger.error(f"Error occurred while establishing connection,{e}")
