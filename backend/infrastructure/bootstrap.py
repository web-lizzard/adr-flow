"""Composition root: wire ports to adapters and construct the FastAPI app."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from application.commands.register_user import RegisterUserCommandHandler
from application.queries.authenticate_user import AuthenticateUserQueryHandler
from application.queries.get_current_user import GetCurrentUserQueryHandler
from infrastructure.adapters.auth.password_hasher import Argon2PasswordHasher
from infrastructure.adapters.auth.token_service import JwtTokenService
from infrastructure.adapters.persistence.repositories.user_repository import (
    SqlUserRepository,
)
from infrastructure.adapters.persistence.unit_of_work import SqlUnitOfWorkFactory
from infrastructure.api.routers.auth import router as auth_router
from infrastructure.config import Settings

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()

    engine = create_async_engine(
        settings.async_database_url,
        pool_pre_ping=True,
    )
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    uow_factory = SqlUnitOfWorkFactory(session_factory)
    user_repository = SqlUserRepository(session_factory)
    password_hasher = Argon2PasswordHasher()
    token_service = JwtTokenService(secret_key=settings.jwt_secret)

    register_user_handler = RegisterUserCommandHandler(
        uow_factory, user_repository, password_hasher
    )
    authenticate_user_handler = AuthenticateUserQueryHandler(
        user_repository, password_hasher
    )
    get_current_user_handler = GetCurrentUserQueryHandler(user_repository)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        logger.info("Database engine created")
        yield
        await engine.dispose()

    app = FastAPI(lifespan=lifespan)
    app.state.engine = engine
    app.state.user_repository = user_repository
    app.state.password_hasher = password_hasher
    app.state.token_service = token_service
    app.state.settings = settings
    app.state.register_user_handler = register_user_handler
    app.state.authenticate_user_handler = authenticate_user_handler
    app.state.get_current_user_handler = get_current_user_handler

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

    api_router = APIRouter(prefix="/api")
    api_router.include_router(auth_router)

    @api_router.get("/health")
    def api_health() -> dict[str, str]:
        return health()

    app.include_router(api_router)

    return app
