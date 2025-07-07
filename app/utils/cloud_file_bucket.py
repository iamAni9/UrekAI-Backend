import aiohttp   # Delete this in future
import aiofiles
from pathlib import Path
from urllib.parse import urlparse
from app.config.settings import settings
import httpx

SUPABASE_URL = settings.SUPABASE_URL
SUPABASE_KEY = settings.SUPABASE_SERVICE_ROLE_KEY
BUCKET_NAME = settings.BUCKET_NAME

async def download_file(url: str) -> Path:
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status != 200:
                raise Exception(f"Download failed: {resp.status}")

            # Creating the /tmp/uploads directory if it doesn't exist
            temp_dir = Path("/tmp/uploads")
            temp_dir.mkdir(parents=True, exist_ok=True)

            # Extracting the filename from the URL
            filename = Path(urlparse(url).path).name
            file_path = temp_dir / filename

            # Saving the file
            async with aiofiles.open(file_path, mode='wb') as f:
                await f.write(await resp.read())

            return file_path
        
async def upload_to_supabase(file, user_id):

    file_bytes = await file.read()

    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": file.content_type
    }

    object_path = f"{user_id}/{file.filename}"  

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{SUPABASE_URL}/storage/v1/object/{BUCKET_NAME}/{object_path}",
            headers=headers,
            content=file_bytes
        )
        if resp.status_code != 200:
            raise Exception(f"Upload failed: {resp.text}")
    
    return f"{SUPABASE_URL}/storage/v1/object/public/{BUCKET_NAME}/{object_path}"

async def delete_from_supabase(object_path: str):
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "prefixes": [f"{object_path}"]
    }

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{SUPABASE_URL}/storage/v1/object/{BUCKET_NAME}/delete",
            headers=headers,
            json=payload
        )
        if resp.status_code != 200:
            raise Exception(f"Failed to delete file: {resp.text}")
        return True