"""FastAPI dependencies for auth and handler resolution."""

from uuid import UUID

from fastapi import Depends, HTTPException, Request

from application.commands.create_adr import CreateAdrCommandHandler
from application.commands.publish_adr import PublishAdrCommandHandler
from application.commands.register_user import RegisterUserCommandHandler
from application.commands.submit_adr_for_review import SubmitAdrForReviewCommandHandler
from application.commands.update_adr_content import UpdateAdrContentCommandHandler
from application.ports.token_service import TokenService
from application.queries.authenticate_user import AuthenticateUserQueryHandler
from application.queries.get_adr import GetAdrQueryHandler
from application.queries.get_adr_review_status import GetAdrReviewStatusQueryHandler
from application.queries.get_current_user import GetCurrentUserQueryHandler
from application.queries.list_adrs import ListAdrsQueryHandler
from application.queries.search_adrs_by_title import SearchAdrsByTitleQueryHandler
from application.logging import get_logger
from infrastructure.config import Settings

SESSION_COOKIE_NAME = "session"
_logger = get_logger(__name__)


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


def get_create_adr_handler(request: Request) -> CreateAdrCommandHandler:
    return request.app.state.create_adr_handler


def get_update_adr_content_handler(
    request: Request,
) -> UpdateAdrContentCommandHandler:
    return request.app.state.update_adr_content_handler


def get_submit_adr_for_review_handler(
    request: Request,
) -> SubmitAdrForReviewCommandHandler:
    return request.app.state.submit_adr_for_review_handler


def get_publish_adr_handler(request: Request) -> PublishAdrCommandHandler:
    return request.app.state.publish_adr_handler


def get_get_adr_review_status_handler(
    request: Request,
) -> GetAdrReviewStatusQueryHandler:
    return request.app.state.get_adr_review_status_handler


def get_get_adr_handler(request: Request) -> GetAdrQueryHandler:
    return request.app.state.get_adr_handler


def get_search_adrs_handler(request: Request) -> SearchAdrsByTitleQueryHandler:
    return request.app.state.search_adrs_handler


def get_list_adrs_handler(request: Request) -> ListAdrsQueryHandler:
    return request.app.state.list_adrs_handler


def get_current_user_id(
    request: Request,
    token_service: TokenService = Depends(get_token_service),
) -> UUID:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if token is None:
        _logger.info("auth.missing_cookie", path=request.url.path)
        raise HTTPException(status_code=401, detail="Not authenticated")

    user_id = token_service.decode_token(token)
    if user_id is None:
        _logger.info("auth.invalid_token", path=request.url.path)
        raise HTTPException(status_code=401, detail="Not authenticated")

    return user_id
