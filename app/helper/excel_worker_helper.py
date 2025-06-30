from pathlib import Path
from typing import Dict
from app.config.logger import get_logger
from fastapi import HTTPException, status
import asyncio
import os
import pandas as pd
import asyncpg

logger = get_logger("EXCEL Worker")

async def get_sample_rows(file_path: str, sample_size: int) -> Dict[str, str]:
 
    # Running the blocking os.path.exists call in a separate thread
    if not await asyncio.to_thread(os.path.exists, file_path):
        raise FileNotFoundError(f"File not found at {file_path}")

    try:
        def read_excel_sample():
            df = pd.read_excel(file_path, nrows=sample_size, engine='openpyxl')
            df.fillna('NULL', inplace=True)
            return df

        df = await asyncio.to_thread(read_excel_sample)

        rows: Dict[str, str] = {}
        for i, row in df.iterrows():
            values = [str(cell) for cell in row]
            rows[f"row{str(i + 1).zfill(2)}"] = ', '.join(values)

        return rows
    except Exception:
        raise
    
async def add_data_into_table_from_excel(conn, file_path, table_name, schema: Dict[str, str], contain_column: str):
    try:
        file_extension = Path(file_path).suffix.lower()
        if file_extension not in ['.xlsx', '.xls']:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported file type: '{file_extension}'. Please upload an Excel file (.xlsx or .xls)."
            )
        
        # Converting the Excel file to a temporary CSV file
        temp_csv_path = await convert_excel_to_csv(file_path, contain_column)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process or convert Excel file: {e}"
        )

    max_retries = 3
    for attempt in range(max_retries):
        try:
            with open(temp_csv_path, "r", encoding='utf-8') as f:
                await conn.copy_to_table(
                    table_name=table_name,
                    source=f,
                    format='csv',
                    header=(contain_column.upper() == "YES"),
                    null='' 
                )

            logger.info(f"Successfully loaded data from '{file_path}' into '{table_name}'.")
            os.remove(temp_csv_path)
            return # Success 
        
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
    
def _blocking_excel_to_csv(input_path: str, output_path: str, header: bool):
    df = pd.read_excel(input_path)
    df.to_csv(output_path, index=False, header=header, encoding='utf-8')


async def convert_excel_to_csv(input_path: str, contain_column: str) -> str:
    logger.info(f"Converting Excel file '{input_path}' to CSV...")
    output_path = f"{Path(input_path).stem}_temp.csv"
    
    header = contain_column.upper() == "YES"

    # Running the blocking pandas I/O operation in a separate thread
    await asyncio.to_thread(_blocking_excel_to_csv, input_path, output_path, header)

    logger.info(f"Successfully converted '{input_path}' to '{output_path}'.")
    return output_path