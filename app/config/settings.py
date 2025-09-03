from pydantic_settings import BaseSettings
# from pydantic import BaseSettings
# from typing import List

class Settings(BaseSettings):
    FRONTEND_ORIGIN: str
    SESSION_SECRET: str = "fallback-secret"
    ENV: str = "development"
    ENV_PORT: int = 10000
    APP_URL: str
    DATABASE_URL: str
    DATABASE_URL_DIRECT: str
    GOOGLE_API_KEY: str
    FIREBASE_CREDENTIALS_JSON: str
    INFOBIP_BASE_URL: str
    INFOBIP_API_KEY: str
    META_ACCESS_TOKEN: str
    META_PHONE_NUMBER_ID: str
    META_API_VERSION: str
    META_VERIFY_TOKEN: str
    SHOPIFY_CLIENT_ID: str = None
    SHOPIFY_CLIENT_SECRET: str = None
    SHOPIFY_SCOPES: str = None
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"

settings = Settings()