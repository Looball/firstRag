from fastapi import FastAPI

from app.api import (
    auth,
    chat,
    conversations,
    knowledge_bases,
    knowledge_files,
    vector_indexes,
)


def create_app() -> FastAPI:
    app = FastAPI()
    app.include_router(auth.router)
    app.include_router(chat.router)
    app.include_router(conversations.router)
    app.include_router(knowledge_bases.router)
    app.include_router(knowledge_files.router)
    app.include_router(vector_indexes.router)
    return app


app = create_app()
