from fastapi import Request, Response, status, BackgroundTasks, Query
from app.config.logger import get_logger
from app.helper.query_analysis_helper import *
from app.helper.shopify_query_analysis_helper import *
from app.utils.whatsapp_message import send_whatsapp_message, mark_user_message_as_read, send_typing_indicator
from app.utils.db_utils import update_job_queue, get_user_id_from_registered_no, delete_multiple_tables, fetch_shopify_credentials
from app.utils.uniqueId import generate_unique_id
from app.config.integration_config.whatsapp import whatsapp_channel
from app.config.settings import settings
from pathlib import Path
from app.config.constants import MAX_EVAL_ITERATION

logger = get_logger("Whatsapp Logger")

def format_table_data(table_data: dict) -> str:
    if table_data is None:
        return None
    parts = []

    for table_name, rows in table_data.items():
        if not rows:
            continue

        headers = list(rows[0].keys())

        col_widths = {
            h: max(len(str(h)), max(len(str(r.get(h, ""))) for r in rows))
            for h in headers
        }

        header_line = " | ".join(f"{h.ljust(col_widths[h])}" for h in headers)
        separator = "-+-".join("-" * col_widths[h] for h in headers)

        row_lines = []
        for r in rows:
            row_lines.append(
                " | ".join(str(r.get(h, "")).ljust(col_widths[h]) for h in headers)
            )

        table_text = "\n".join([f"*{table_name}*:", header_line, separator] + row_lines)
        parts.append(table_text)

    return "\n\n".join(parts)

def format_analysis(analysis: dict) -> str:
    if analysis is None:
        return None
    parts = []
    for key, value in analysis.items():
        if isinstance(value, list):
            value = ", ".join(map(str, value))
        elif isinstance(value, dict):
            # Pretty print nested dict
            nested = "\n".join([f"   - {k}: {v}" for k, v in value.items()])
            value = f"\n{nested}"
        if key.capitalize() == 'Summary':
            parts.append(f"{value}")
        else:
            parts.append(f"\n*{key.capitalize()}*\n{value}")
    return "\n".join(parts)

async def download_and_process_file_job(userid: str, media_id: str, filename: str, sender_no: str):
    try:
        # Step 1: Getting the temporary media URL from the media ID
        file_url = whatsapp_channel.get_media_url(media_id)
        if not file_url:
            raise ValueError(f"Could not retrieve media URL for media ID: {media_id}")

        # Step 2: Downloading the file content using the URL
        file_content = whatsapp_channel.download_media(file_url)
        if not file_content:
            raise ValueError(f"Failed to download file content from URL: {file_url}")

        # Step 3: Saving the file temporarily
        temp_dir = Path("/tmp/uploads")
        temp_dir.mkdir(parents=True, exist_ok=True)
        file_path = temp_dir / filename
        
        with open(file_path, "wb") as f:
            f.write(file_content)
        
        # Step 4: Updating the job queue
        ext = Path(filename).suffix.lower()
        unique_table_id = generate_unique_id()
        table_name = f"table_{unique_table_id}"
        
        job_data = {
            "filePath": str(file_path),
            "tableName": table_name,
            "userid": str(userid),
            "uploadId": unique_table_id,
            "originalFileName": filename,
            "medium": "WHATSAPP",
            "receiver_no": sender_no
        }
        
        logger.info("Processing file", extra={"file": filename, "tableName": table_name})

        if ext == ".csv":
            queue_name = "csv_queue"
            await update_job_queue(job_data, queue_name, "csv_job", "csv", logger)
            send_whatsapp_message(sender_no, f"Upload for uploadID: {unique_table_id} is in progress. I will notify you once completed.", logger)
        elif ext in [".xlsx", ".xls"]:
            queue_name = "excel_queue"
            await update_job_queue(job_data, queue_name, "excel_job", "excel", logger)
            send_whatsapp_message(sender_no, f"Upload for uploadID: {unique_table_id} is in progress. I will notify you once completed.", logger)
        else:
            raise ValueError(f"Unsupported file format: {ext}")

    except Exception as e:
        logger.error(f"Failed to process file {filename}: {e}")
        send_whatsapp_message(sender_no, "An error occurred while processing your file.", logger)

