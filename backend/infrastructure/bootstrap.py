"""Composition root: wire ports to adapters and construct the FastAPI app."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from application.commands.create_adr import CreateAdrCommandHandler
from application.commands.publish_adr import PublishAdrCommandHandler
from application.commands.register_user import RegisterUserCommandHandler
from application.commands.submit_adr_for_review import SubmitAdrForReviewCommandHandler
from application.commands.update_adr_content import UpdateAdrContentCommandHandler
from application.handlers.run_ai_review import RunAiReviewHandler
from application.logging import get_logger
from application.queries.authenticate_user import AuthenticateUserQueryHandler
from application.queries.get_adr import GetAdrQueryHandler
from application.queries.get_adr_review_status import GetAdrReviewStatusQueryHandler
from application.queries.get_current_user import GetCurrentUserQueryHandler
from application.queries.list_adrs import ListAdrsQueryHandler
from application.queries.search_adrs_by_title import SearchAdrsByTitleQueryHandler
from application.runtime.dispatcher import EventDispatcher
from domain.adr import ADRSubmittedForReview
from infrastructure.adapters.auth.password_hasher import Argon2PasswordHasher
from infrastructure.adapters.auth.token_service import JwtTokenService
from infrastructure.adapters.persistence.event_store import SqlEventStore
from infrastructure.adapters.persistence.repositories.adr_repository import (
    SqlAdrRepository,
)
from infrastructure.adapters.persistence.repositories.user_repository import (
    SqlUserRepository,
)
from infrastructure.adapters.persistence.unit_of_work import SqlUnitOfWorkFactory
from infrastructure.api.middleware.request_logging import RequestLoggingMiddleware
from infrastructure.api.routers.adr import router as adr_router
from infrastructure.api.routers.auth import router as auth_router
from infrastructure.config import Settings, load_settings
from infrastructure.llm.factory import build_adr_review_service
from infrastructure.logging import configure_logging
from infrastructure.messaging.task_group_bus import TaskGroupEventBus

logger = get_logger(__name__)


async def _replay_unprocessed_events(
    session_factory: async_sessionmaker[AsyncSession],
    event_bus: TaskGroupEventBus,
) -> None:
    logger.info("bootstrap.replay_started")
    processed_at = datetime.now(UTC)
    async with session_factory() as session:
        async with session.begin():
            store = SqlEventStore(session)
            await store.mark_sync_projection_events_processed(processed_at=processed_at)
    total_batches = 0
    while await _drain_unprocessed_events(session_factory, event_bus) > 0:
        total_batches += 1
    logger.info("bootstrap.replay_completed", total_batches=total_batches)


async def _drain_unprocessed_events(
    session_factory: async_sessionmaker[AsyncSession],
    event_bus: TaskGroupEventBus,
) -> int:
    async with session_factory() as session:
        store = SqlEventStore(session)
        unprocessed = await store.load_unprocessed(limit=100)
    if unprocessed:
        logger.debug(
            "bootstrap.drain_batch",
            loaded_count=len(unprocessed),
            event_ids=[str(stored_event.id) for stored_event in unprocessed],
        )
        for stored_event in unprocessed:
            logger.info(
                "bootstrap.event_dispatched",
                stored_event_id=str(stored_event.id),
                event_type=type(stored_event.event).__name__,
            )
            await event_bus.dispatch_now(stored_event)
    return len(unprocessed)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or load_settings()
    configure_logging(log_json=settings.log_json, log_level=settings.log_level)

    engine = create_async_engine(
        settings.async_database_url,
        pool_pre_ping=True,
    )
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    uow_factory = SqlUnitOfWorkFactory(session_factory)
    user_repository = SqlUserRepository(session_factory)
    adr_repository = SqlAdrRepository(session_factory)
    password_hasher = Argon2PasswordHasher()
    token_service = JwtTokenService(secret_key=settings.jwt_secret)
    adr_review_service = build_adr_review_service(settings)

    register_user_handler = RegisterUserCommandHandler(
        uow_factory, user_repository, password_hasher
    )
    authenticate_user_handler = AuthenticateUserQueryHandler(
        user_repository, password_hasher
    )
    get_current_user_handler = GetCurrentUserQueryHandler(user_repository)
    create_adr_handler = CreateAdrCommandHandler(uow_factory, adr_repository)
    update_adr_content_handler = UpdateAdrContentCommandHandler(
        uow_factory, adr_repository
    )
    submit_adr_for_review_handler = SubmitAdrForReviewCommandHandler(
        uow_factory, adr_repository
    )
    publish_adr_handler = PublishAdrCommandHandler(uow_factory, adr_repository)
    get_adr_handler = GetAdrQueryHandler(adr_repository)
    get_adr_review_status_handler = GetAdrReviewStatusQueryHandler(adr_repository)
    search_adrs_handler = SearchAdrsByTitleQueryHandler(adr_repository)
    list_adrs_handler = ListAdrsQueryHandler(adr_repository)

    run_ai_review_handler = RunAiReviewHandler(
        uow_factory,
        adr_repository,
        adr_review_service,
    )
    dispatcher = EventDispatcher()
    dispatcher.register(ADRSubmittedForReview, run_ai_review_handler.handle)

    event_bus = TaskGroupEventBus()
    event_bus.set_dispatch(dispatcher.dispatch)

    async def drain_event_bus_once() -> int:
        return await _drain_unprocessed_events(session_factory, event_bus)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        logger.info("bootstrap.database_engine_created")
        logger.info(
            "bootstrap.llm_configured",
            provider=settings.llm_provider,
            model=settings.llm_model,
            base_url_configured=settings.llm_base_url is not None,
            api_key_configured=settings.llm_api_key is not None,
            timeout_seconds=settings.llm_timeout_seconds,
        )
        await _replay_unprocessed_events(session_factory, event_bus)
        poll_interval_seconds = 0.05
        event_bus.start_worker(
            lambda: _drain_unprocessed_events(session_factory, event_bus),
            poll_interval_seconds=poll_interval_seconds,
        )
        logger.info(
            "bootstrap.worker_started",
            poll_interval_seconds=poll_interval_seconds,
        )
        logger.info("bootstrap.ready")
        yield
        logger.info("bootstrap.shutdown_started")
        await event_bus.stop_worker()
        await engine.dispose()
        logger.info("bootstrap.engine_disposed")

    app = FastAPI(lifespan=lifespan)
    app.state.engine = engine
    app.state.user_repository = user_repository
    app.state.password_hasher = password_hasher
    app.state.token_service = token_service
    app.state.settings = settings
    app.state.event_bus = event_bus
    app.state.drain_event_bus_once = drain_event_bus_once
    app.state.register_user_handler = register_user_handler
    app.state.authenticate_user_handler = authenticate_user_handler
    app.state.get_current_user_handler = get_current_user_handler
    app.state.create_adr_handler = create_adr_handler
    app.state.update_adr_content_handler = update_adr_content_handler
    app.state.submit_adr_for_review_handler = submit_adr_for_review_handler
    app.state.publish_adr_handler = publish_adr_handler
    app.state.get_adr_handler = get_adr_handler
    app.state.get_adr_review_status_handler = get_adr_review_status_handler
    app.state.search_adrs_handler = search_adrs_handler
    app.state.list_adrs_handler = list_adrs_handler

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RequestLoggingMiddleware)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    api_router = APIRouter(prefix="/api")
    api_router.include_router(auth_router)
    api_router.include_router(adr_router)

    @api_router.get("/health")
    def api_health() -> dict[str, str]:
        return health()

    app.include_router(api_router)

    return app
