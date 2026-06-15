"""HTTP routes for registration, login, and current-user retrieval."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response

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
    SESSION_COOKIE_NAME,
    get_authenticate_user_handler,
    get_current_user_handler,
    get_current_user_id,
    get_register_user_handler,
    get_settings,
    get_token_service,
)
from infrastructure.api.schemas.auth import LoginRequest, RegisterRequest, UserResponse
from infrastructure.config import Settings

router = APIRouter(prefix="/auth", tags=["auth"])

SESSION_MAX_AGE_SECONDS = 86400


@router.post("/register", status_code=201, response_model=UserResponse)
async def register(
    body: RegisterRequest,
    response: Response,
    handler: RegisterUserCommandHandler = Depends(get_register_user_handler),
    token_service: TokenService = Depends(get_token_service),
    settings: Settings = Depends(get_settings),
    get_user_handler: GetCurrentUserQueryHandler = Depends(get_current_user_handler),
) -> UserResponse:
    try:
        user_id = await handler.handle(
            RegisterUserCommand(email=body.email, password=body.password)
        )
    except EmailAlreadyTaken:
        raise HTTPException(
            status_code=400,
            detail="Unable to create account with the provided credentials",
        ) from None
    except ValueObjectError as exc:
        raise HTTPException(
            status_code=400,
            detail=exc.message or exc.kind,
        ) from None

    token = token_service.create_token(user_id)
    _set_session_cookie(response, token, settings)

    user = await get_user_handler.handle(GetCurrentUserQuery(user_id=user_id))
    return _to_user_response(user)


@router.post("/login", response_model=UserResponse)
async def login(
    body: LoginRequest,
    response: Response,
    handler: AuthenticateUserQueryHandler = Depends(get_authenticate_user_handler),
    token_service: TokenService = Depends(get_token_service),
    settings: Settings = Depends(get_settings),
    get_user_handler: GetCurrentUserQueryHandler = Depends(get_current_user_handler),
) -> UserResponse:
    try:
        user_id = await handler.handle(
            AuthenticateUserQuery(email=body.email, password=body.password)
        )
    except InvalidCredentials:
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password",
        ) from None

    token = token_service.create_token(user_id)
    _set_session_cookie(response, token, settings)

    user = await get_user_handler.handle(GetCurrentUserQuery(user_id=user_id))
    return _to_user_response(user)


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


def _set_session_cookie(
    response: Response,
    token: str,
    settings: Settings,
) -> None:
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path=settings.cookie_path,
        max_age=SESSION_MAX_AGE_SECONDS,
    )


def _to_user_response(user: UserReadModel) -> UserResponse:
    return UserResponse(
        id=user.id,
        email=user.email,
        created_at=user.created_at,
    )
