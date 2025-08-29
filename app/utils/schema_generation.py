from fastapi import HTTPException
from typing import Dict, List
from app.config.prompts.prompts import SCHEMA_GENERATION
from app.ai.gemini import query_ai
import re, json
from app.config.constants import SCHEMA_BATCH_SIZE
from app.utils.db_utils import insert_analysis_data
import csv
from io import StringIO
    
def get_row_length(row):
    return len(next(csv.reader(StringIO(row), skipinitialspace=True)))
    
def parse_csv_row(row: str) -> List[str]:
    result = []
    current = ''
    in_quotes = False
    for char in row:
        if char == '"':
            in_quotes = not in_quotes
        elif char == ',' and not in_quotes:
            result.append(current.strip())
            current = ''
        else:
            current += char
    result.append(current.strip())
    return result

def split_sample_rows_by_column_batch(sample_rows: Dict[str, str], batch_size: int) -> List[Dict[str, str]]:
    row_keys = list(sample_rows.keys())
    column_matrix = [parse_csv_row(sample_rows[key]) for key in row_keys]
    max_columns = max(len(row) for row in column_matrix)
    normalized = [row + ['NULL'] * (max_columns - len(row)) for row in column_matrix]

    batches = []
    for start in range(0, max_columns, batch_size):
        end = min(start + batch_size, max_columns)
        batch = {}
        for i, row_key in enumerate(row_keys):
            batch[row_key] = ', '.join(normalized[i][start:end])
        batches.append(batch)
    return batches, max_columns

async def get_schema(table_name: str, sample_rows: List[str], column_no: int, logger) -> Dict:
    logger.info(f"Analyzing schema for table: {table_name}")

    user_query = f"""
    Table Name: {table_name}
    Sample Datarows: {sample_rows}
    Number of Columns: {column_no}

    {SCHEMA_GENERATION["userPrompt"]}

    Respond only with JSON:
    {{
        "schema": {{
            "columns": [{{"column_name": "string", "data_type": "string", "is_nullable": "YES/NO"}}]
        }},
        "contain_columns": {{
            "contain_column": "YES/NO"
        }},
        "column_insights": {{
            "col_name": {{
                "patterns": ["..."],
                "anomalies": ["..."],
                "business_significance": "..."
            }}
        }}
    }}
    """

    try:
        ai_response = await query_ai(user_query, SCHEMA_GENERATION["systemPrompt"])
        cleaned = re.sub(r'```json|```', '', ai_response).strip()
        cleaned = re.sub(r'([{,])(\s*)([a-zA-Z_][a-zA-Z0-9_]*)\s*:', r'\1 "\3":', cleaned)
        braces = cleaned.count('{') - cleaned.count('}')
        if braces > 0:
            cleaned += '}' * braces
        return json.loads(cleaned)
    except Exception as e:
        logger.error("Error parsing AI response", exc_info=True)
        raise

async def generate_table_schema(conn, userid, table_name, original_file_name, sample_rows, logger):
    try:
        logger.info(f"Starting schema generation for table {table_name}")
        column_batches, max_length = split_sample_rows_by_column_batch(sample_rows, SCHEMA_BATCH_SIZE)
        schemas = []

        for i, batch in enumerate(column_batches):
            logger.info(f"Processing batch {i + 1}/{len(column_batches)}")
            # row1 = batch.get("row01") or list(batch.values())[0]
            col_count = min(max_length, SCHEMA_BATCH_SIZE)
            if max_length > SCHEMA_BATCH_SIZE:
                max_length = max_length - SCHEMA_BATCH_SIZE
                
            logger.info(f"Row1: {batch.get('row01')}")
            logger.info(f"Column Count: {col_count}")
            
            schema = await get_schema(table_name, list(batch.values()), col_count, logger)
            schemas.append(schema)

        logger.info(f"Schema: {schemas}")
        merged_schema = {
            "schema": {"columns": []},
            "contain_columns": {"contain_column": "NO"},
            "column_insights": {}
        }

        for part in schemas:
            merged_schema["schema"]["columns"].extend(part["schema"]["columns"])
            merged_schema["column_insights"].update(part["column_insights"])
            if part["contain_columns"]["contain_column"] == "YES":
                merged_schema["contain_columns"]["contain_column"] = "YES"

        await insert_analysis_data(
            conn, 
            userid,
            table_name, 
            original_file_name, 
            json.dumps(merged_schema["schema"]), 
            json.dumps(merged_schema["column_insights"]),
            logger 
        )
        
        return {
            "schema": merged_schema["schema"],
            "contain_columns": merged_schema["contain_columns"]
        }
    except Exception as e:
        logger.error("Schema generation failed", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))