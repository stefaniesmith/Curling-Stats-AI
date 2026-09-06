from fastapi import FastAPI

from curlchat.api.routes.chat import router as chat_router
from curlchat.api.routes.conversations import router as conversations_router
from curlchat.api.routes.health import router as health_router
from curlchat.core.tracing import configure_tracing
from curlchat.db.session import get_settings


def create_app() -> FastAPI:
    app = FastAPI(title="CurlChat API", version="0.1.0")
    app.include_router(health_router)
    app.include_router(chat_router)
    app.include_router(conversations_router)
    configure_tracing(app, get_settings())
    return app


app = create_app()
