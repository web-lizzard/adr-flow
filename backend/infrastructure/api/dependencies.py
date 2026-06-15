"""FastAPI dependencies for auth and handler resolution."""

from uuid import UUID

from fastapi import Depends, HTTPException, Request

from application.commands.register_user import RegisterUserCommandHandler
from application.ports.token_service import TokenService
from application.queries.authenticate_user import AuthenticateUserQueryHandler
from application.queries.get_current_user import GetCurrentUserQueryHandler
from infrastructure.config import Settings

SESSION_COOKIE_NAME = "session"


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_token_service(request: Request) -> TokenService:
    return request.app.state.token_service


def get_register_user_handler(request: Request) -> RegisterUserCommandHandler:
    return request.app.state.register_user_handler


def get_authenticate_user_handler(request: Request) -> AuthenticateUserQueryHandler:
    return request.app.state.authenticate_user_handler


def get_current_user_handler(request: Request) -> GetCurrentUserQueryHandler:
    return request.app.state.get_current_user_handler


def get_current_user_id(
    request: Request,
    token_service: TokenService = Depends(get_token_service),
) -> UUID:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if token is None:
        raise HTTPException(status_code=401, detail="Not authenticated")

    user_id = token_service.decode_token(token)
    if user_id is None:
        raise HTTPException(status_code=401, detail="Not authenticated")

    return user_id
