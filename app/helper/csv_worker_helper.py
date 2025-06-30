import aiofiles
from pathlib import Path
from typing import Dict
import asyncpg
import chardet
from fastapi import HTTPException, status
from app.config.logger import get_logger
import asyncio
import os

logger = get_logger("CSV Worker")

async def get_sample_rows(file_path: str, sample_size: int) -> Dict[str, str]:
    
    # Running the blocking os.path.exists call in a separate thread
    if not await asyncio.to_thread(os.path.exists, file_path):
        raise FileNotFoundError(f"File not found at {file_path}")

    try:
        rows: Dict[str, str] = {}
        async with aiofiles.open(file_path, mode='r', encoding='utf-8', errors='ignore') as f:
            # aiofiles — is an asynchronous file I/O library
            # No need for await f.readlines() which reads the whole file.
            # Asynchronous iteration is more memory-efficient.
            i = 0
            async for line in f:
                if i >= sample_size:
                    break
                # Process the line
                values = [val.strip() if val.strip() else 'NULL' for val in line.strip().split(',')]
                rows[f"row{str(i + 1).zfill(2)}"] = ', '.join(values)
                i += 1
        return rows
    except Exception:
        raise


async def add_data_into_table_from_csv(conn, file_path, table_name, schema: Dict[str, str], contain_column: str):
    try:
        utf8_file_path = await convert_file_to_utf8(file_path)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process or convert file: {e}"
        )

    max_retries = 3
    for attempt in range(max_retries):
        try:
            # await conn.execute("SET datestyle TO 'ISO, DMY'")

            with open(utf8_file_path, "rb") as f:
                await conn.copy_to_table(
                    table_name,
                    source=f,
                    format='csv',
                    header=(contain_column.upper() == "YES"),
                    null=''
                )

            logger.info(f"Successfully loaded data into '{table_name}'.")
            return  # Success

        except asyncpg.PostgresError as e:
            logger.error(f"COPY failed (attempt {attempt + 1}): {e}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to insert data into '{table_name}': {str(e)}"
            )

    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=f"❌ All attempts to insert into '{table_name}' failed after {max_retries} tries."
    )
    
async def convert_file_to_utf8(input_path: str) -> str:
    async with aiofiles.open(input_path, 'rb') as f:
        raw_data = await f.read()
        detected = chardet.detect(raw_data)
        encoding = detected['encoding'] or 'utf-8'

    if encoding.lower() in ['utf-8', 'ascii']:
        logger.info(f"File '{input_path}' is already UTF-8/ASCII. No conversion needed.")
        return input_path

    logger.info(f"Detected encoding: {encoding}. Converting to UTF-8...")
    output_path = Path(input_path).stem + "_utf8.csv"

    async with aiofiles.open(input_path, mode='r', encoding=encoding) as f_in:
        content = await f_in.read()
        async with aiofiles.open(output_path, mode='w', encoding='utf-8') as f_out:
            await f_out.write(content)
            
    return output_path