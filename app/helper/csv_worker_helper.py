import aiofiles
import re
from pathlib import Path
from typing import Dict, Optional, Tuple
import asyncpg
import chardet
from fastapi import HTTPException, status
from app.config.logger import logger
import asyncio
import os

async def get_sample_rows(file_path: str, sample_size: int) -> Dict[str, str]:
    
    # Run the blocking os.path.exists call in a separate thread
    if not await asyncio.to_thread(os.path.exists, file_path):
        raise FileNotFoundError(f"File not found at {file_path}")

    rows: Dict[str, str] = {}
    async with aiofiles.open(file_path, mode='r', encoding='utf-8', errors='ignore') as f:
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


# Track upgrades to avoid endless upcasting
COLUMN_TYPE_UPGRADES = {
    "INTEGER": "BIGINT",
    "BIGINT": "TEXT",
    "DOUBLE PRECISION": "TEXT",
    "VARCHAR": "TEXT",
    "NUMERIC": "TEXT"
}

async def add_data_into_table_from_csv(conn, file_path, table_name, schema: Dict[str, str], contain_column: str):
    try:
        utf8_file_path = await convert_file_to_utf8(file_path)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process or convert file: {e}"
        )

    max_retries = 3
    attempted_upgrades = {}  # Track attempted upgrades per column

    for attempt in range(max_retries):
        try:
            await conn.execute("SET datestyle TO 'ISO, DMY'")

            with open(utf8_file_path, "rb") as f:
                await conn.copy_to_table(
                    table_name,
                    source=f,
                    format='csv',
                    header=(contain_column.upper() == "YES"),
                    null='\\N'
                )

            logger.info(f"Successfully loaded data into '{table_name}'.")
            return  # Success

        except asyncpg.PostgresError as e:
            logger.info(f"COPY failed (attempt {attempt + 1}): {e}")
            conversion = get_type_conversion(e)

            if conversion:
                col_name, new_type = conversion

                # Avoid upgrading the same column to the same type repeatedly
                if attempted_upgrades.get(col_name) == new_type:
                    logger.info(f"Already tried upgrading column '{col_name}' to '{new_type}'. Skipping.")
                    break

                attempted_upgrades[col_name] = new_type

                try:
                    await alter_column_type(conn, table_name, col_name, new_type)
                    logger.info(f"Retrying COPY after schema update...")
                    continue
                except Exception as alter_err:
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail=f"Failed to alter table column '{col_name}': {alter_err}"
                    )
            else:
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
    

def get_type_conversion(err: asyncpg.PostgresError) -> Optional[Tuple[str, str]]:
    message = err.message.lower()
    detail = err.detail or ""
    column_name = getattr(err, "column_name", None)

    # Try extracting column from message if not available directly
    if not column_name:
        match = re.search(r'column "([^"]+)"', detail) or re.search(r'column "([^"]+)"', message)
        if match:
            column_name = match.group(1)

    if not column_name:
        return None

    if 'value too long for type character varying' in message:
        return (column_name, 'TEXT')

    if 'out of range for type integer' in message:
        return (column_name, 'BIGINT')

    if 'invalid input syntax for type integer' in message:
        return (column_name, 'TEXT')

    if 'invalid input syntax for type double precision' in message:
        return (column_name, 'TEXT')

    if 'numeric field overflow' in message:
        return (column_name, 'TEXT')

    if 'cannot cast' in message and 'to type' in message:
        return (column_name, 'TEXT')

    return None


async def alter_column_type(conn, table_name: str, column_name: str, new_type: str):
    # Basic validation
    if not all([table_name, column_name, new_type]):
        raise ValueError("Table name, column name, and new type cannot be empty.")
    
    # Using 'USING column::new_type' is often necessary for safe casting
    query = f"""
        ALTER TABLE "{table_name}"
        ALTER COLUMN "{column_name}" TYPE {new_type}
        USING "{column_name}"::{new_type};
    """
    logger.info(f"Executing schema change: {query}")
    await conn.execute(query)