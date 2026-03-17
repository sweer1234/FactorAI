from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session

from .api import router
from .config import settings
from .db import engine, init_db
from .seed import seed_if_empty


def create_app() -> FastAPI:
    sqlite_file = Path(settings.sqlite_path)
    sqlite_file.parent.mkdir(parents=True, exist_ok=True)
    init_db()
    with Session(engine) as session:
        seed_if_empty(session)

    app = FastAPI(title=settings.app_name)

    origins = [origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router, prefix=settings.api_prefix)
    return app


app = create_app()
