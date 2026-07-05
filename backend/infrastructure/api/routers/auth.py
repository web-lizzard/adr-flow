"""HTTP routes for registration, login, and current-user retrieval."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from application.commands.register_user import (
    RegisterUserCommand,
    RegisterUserCommandHandler,
)
from application.ports.token_service import TokenService
from application.ports.user_repository import UserReadModel
from application.queries.authenticate_user import (
    AuthenticateUserQuery,
    AuthenticateUserQueryHandler,
)
from application.queries.get_current_user import (
    GetCurrentUserQuery,
    GetCurrentUserQueryHandler,
)
from domain.errors import (
    EmailAlreadyTaken,
    InvalidCredentials,
    UserNotFound,
    ValueObjectError,
)
from infrastructure.api.dependencies import (
    get_authenticate_user_handler,
    get_current_user_handler,
    get_current_user_id,
    get_register_user_handler,
    get_token_service,
)
from infrastructure.api.schemas.auth import (
    AuthResponse,
    LoginRequest,
    RegisterRequest,
    UserResponse,
)
from application.logging import get_logger

router = APIRouter(prefix="/auth", tags=["auth"])
_logger = get_logger(__name__)


@router.post("/register", status_code=201, response_model=AuthResponse)
async def register(
    body: RegisterRequest,
    handler: RegisterUserCommandHandler = Depends(get_register_user_handler),
    token_service: TokenService = Depends(get_token_service),
) -> AuthResponse:
    try:
        user_id = await handler.handle(
            RegisterUserCommand(email=body.email, password=body.password)
        )
    except EmailAlreadyTaken:
        _logger.info(
            "route.auth.register.rejected",
            reason="email_already_taken",
            status_code=400,
        )
        raise HTTPException(
            status_code=400,
            detail="Unable to create account with the provided credentials",
        ) from None
    except ValueObjectError as exc:
        _logger.info(
            "route.auth.register.rejected",
            reason=exc.kind,
            status_code=400,
        )
        raise HTTPException(
            status_code=400,
            detail=exc.message or exc.kind,
        ) from None

    token = token_service.create_token(user_id)
    _logger.info("route.auth.register.completed", status_code=201)
    return AuthResponse(access_token=token)


@router.post("/login", response_model=AuthResponse)
async def login(
    body: LoginRequest,
    handler: AuthenticateUserQueryHandler = Depends(get_authenticate_user_handler),
    token_service: TokenService = Depends(get_token_service),
) -> AuthResponse:
    try:
        user_id = await handler.handle(
            AuthenticateUserQuery(email=body.email, password=body.password)
        )
    except InvalidCredentials:
        _logger.info(
            "route.auth.login.rejected",
            reason="invalid_credentials",
            status_code=401,
        )
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password",
        ) from None

    token = token_service.create_token(user_id)
    _logger.info("route.auth.login.completed", status_code=200)
    return AuthResponse(access_token=token)


@router.get("/me", response_model=UserResponse)
async def me(
    user_id: UUID = Depends(get_current_user_id),
    handler: GetCurrentUserQueryHandler = Depends(get_current_user_handler),
) -> UserResponse:
    try:
        user = await handler.handle(GetCurrentUserQuery(user_id=user_id))
    except UserNotFound:
        raise HTTPException(status_code=401, detail="Not authenticated") from None

    return _to_user_response(user)


def _to_user_response(user: UserReadModel) -> UserResponse:
    return UserResponse(
        id=user.id,
        email=user.email,
        created_at=user.created_at,
    )
