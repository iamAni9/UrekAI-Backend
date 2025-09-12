from datetime import datetime, timezone
from typing import Dict, Any
import asyncpg
from fastapi import HTTPException, status
from app.config.database_config.postgres import database as db
from app.utils.uniqueId import generate_unique_id

async def update_job_queue(job_data, queue_name, channel_name, payload, logger):
    try:
        async with db.transaction():
            await db.execute(f"""
                INSERT INTO {queue_name} (
                    upload_id, user_id, table_name, file_path, original_file_name, medium, receiver_no
                ) VALUES (
                    :upload_id, :user_id, :table_name, :file_path, :original_file_name, :medium, :receiver_no
                )
            """, values={
                 "upload_id": job_data["uploadId"],
                 "user_id": job_data["userid"],
                #  "email": job_data["email"],
                 "table_name": job_data["tableName"],
                 "file_path": job_data["filePath"],
                 "original_file_name": job_data["originalFileName"],
                 "medium": job_data.get("medium"),          # Use get() in case the field is optional
                 "receiver_no": job_data.get("receiver_no")
            })
            await db.execute(f"NOTIFY {channel_name}, '{payload}';")
        logger.info(f"Successfully added job {job_data['uploadId']} and sent notification.")
    except Exception as error:
        logger.error(f"Error inserting into {queue_name}: {error}")
        raise

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

async def delete_multiple_tables(files, tables, logger):
    try:
        query = f'DROP TABLE IF EXISTS "{"".join(tables)}" CASCADE'
        await db.execute(query)
        logger.info(f"Table '{tables}' deleted successfully.")
        
        values_clause = ', '.join(f"('{t}', '{f}')" for t, f in zip(tables, files))

        delete_query = f"""
            DELETE FROM analysis_data a
            WHERE EXISTS (
                SELECT 1 FROM (VALUES {values_clause}) AS v(table_name, file_name)
                WHERE a.table_name = v.table_name AND a.file_name = v.file_name
            );
        """

        await db.execute(delete_query)
        logger.info(f"Deleted rows from analysis_data for table/file pairs: {values_clause}")
       
    except Exception as e:
        logger.error(f"Error occurred while deleting table '{tables}': {e}")
        raise
    
async def delete_temp_table(conn, table_name, logger):
    try:
        query = f'DROP TABLE IF EXISTS "{table_name}" CASCADE'
        await conn.execute(query)
        logger.info(f"Table '{table_name}' deleted successfully.")
    except Exception as e:
        logger.error(f"Error occurred while deleting table '{table_name}': {e}")
        raise
    
async def update_upload_progress_in_queue(conn, queue_name, logger, upload_id, progress, status='processing'):
    try:
        query = f"""
                UPDATE {queue_name}
                SET status = $1, progress = $2
                WHERE upload_id = $3
                """
        await conn.execute(query, status, progress, upload_id)
        logger.info(f"{queue_name} updated")
    except Exception as e:
        logger.error(f"Error occurred while updating {queue_name}: {e}")
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

async def get_user_id_from_registered_no(number: str, logger):
    try:
        query = "SELECT id FROM registered_number WHERE number = :number"
        user_id = await db.fetch_val(query, {"number": number})
        return user_id
    except Exception as e:
        logger.error(f"Failed to retrieve user_id using number: {e}")
        return None
    
async def save_token_to_db(shop_name: str, access_token: str, email: str, owner_name: str, logger):
    new_id = generate_unique_id()
    now = datetime.now(timezone.utc)
    query = """
        WITH ins AS (
            INSERT INTO users (id, name, email, password, created_at, updated_at)
            VALUES (:id, :name, :email, :password, :created_at, :updated_at)
            ON CONFLICT (email) DO NOTHING
            RETURNING id
        )
        SELECT id FROM ins
        UNION
        SELECT id FROM users WHERE email = :email;
    """
    try:
        result = await db.fetch_one(query, {
            "id": new_id,
            "name": owner_name,
            "email": email,
            "password": "null_null",
            "created_at": now,
            "updated_at": now
        })

        user_id = result["id"]
    except Exception as e:
        logger.error(f"Failed to insert user data: {e}")
        raise
    
    query = """
    INSERT INTO registered_shopify_store (id, store_name, access_token, updated_at)
    VALUES ($1, $2, $3, $4)
    ON CONFLICT (id, store_name) DO UPDATE SET
        access_token = EXCLUDED.access_token,
        updated_at = EXCLUDED.updated_at;
    """
    values = (user_id, shop_name, access_token, now)
    
    try:
        await db.execute(query, *values)
        logger.info("Successfully inserted shopify data into the database.")
    except Exception as e:
        logger.error(f"Failed to insert shopify data: {e}")
        raise
    