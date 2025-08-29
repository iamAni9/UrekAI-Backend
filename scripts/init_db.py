import os
import time
import psycopg2
from psycopg2.extras import RealDictCursor
# from dotenv import load_dotenv

# load_dotenv()

print("Starting database initialization script...")
time.sleep(5) 

try:
    conn = psycopg2.connect(
        dsn=os.environ["DATABASE_URL"],
        cursor_factory=RealDictCursor
    )
    print("Successfully connected to PostgreSQL!")

    with conn.cursor() as cursor:
        print("Creating tables if they don't exist...")

        cursor.execute("""
           CREATE TABLE IF NOT EXISTS users (
                id UUID PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                email VARCHAR(255) NOT NULL UNIQUE,
                password VARCHAR(255) NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
        """)
        print("- Table 'users' checked/created.")
        
        cursor.execute("""
           CREATE TABLE IF NOT EXISTS registered_number (
                id UUID NOT NULL,
                number TEXT NOT NULL,
                
                CONSTRAINT registered_number_pkey PRIMARY KEY (id, number),
                CONSTRAINT fk_user_id FOREIGN KEY (id) REFERENCES users(id) ON DELETE CASCADE
            );
            
            CREATE INDEX IF NOT EXISTS idx_registered_number_id ON registered_number(id);
        """)
        print("- Table 'registered_number' checked/created.")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS analysis_data (
                id UUID NOT NULL,       
                table_name VARCHAR(255) NOT NULL,
                file_name VARCHAR(255) NOT NULL,
                schema JSONB NOT NULL,
                column_insights JSONB NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,

                CONSTRAINT analysis_data_pkey PRIMARY KEY (id, table_name),
                CONSTRAINT fk_user_id FOREIGN KEY (id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_analysis_data_id ON analysis_data(id); 
        """)
        print("- Table 'analysis_data' checked/created.")

        cursor.execute("""
            CREATE UNLOGGED TABLE IF NOT EXISTS csv_queue (
                id SERIAL PRIMARY KEY,
                upload_id UUID UNIQUE NOT NULL,
                user_id TEXT NOT NULL,
                table_name TEXT NOT NULL,
                file_path TEXT NOT NULL,
                original_file_name TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                progress SMALLINT NOT NULL DEFAULT 0,
                medium TEXT NULL,
                receiver_no TEXT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );

            CREATE INDEX IF NOT EXISTS idx_csv_queue_status_upload_id_progress
                ON csv_queue (status, upload_id, progress);
        """)
        print(" - Table 'csv_queue' checked/created.")
        
        cursor.execute("""
            CREATE UNLOGGED TABLE IF NOT EXISTS excel_queue (
                id SERIAL PRIMARY KEY,
                upload_id UUID UNIQUE NOT NULL,
                user_id TEXT NOT NULL,
                table_name TEXT NOT NULL,
                file_path TEXT NOT NULL,
                original_file_name TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                progress SMALLINT NOT NULL DEFAULT 0,
                medium TEXT NULL,
                receiver_no TEXT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );

            CREATE INDEX IF NOT EXISTS idx_excel_queue_status_upload_id_progress
                ON excel_queue (status, upload_id, progress)
                    """)
        print(" - Table 'excel_queue' checked/created.")

        conn.commit()
        print("✅ Database initialization complete. Tables are ready.")

except psycopg2.OperationalError as e:
    print(f"Could not connect to the database: {e}")
    exit(1)
except Exception as e:
    print(f"An unexpected error occurred: {e}")
    exit(1)
finally:
    if 'conn' in locals() and conn is not None:
        conn.close()