from fastapi import FastAPI

from curlchat.api.routes.chat import router as chat_router
from curlchat.api.routes.health import router as health_router


def create_app() -> FastAPI:
    app = FastAPI(title="CurlChat API", version="0.1.0")
    app.include_router(health_router)
    app.include_router(chat_router)
    return app


app = create_app()
