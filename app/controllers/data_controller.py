from fastapi import UploadFile,  Request, status
from fastapi.responses import JSONResponse
from typing import List
from pathlib import Path
from app.config.logger import logger
from app.config.postgres import database as db
import uuid
from app.utils.uniqueId import generate_unique_id, str_to_uuid

async def check_user_exists(userid, email):
    try:
        user = await db.fetch_one("SELECT * FROM users WHERE id = :userid AND email = :email", {"userid": userid, "email": email})
        return bool(user)
    except Exception as error:
        logger.error(f"Error while checking user in db: {error}")
        raise
    
def generate_table_id():
    return uuid.uuid4().hex  # 32-character hex string

async def update_csv_queue(job_data):
    try:
        async with db.transaction():
            await db.execute("""
                INSERT INTO csv_queue (
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
            await db.execute("NOTIFY new_csv_job;")
        logger.info(f"Successfully added job {job_data['uploadId']} and sent notification.")
    except Exception as error:
        logger.error(f"Error inserting into CSV queue: {error}")
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
                # ext = Path(file.filename).suffix.lower()
                ext = ".csv"
                unique_table_id = generate_unique_id()
                table_name = f"table_{unique_table_id}"

                # Save the file temporarily
                temp_dir = Path("/tmp/uploads")
                temp_dir.mkdir(parents=True, exist_ok=True)
                file_path = temp_dir / file.filename

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

                logger.info("Processing file", extra={"file": "ABCD", "tableName": table_name})

                if ext == ".csv":
                    await update_csv_queue(job_data)
                # elif ext in [".xlsx", ".xls"]:
                #     await excel_queue.enqueue(job_data)
                # elif ext == ".json":
                #     await json_queue.enqueue(job_data)
                else:
                    raise ValueError(f"Unsupported file format: {ext}")

                upload_results.append({
                    "success": True,
                    "message": "Upload accepted",
                    "originalFileName": "ABCD",
                    "uploadId": unique_table_id,
                    "tableName": table_name,
                    "status": "pending"
                })

            except Exception as error:
                logger.exception("Error processing file")
                upload_results.append({
                    "success": False,
                    "message": "Failed to process file",
                    "error": str(error),
                    "fileName": "ABCD",
                    "status": "failed"
                })

        return {
            "success": True,
            "message": "Upload initiated for files",
            "results": upload_results
        }

    except Exception as error:
        logger.exception("Unhandled error in upload handler")
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": "Server error"}
        )
    