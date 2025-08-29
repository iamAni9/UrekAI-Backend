# from fastapi import Request, Response, status, BackgroundTasks
# from app.config.logger import get_logger
# from app.helper.query_analysis_helper import *
# from app.utils.whatsapp_message import send_whatsapp_message
# from app.utils.db_utils import update_job_queue, get_user_id_from_registered_no
# from app.utils.uniqueId import generate_unique_id
# from pathlib import Path
# import requests

# logger = get_logger("Whatsapp Logger")

# async def download_and_process_file_job(userid, file_url: str, filename: str, receiver: str, sender: str):
#     try:
#         response = requests.get(file_url)
#         response.raise_for_status()

#         file_content = response.content
        
#         # Saving the file temporarily
#         temp_dir = Path("/tmp/uploads")
#         temp_dir.mkdir(parents=True, exist_ok=True)
#         file_path = temp_dir / filename
        
#         with open(file_path, "wb") as f:
#             f.write(file_content)
        
#         ext = filename.suffix.lower()
#         unique_table_id = generate_unique_id()
#         table_name = f"table_{unique_table_id}"
        
#         job_data = {
#             "filePath": str(file_path),
#             "tableName": table_name,
#             "userid": userid,
#             "uploadId": unique_table_id,
#             "originalFileName": filename,
#             "medium": "WHATSAPP",
#             "receiver_no": receiver
#         }
        
#         logger.info("Processing file", extra={"file": filename, "tableName": table_name})

#         if ext == ".csv":
#             queue_name = "csv_queue"
#             await update_job_queue(job_data, queue_name, "csv_job", "csv")
#             send_whatsapp_message(receiver, sender, f"Upload for uploadID: {unique_table_id} is in progress. I will notify you once completed.", logger)
#         elif ext in [".xlsx", ".xls"]:
#             queue_name = "excel_queue"
#             await update_job_queue(job_data, queue_name, "excel_job", "excel")
#         else:
#             raise ValueError(f"Unsupported file format: {ext}")

#     except requests.exceptions.RequestException as e:
#         logger.error(f"Failed to download file from Infobip URL: {e}")
#         send_whatsapp_message(receiver, sender, "Error occurred while downloading your file.", logger)
#     except Exception as e:
#         logger.error(f"Failed to process file {filename}: {e}")
#         send_whatsapp_message(receiver, sender, "Error occurred while processing your file.", logger)

# async def process_and_reply(payload: dict):
#     for result in payload.get("results", []):
#         from_number = result.get("from")
#         to_number = result.get("to")
        
#         userid = get_user_id_from_registered_no(from_number, logger)
#         if userid is None:
#             send_whatsapp_message(to_number, from_number, "Your number is not registered with UrekAI.", logger)
#             return
            
#         content = result.get("message", {})
#         if content:
#             message_type = content.get("type")
#             try: 
#                 if message_type == "TEXT":
#                     body = content.get("text")
#                     logger.info(f"From: {from_number}, To: {to_number}, Body: {body}")

#                     if from_number:
#                         try:
#                             classification = await classify_query(body)
#                             if classification.type in ['general', 'unsupported']:
#                                 send_whatsapp_message(to_number, from_number, classification.message, logger)
#                         except Exception as e:
#                             logger.error(f"Error occurred while sending reply: {e}")
#                             raise
#                 elif message_type == "DOCUMENT":
#                     file_url = content.get("url")
#                     filename = content.get("caption", "unknown_file")

#                     logger.info(f"Received document from {from_number}: {filename}")
                    
#                     if filename.lower().endswith(('.csv', '.xls', '.xlsx')):
#                         if file_url:
#                             send_whatsapp_message(to_number, from_number, "Uploading your file...", logger)
#                             await download_and_process_file_job(userid, file_url, filename, to_number, from_number)
#                         else:
#                             logger.error(f"Document message from {from_number} did not contain a URL.")
#                             send_whatsapp_message(to_number, from_number, "Could not retrieve your file. Please try again.", logger)
#                     else:
#                         logger.warning(f"Unsupported document type received: {filename}")
#                         send_whatsapp_message(to_number, from_number, "File type not supported. Please upload a CSV or Excel file.", logger)
#                 else:
#                     logger.warning(f"Received unsupported message type: {message_type}")
#                     send_whatsapp_message(to_number, from_number, "Please upload a CSV or Excel file.", logger)
#             except Exception as e:
#                 send_whatsapp_message(to_number, from_number, "Error occurred while processing your message.", logger)
#                 logger.error(f"Error occurred while sending reply: {e}")

# async def whatsapp_handler_infobip(request: Request, background_tasks: BackgroundTasks) -> Response:
#     try:
#         payload = await request.json()
#         logger.info(f"Received Infobip payload: {payload}")

#         # Adding the message processing to background tasks
#         background_tasks.add_task(process_and_reply, payload)

#         # Immediately returning a 200 OK response for preventing the event loop issue
#         return Response(status_code=status.HTTP_200_OK)

#     except Exception as e:
#         logger.error(f"An error occurred in Infobip handler: {e}")
#         return Response(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)