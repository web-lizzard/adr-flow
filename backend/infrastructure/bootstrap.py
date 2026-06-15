"""Composition root: wire ports to adapters and construct the FastAPI app."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from infrastructure.adapters.auth.password_hasher import Argon2PasswordHasher
from infrastructure.adapters.auth.token_service import JwtTokenService
from infrastructure.adapters.persistence.event_store import SqlEventStore
from infrastructure.adapters.persistence.projections.user_projection import (
    SqlUserProjection,
)
from infrastructure.config import Settings

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()

    engine = create_async_engine(
        settings.async_database_url,
        pool_pre_ping=True,
    )
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    event_store = SqlEventStore(session_factory)
    user_projection = SqlUserProjection(session_factory)
    password_hasher = Argon2PasswordHasher()
    token_service = JwtTokenService(secret_key=settings.jwt_secret)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        logger.info("Database engine created")
        yield
        await engine.dispose()

    app = FastAPI(lifespan=lifespan)
    app.state.engine = engine
    app.state.session_factory = session_factory
    app.state.event_store = event_store
    app.state.user_projection = user_projection
    app.state.password_hasher = password_hasher
    app.state.token_service = token_service
    app.state.settings = settings

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app
