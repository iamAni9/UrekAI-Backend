from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse
from starlette.middleware.sessions import SessionMiddleware
from app.config.settings import settings
from app.config.logger import logger
from app.routes import register_routers
from app.config.postgres import database as db
from contextlib import asynccontextmanager


def create_app() -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Startup
        try:
            await db.connect()
            logger.info("Database connected")
        except Exception as e:
            logger.critical("Failed to connect to database", exc_info=True)
            raise

        yield

        # Shutdown
        try:
            await db.disconnect()
            logger.info("Database disconnected")
        except Exception as e:
            logger.error("Error closing database connections", exc_info=True)

    app = FastAPI(lifespan=lifespan)

    allowed_origins = [origin.strip() for origin in settings.FRONTEND_ORIGIN.split(",")]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.SESSION_SECRET,
        session_cookie="session",
        same_site="none" if settings.ENV_PORT == "production" else "lax",
        https_only=(settings.ENV_PORT == "production"),
        max_age=3600 * 24 * 7,
    )

    # Routers
    register_routers(app)

    @app.get("/")
    async def home():
        logger.info("Home route accessed")
        return {"message": "Welcome to the API"}

    @app.get("/health")
    async def health():
        logger.info("Health check accessed")
        return {"status": "healthy"}

    @app.middleware("http")
    async def catch_json_errors(request: Request, call_next):
        try:
            return await call_next(request)
        except Exception as e:
            logger.error(f"Unhandled error: {str(e)}")
            return JSONResponse(status_code=500, content={"error": "Internal Server Error"})

    return app
