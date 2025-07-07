from fastapi import UploadFile,  Request, status, HTTPException
from fastapi.responses import JSONResponse
from typing import List
from pathlib import Path
# from app.config.settings import settings
from app.config.logger import get_logger
from app.config.postgres import database as db
from app.utils.uniqueId import generate_unique_id, str_to_uuid
# from app.utils.cloud_file_bucket import upload_to_supabase

logger = get_logger("API Logger")

async def check_user_exists(userid, email):
    try:
        user = await db.fetch_one("SELECT * FROM users WHERE id = :userid AND email = :email", {"userid": userid, "email": email})
        return bool(user)
    except Exception as error:
        logger.error(f"Error while checking user in db: {error}")
        raise

async def check_upload_status(queue_name, user_id, upload_id):
    try:
        result = await db.fetch_one(
                    f"""
                    SELECT progress, status
                    FROM {queue_name}
                    WHERE upload_id = :upload_id AND user_id = :user_id
                    """,
                    values={"upload_id": upload_id, "user_id": user_id}
                )   
        return result;         
    except Exception as error:
        logger.error(f"Error while checking status for upload_id: {upload_id}", error)
        raise

async def update_job_queue(job_data, queue_name, channel_name, payload):
    try:
        async with db.transaction():
            await db.execute(f"""
                INSERT INTO {queue_name} (
                    upload_id, user_id, email, table_name, file_path, original_file_name
                ) VALUES (
                    :upload_id, :user_id, :email, :table_name, :file_path, :original_file_name
                )
            """, values={
                 "upload_id": job_data["uploadId"],
                 "user_id": job_data["userid"],
                 "email": job_data["email"],
                 "table_name": job_data["tableName"],
                 "file_path": job_data["filePath"],
                 "original_file_name": job_data["originalFileName"]
            })
            await db.execute(f"NOTIFY {channel_name}, '{payload}';")
        logger.info(f"Successfully added job {job_data['uploadId']} and sent notification.")
    except Exception as error:
        logger.error(f"Error inserting into {queue_name}: {error}")
        raise

async def remove_upload_data(userid, upload_id):
    table_name = f"table_{upload_id}"
    try:
        async with db.transaction():
            await db.execute(f'DROP TABLE IF EXISTS "{table_name}"')

            await db.execute(
                "DELETE FROM analysis_data WHERE id = :userid AND table_name = :table_name",
                {"userid": userid, "table_name": table_name}
            )
        logger.info(f"Removed table data for userid: {userid} and upload_id: {upload_id} successfully")
        return True
    except Exception as error:
        logger.error(
            f"Error while removing table data for userid: {userid} and upload_id: {upload_id}: {error}"
        )
        raise
    

async def file_upload_handler(request: Request, files: List[UploadFile]):
    try:
        logger.info("File uploading starts")
        user = request.session.get("user")
        logger.info(f"USER: {user}")
        if not user:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"success": False, "message": "Unauthorized"}
            )
        userid = str_to_uuid(user.get("id"))
        email = user.get("email")

        if not isinstance(files, list):
            files = [files]
            
        if not files or not userid or not email:
            logger.error("Missing required fields", extra={"userid": userid, "email": email, "files": len(files)})
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={
                    "success": False,
                    "message": "At least one file and email are required",
                    "status": "Failed"
                }
            )
                    
        logger.info(f"FILES RECEIVED: {len(files)} file(s)")
        # logger.info("TYPES:", [type(f) for f in files])
        
        
        user_exists = await check_user_exists(userid, email)
        if not user_exists:
            logger.error("User not found", extra={"email": email})
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={
                    "success": False,
                    "message": "User not found. Please register first.",
                    "status": "Failed"
                }
            )

        upload_results = []

        for file in files:
            try:
                ext = Path(file.filename).suffix.lower()
                unique_table_id = generate_unique_id()
                table_name = f"table_{unique_table_id}"
                queue_name = ''

                # Save the file temporarily
                temp_dir = Path("/tmp/uploads")
                temp_dir.mkdir(parents=True, exist_ok=True)
                file_path = temp_dir / file.filename
                
                # if settings.ENV == 'development':
                #     temp_dir = Path("/tmp/uploads")
                #     temp_dir.mkdir(parents=True, exist_ok=True)
                #     file_path = temp_dir / file.filename
                # else:
                #     file_path = upload_to_supabase(file, userid)

                with open(file_path, "wb") as f:
                    content = await file.read()
                    f.write(content)

                job_data = {
                    "filePath": str(file_path),
                    "tableName": table_name,
                    "userid": userid,
                    "email": email,
                    "uploadId": unique_table_id,
                    "originalFileName": file.filename
                }

                logger.info("Processing file", extra={"file": file.filename, "tableName": table_name})

                if ext == ".csv":
                    queue_name = "csv_queue"
                    await update_job_queue(job_data, queue_name, "csv_job", "csv")
                elif ext in [".xlsx", ".xls"]:
                    queue_name = "excel_queue"
                    await update_job_queue(job_data, queue_name, "excel_job", "excel")
                # elif ext == ".json":
                #     await json_queue.enqueue(job_data)
                else:
                    raise ValueError(f"Unsupported file format: {ext}")

                upload_results.append({
                    "success": True,
                    "message": "Upload accepted",
                    "originalFileName": file.filename,
                    "uploadId": unique_table_id,
                    "queue_name": queue_name
                })

            except Exception as error:
                logger.exception("Error processing file")
                upload_results.append({
                    "success": False,
                    "message": "Failed to process file",
                    "error": str(error),
                    "fileName": file.filename,
                    "status": "failed"
                })

        return {
            "success": True,
            "message": "Upload initiated for files",
            "results": upload_results
        }

    except Exception as error:
        logger.exception(f"Unhandled error in upload handler: {error}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": "Server error"}
        )

async def file_upload_status_check(request: Request):
    try:
        user = request.session.get("user")
        if not user:
            raise HTTPException(status_code=401, detail="Unauthorized")
        
        user_id = user.get("id")
        
        upload_id = request.query_params.get("upload_id")
        file_type = request.query_params.get("extension")
        # print(f"Upload ID = {upload_id}, File type = {file_type}")
        if not upload_id or not file_type:
            logger.error("Missing required fields", extra={"upload_id": upload_id, "extension": file_type})
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={
                    "success": False,
                    "message": "Provide upload_id and extension",
                    "status": "Failed"
                }
            )
        
        if file_type == 'csv':
            queue_name = "csv_queue"
        else:
            queue_name = "excel_queue"
        
        info = await check_upload_status(queue_name, user_id, upload_id)
        if info:
            return {
                "success": True,
                "message": info
            }
        else:
            return {
                "success": False,
                "message": "Job not found."
            }
    except Exception as error:
        logger.exception(f"Error while checking upload status: {error}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": "Unexpected error while checking upload status"}
        )
        
async def file_upload_delete(request: Request):
    try:
        user = request.session.get("user")
        if not user:
            raise HTTPException(status_code=401, detail="Unauthorized")
        
        userid = str_to_uuid(user.get("id"))
        
        body = await request.json()
        upload_id = body.get("uploadId")
        
        result = await remove_upload_data(userid, upload_id)
        
        if result:
            return {
                "success": True,
                "message": "File removed successfully"
            }
        else:
            return {
                "success": False,
                "message": "File not found."
            }
        
    except Exception as error:
        logger.exception(f"Error while removing data table: {error}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": "Unexpected error while deleting file data from db"}
        )