async def process_shopify_analysis(user_msg: str, sender_no: str, classification_message: str, shop: str, access_token: str):
    try:
        llm_suggestions = None
        analysis_results = None
        for attempt in range(1, MAX_EVAL_ITERATION + 1):
        # for attempt in range(1, 2):
            logger.info(f"Attempt {attempt} to generate and evaluate ShopifyQL queries")
            
            generated_queries_raw = await generate_shopifyQL(user_msg, llm_suggestions)
            logger.info(f"Generated queries: {generated_queries_raw}")
            parsed_queries = parse_generated_shopify_queries(generated_queries_raw)
            if not parsed_queries:
                logger.error('Failed to parse generated queries')
                continue
            logger.info(f"Parsed queries: {parsed_queries}")
            
            query_results = await execute_shopify_queries(parsed_queries, shop, access_token)
            # logger.info(f"Query executed successfully, {query_results}")
            
            if query_results and query_results[0]:
                logger.info("Executing in loop")

                structured_result_lines = []
                for i, val in enumerate(query_results):
                    if val.get('data') is not None:
                        result_str = (
                            f"Query {i + 1}:\n{val['query']}\nResults:\n"
                            f"{json.dumps(val['data'], indent=2, default=str)}\n"
                        )
                    else:
                        result_str = (
                            f"Query {i + 1}:\n{val['query']}\nError:\n"
                            f"{val.get('errors', 'No results and no error message.')}\n"
                        )
                    structured_result_lines.append(result_str)
                    
                structured_result = "\n".join(structured_result_lines)
                logger.info(f"Queries and results: {structured_result}")
                
                analysis_results = await generate_analysis(structured_result, user_msg, classification_message)

                if not analysis_results:
                    logger.warning('Generated analysis failed evaluation')
                    continue
                
                evaluation = await analysis_evaluation(
                    json.dumps(analysis_results), structured_result, user_msg, llm_suggestions
                )
                
                if evaluation.get('good_result') == 'Yes':
                    logger.info(f"Analysis Data: {analysis_results}")
                    analysis_text = format_analysis(analysis_results.get("analysis"))
                    table_data = format_table_data(analysis_results.get("table_data"))
                    if analysis_text:
                        send_whatsapp_message(sender_no, analysis_text, logger)
                    if table_data:
                        send_whatsapp_message(sender_no, table_data, logger)
                    break

                llm_suggestions = evaluation.get('required')
                analysis_results = None
                
        if not analysis_results:
            send_whatsapp_message(sender_no, 'Failed to generate a good analysis after multiple attempts. Try again.', logger)
            return
    except Exception as e:
        logger.error(f"Error in Shopify analysis: {e}")
        raise

async def process_analysis(user_msg: str, sender_no: str, classification, structured_metadata):
    try:
        llm_suggestions = None
        analysis_results = None
        for attempt in range(1, MAX_EVAL_ITERATION + 1):
            logger.info(f"Attempt {attempt} to generate and evaluate SQL queries")
            
            generated_queries_raw = await generate_sql_queries(
                user_msg, classification.type, structured_metadata, llm_suggestions
            )
            
            parsed_queries = parse_generated_queries(generated_queries_raw)
            if not parsed_queries:
                logger.error('Failed to parse generated queries')
                continue 
            
            if isinstance(parsed_queries, dict) and parsed_queries.get("error"):
                send_whatsapp_message(sender_no, f"Data is not sufficient. {parsed_queries['suggestions'][0]}", logger)
                logger.error("Unsupported query based on data available in uploaded files.")
                logger.info(parsed_queries)
                return
            
            logger.info(f"Generated queries: {parsed_queries}")

            query_results = await execute_parsed_queries(parsed_queries)
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
                    else:
                        result_str = (
                            f"Query {i + 1}:\n{val['query']}\nError:\n"
                            f"{val.get('error', 'No results and no error message.')}\n"
                        )

                    structured_result_lines.append(result_str)

                structured_result = "\n".join(structured_result_lines)
                logger.info(f"Queries and results: {structured_result}")
                
                analysis_results = await generate_analysis(structured_result, user_msg, classification.message)

                if not analysis_results:
                    logger.warning('Generated analysis failed evaluation')
                    continue
                
                evaluation = await analysis_evaluation(
                    json.dumps(analysis_results), structured_result, user_msg, llm_suggestions
                )
                
                if evaluation.get('good_result') == 'Yes':
                    logger.info(f"Analysis Data: {analysis_results}")
                    analysis_text = format_analysis(analysis_results["analysis"])
                    table_data = format_table_data(analysis_results["table_data"])
                    send_whatsapp_message(sender_no, analysis_text, logger)
                    send_whatsapp_message(sender_no, table_data, logger)
                    break

                llm_suggestions = evaluation.get('required')
                
        if not analysis_results:
            send_whatsapp_message(sender_no, 'Failed to generate a good analysis after multiple attempts. Try again.', logger)
            return
    except Exception as e:
        raise

