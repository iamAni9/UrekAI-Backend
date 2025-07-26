from pydantic_settings import BaseSettings
# from typing import List

class Settings(BaseSettings):
    FRONTEND_ORIGIN: str
    SESSION_SECRET: str = "fallback-secret"
    ENV: str = "development"
    ENV_PORT: int = 10000
    DATABASE_URL: str
    DATABASE_URL_DIRECT: str
    GOOGLE_API_KEY: str
    SUPABASE_URL: str = "NA"
    SUPABASE_SERVICE_ROLE_KEY: str = "NA"
    FIREBASE_CREDENTIALS_JSON: str
    # CELERY_BROKER_URL: str
    # CELERY_RESULT_BACKEND: str
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"

settings = Settings()