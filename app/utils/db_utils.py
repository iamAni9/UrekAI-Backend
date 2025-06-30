from app.config.logger import get_logger
from datetime import datetime, timezone
from typing import Dict, Any
import asyncpg
from fastapi import HTTPException, status

async def remove_analysis(conn, userid, table_name, logger):
    try:
        query = """
        DELETE FROM analysis_data 
        WHERE id = $1 AND table_name = $2
        """
        await conn.execute(query, userid, table_name)
        logger.info(f"✅ Analysis for '{userid}' and {table_name}' removed successfully.")
    except Exception as e:
        logger.error(f"Error occurred while removing the analysis for {userid}' and {table_name}': {e}")
        raise
    
async def delete_temp_table(conn, table_name, logger):
    try:
        query = f'DROP TABLE IF EXISTS "{table_name}" CASCADE'
        await conn.execute(query)
        logger.info(f"✅ Table '{table_name}' deleted successfully.")
    except Exception as e:
        logger.error(f"Error occurred while deleting table '{table_name}': {e}")
        raise

# --- Helper function to sanitize SQL identifiers ---
def sanitize_identifier(name: str) -> str:
    """
    Sanitizes a string to be used as a safe SQL identifier (table or column name).
    Removes characters that are not alphanumeric or underscores.
    """
    if not isinstance(name, str) or not name:
        raise ValueError("Identifier must be a non-empty string.")
    return "".join(char for char in name if char.isalnum() or char == '_')


async def create_table_from_schema(conn, table_name: str, schema: Dict[str, Any], logger):
    try:
        # --- 1. Validating and Sanitizing Inputs (More Robust Approach) ---
        safe_table_name = sanitize_identifier(table_name)
        if not schema or 'columns' not in schema or not schema['columns']:
            raise ValueError("Schema must be a dictionary with a non-empty 'columns' list.")

        # --- 2. Building Column Definitions ---
        column_definitions = []
        for col in schema['columns']:
            # Ensure each column dict has the required keys
            if 'column_name' not in col or 'data_type' not in col:
                raise ValueError(f"Invalid column definition found: {col}")
            
            safe_col_name = sanitize_identifier(col['column_name'])
            data_type = col['data_type'] # Data types should be validated against an allow-list

            # column_definitions.append(f'"{safe_col_name}" {data_type}')
            column_definitions.append(f'"{safe_col_name}" TEXT')

        # --- 3. Constructing the Full SQL Query ---
        columns_sql = ",\n  ".join(column_definitions)
        create_table_query = f"""
            CREATE TABLE IF NOT EXISTS "{safe_table_name}" (
                {columns_sql}
            );
        """
        
        logger.debug(f"Executing query: \n{create_table_query}")

        # --- 4. Executing the Query ---
        
        await conn.execute(create_table_query)
        
        logger.info(f"Table '{safe_table_name}' created successfully or already exists.")
        return True

    except (ValueError, KeyError) as e:
        # Catches errors from invalid schema or identifiers
        logger.error(f"Schema validation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid schema provided: {e}"
        )
    except asyncpg.PostgresError as e:
        # Catches any errors from the database itself
        logger.error(f"Error creating table '{table_name}': {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error while creating table: {e}"
        )
        
async def insert_analysis_data(conn, id, table_name: str, original_file_name: str, schema, column_insight, logger):
    query = """
    INSERT INTO analysis_data (id, table_name, file_name, schema, column_insights, created_at)
    VALUES ($1, $2, $3, $4, $5, $6)
    """

    values = (
        id,
        table_name,
        original_file_name,
        schema,
        column_insight,
        datetime.now(timezone.utc)
    )

    try:
        await conn.execute(query, *values)
        logger.info("Successfully inserted analysis data into the database.")
    except Exception as e:
        logger.error(f"Failed to insert analysis data: {e}")
        raise