async def process_query_message(userid: str, user_msg: str, sender_no: str):
    try:
        classification = await classify_query(user_msg, "WhatsApp")
        if classification.type in ['general', 'file_management', 'integration_management', 'unsupported']:
            send_whatsapp_message(sender_no, classification.message, logger)
            return
        
        user_metadata = await fetch_user_metadata(userid)
        if not user_metadata:
            send_whatsapp_message(sender_no, "You don't have any data uploaded.", logger)
            return
        
        structured_metadata = flatten_and_format(user_metadata)
        
        if classification.type in ['check_upload', 'delete_upload']:
            try:
                selected_list = await data_management_selection(
                    user_msg, classification.type, structured_metadata
                )
                logger.info(f"Selected_list: {selected_list}")
                if classification.type == 'check_upload':
                    data = ", ".join(selected_list['files'])
                    send_whatsapp_message(sender_no, f"*Your Uploaded Data -*\n{data} ", logger)
                else:
                    data = ", ".join(selected_list['files'])
                    await delete_multiple_tables(selected_list['files'], selected_list['tables'], logger)
                    send_whatsapp_message(sender_no, f"*Your Uploaded Data*\n{data}\n*Deleted successfully*", logger)
                return
            except Exception as e:
                logger.error(f"Something went wrong, Try Again: {e}")
                send_whatsapp_message(sender_no, "Something went wrong, Try Again.", logger)
                return
        
        if classification.type == 'shopify':
            shop, access_token = await fetch_shopify_credentials(userid, logger)
            if not shop or not access_token:    
                send_whatsapp_message(sender_no, "Shopify credentials are not configured. Please set them up to proceed.", logger)
                return
            await process_shopify_analysis(user_msg, sender_no, classification.message, shop, access_token)
        else:
            await process_analysis(user_msg, sender_no, classification, structured_metadata)
        return
    except Exception as e:
        raise
    


async def process_and_reply(payload: dict):
    try:
        # {'object': 'whatsapp_business_account', 
        #  'entry': [
        #     {'id': '626610350502138', 
        #      'changes': [
        #         {'value': {'messaging_product': 'whatsapp', 
        #          'metadata': {'display_phone_number': '15551513895', 'phone_number_id': '810142712173971'}, 
        #          'contacts': [{'profile': {'name': 'Kratika'}, 'wa_id': '919760070912'}], 
        #          'messages': [{'from': '919769769762', 'id': 'wamid.HBgMOTE5NzYwMDcwOTEyFQIAEhggNjVGQTczMTJGMUI0MjE2QTgxNUJDMDEwMDgyRUU5QzAA', 'timestamp': '1756199529', 'text': {'body': 'Testing message'}, 'type': 'text'}]}, 
        #          'field': 'messages'
        #         }
        #       ]
        #     }
        #   ]
        # }
        changes = payload.get("entry", [{}])[0].get("changes", [{}])[0]
        value = changes.get("value", {})
        
        if "messages" in value:
            message = value["messages"][0]
            from_number = message["from"]
            metadata = value.get("metadata", {})
            to_number = metadata.get("display_phone_number")
            # phone_number_id = metadata.get("phone_number_id")

            userid = await get_user_id_from_registered_no(from_number, logger)
            if userid is None:
                send_whatsapp_message(from_number, "Your number is not registered with UrekAI.", logger)
                return
            try: 
                message_type = message.get("type")
                message_id = message.get("id")
                
                await mark_user_message_as_read(message_id, logger)

                if message_type == "text":
                    await send_typing_indicator(message_id, logger)
                    body = message["text"]["body"]
                    logger.info(f"From: {from_number}, To: {to_number}, Body: {body}")
                    await process_query_message(str(userid), body, from_number)

                elif message_type == "document":
                    await send_typing_indicator(message_id, logger)
                    document = message["document"]
                    media_id = document["id"]
                    filename = document.get("filename", "unknown_file")
                    
                    logger.info(f"Received document from {from_number}: {filename} (Media ID: {media_id})")

                    if Path(filename).suffix.lower() in ['.csv', '.xls', '.xlsx']:
                        send_whatsapp_message(from_number, "Uploading your file...", logger)
                        await download_and_process_file_job(userid, media_id, filename, from_number)
                    else:
                        logger.warning(f"Unsupported document type received: {filename}")
                        send_whatsapp_message(from_number, "File type not supported. Please upload a CSV or Excel file.", logger)
                else:
                    logger.warning(f"Received unsupported message type: {message_type}")
                    send_whatsapp_message(from_number, "This message type is not supported.", logger)
            except Exception as e:
                send_whatsapp_message(from_number, "Error occurred while processing your message.", logger)
                logger.error(f"Error occurred while sending reply: {e}")
    except Exception as e:
        logger.error(f"Error processing webhook payload: {e}", exc_info=True)
        raise

async def whatsapp_handler_meta(
    request: Request,
    background_tasks: BackgroundTasks,
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
    hub_verify_token: str = Query(None, alias="hub.verify_token")
) -> Response:
    """
    Handles both webhook verification (GET) and message notifications (POST) from Meta.
    """
    # Handling Webhook Verification
    if hub_mode == "subscribe" and hub_verify_token:
        if hub_verify_token == settings.META_VERIFY_TOKEN:
            logger.info("Webhook verified successfully!")
            return Response(content=hub_challenge, status_code=status.HTTP_200_OK)
        else:
            logger.warning("Webhook verification failed: Invalid verify token.")
            return Response(status_code=status.HTTP_403_FORBIDDEN)

    # Handling Message Notifications
    if request.method == "POST":
        try:
            payload = await request.json()
            logger.info(f"Received Meta payload: {payload}")
            
            background_tasks.add_task(process_and_reply, payload)
            
            # Acknowledging receipt immediately
            return Response(status_code=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"An error occurred in Meta handler: {e}")
            return Response(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)