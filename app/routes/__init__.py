from fastapi import FastAPI
from .v1.users import router as user_router_v1
from .v1.data import router as data_router_v1
from .v1.chat import router as chat_router_v1
from .v2.chat import router as chat_router_v2
from .v2.integration import router as integration_router

def register_routers(app: FastAPI):
    app.include_router(user_router_v1, prefix="/v1/api/users")
    app.include_router(data_router_v1, prefix="/v1/api/data")
    app.include_router(chat_router_v1, prefix="/v1/api/chat")
    app.include_router(chat_router_v2, prefix="/v2/api/chat")
    app.include_router(integration_router, prefix="/v2/api/integration")
