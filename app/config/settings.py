from pydantic_settings import BaseSettings
# from typing import List

class Settings(BaseSettings):
    FRONTEND_ORIGIN: str
    SESSION_SECRET: str = "fallback-secret"
    NODE_ENV: str = "development"
    PORT: int = 8000
    DATABASE_URL: str
    GOOGLE_API_KEY: str
    # CELERY_BROKER_URL: str
    # CELERY_RESULT_BACKEND: str
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"

settings = Settings()
