"""HTTP routes for ADR create, list, read, update, beacon-save, and search."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response

from application.commands.create_adr import CreateAdrCommand, CreateAdrCommandHandler
from application.commands.publish_adr import (
    PublishAdrCommand,
    PublishAdrCommandHandler,
)
from application.commands.submit_adr_for_review import (
    SubmitAdrForReviewCommand,
    SubmitAdrForReviewCommandHandler,
)
from application.commands.update_adr_content import (
    UpdateAdrContentCommand,
    UpdateAdrContentCommandHandler,
)
from application.ports.adr_repository import AdrReadModel
from application.queries.get_adr import GetAdrQuery, GetAdrQueryHandler
from application.queries.get_adr_review_status import (
    AdrReviewStatus,
    GetAdrReviewStatusQuery,
    GetAdrReviewStatusQueryHandler,
)
from application.queries.list_adrs import ListAdrsQuery, ListAdrsQueryHandler
from application.queries.search_adrs_by_title import (
    SearchAdrsByTitleQuery,
    SearchAdrsByTitleQueryHandler,
)
from domain.errors import (
    AdrAccessDenied,
    AdrNotFound,
    AdrTitleAlreadyExists,
    DomainError,
)
from infrastructure.api.dependencies import (
    get_create_adr_handler,
    get_current_user_id,
    get_get_adr_handler,
    get_get_adr_review_status_handler,
    get_list_adrs_handler,
    get_publish_adr_handler,
    get_search_adrs_handler,
    get_submit_adr_for_review_handler,
    get_update_adr_content_handler,
)
from infrastructure.api.schemas.adr import (
    AdrResponse,
    AdrSummary,
    CreateAdrRequest,
    CreateAdrResponse,
    ListAdrsResponse,
    ReviewAnnotationResponse,
    ReviewErrorResponse,
    ReviewStatusResponse,
    SearchAdrsResponse,
    UpdateAdrRequest,
)
from application.logging import get_logger

router = APIRouter(prefix="/adrs", tags=["adrs"])
_logger = get_logger(__name__)


def _domain_error_reason(exc: DomainError) -> str:
    if exc.message:
        return exc.message
    return getattr(type(exc), "kind", "domain_error")


@router.post("/{adr_id}/submit-review", status_code=202)
async def submit_adr_for_review(
    adr_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    handler: SubmitAdrForReviewCommandHandler = Depends(
        get_submit_adr_for_review_handler
    ),
) -> Response:
    adr_id_str = str(adr_id)
    try:
        result = await handler.handle(
            SubmitAdrForReviewCommand(adr_id=adr_id, user_id=user_id)
        )
    except AdrNotFound:
        _logger.info(
            "route.adrs.submit_review.rejected",
            adr_id=adr_id_str,
            status_code=404,
            reason="adr_not_found",
        )
        raise HTTPException(status_code=404, detail="ADR not found") from None
    except DomainError as exc:
        reason = _domain_error_reason(exc)
        _logger.info(
            "route.adrs.submit_review.rejected",
            adr_id=adr_id_str,
            status_code=400,
            reason=reason,
        )
        raise HTTPException(
            status_code=400,
            detail=reason,
        ) from None

    _logger.info(
        "route.adrs.submit_review.completed",
        adr_id=adr_id_str,
        status_code=202,
        stored_event_id=str(result.stored_event.id),
    )
    return Response(status_code=202)


@router.post("/{adr_id}/publish", status_code=204)
async def publish_adr(
    adr_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    handler: PublishAdrCommandHandler = Depends(get_publish_adr_handler),
) -> Response:
    adr_id_str = str(adr_id)
    try:
        await handler.handle(PublishAdrCommand(adr_id=adr_id, user_id=user_id))
    except AdrNotFound:
        _logger.info(
            "route.adrs.publish.rejected",
            adr_id=adr_id_str,
            status_code=404,
            reason="adr_not_found",
        )
        raise HTTPException(status_code=404, detail="ADR not found") from None
    except DomainError as exc:
        reason = _domain_error_reason(exc)
        _logger.info(
            "route.adrs.publish.rejected",
            adr_id=adr_id_str,
            status_code=400,
            reason=reason,
        )
        raise HTTPException(
            status_code=400,
            detail=reason,
        ) from None

    _logger.info(
        "route.adrs.publish.completed",
        adr_id=adr_id_str,
        status_code=204,
    )
    return Response(status_code=204)


@router.get("/{adr_id}/review-status", response_model=ReviewStatusResponse)
async def get_adr_review_status(
    adr_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    handler: GetAdrReviewStatusQueryHandler = Depends(
        get_get_adr_review_status_handler
    ),
) -> ReviewStatusResponse:
    try:
        status = await handler.handle(
            GetAdrReviewStatusQuery(adr_id=adr_id, user_id=user_id)
        )
    except AdrNotFound:
        _logger.info(
            "route.adrs.review_status.rejected",
            adr_id=str(adr_id),
            status_code=404,
            reason="adr_not_found",
        )
        raise HTTPException(status_code=404, detail="ADR not found") from None

    return _to_review_status_response(status)


@router.post("", status_code=201, response_model=CreateAdrResponse)
async def create_adr(
    body: CreateAdrRequest,
    user_id: UUID = Depends(get_current_user_id),
    handler: CreateAdrCommandHandler = Depends(get_create_adr_handler),
) -> CreateAdrResponse:
    try:
        adr_id = await handler.handle(
            CreateAdrCommand(user_id=user_id, title=body.title)
        )
    except AdrTitleAlreadyExists:
        _logger.info(
            "route.adrs.create_adr.rejected",
            status_code=409,
            reason="title_exists",
        )
        raise HTTPException(
            status_code=409,
            detail="An ADR with this title already exists",
        ) from None

    _logger.info(
        "route.adrs.create_adr.completed",
        adr_id=str(adr_id),
        status_code=201,
    )
    return CreateAdrResponse(id=adr_id)


@router.get("", response_model=ListAdrsResponse)
async def list_adrs(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    user_id: UUID = Depends(get_current_user_id),
    handler: ListAdrsQueryHandler = Depends(get_list_adrs_handler),
) -> ListAdrsResponse:
    results = await handler.handle(
        ListAdrsQuery(user_id=user_id, limit=limit, offset=offset)
    )
    return ListAdrsResponse(results=[_to_adr_summary(adr) for adr in results])


@router.get("/search", response_model=SearchAdrsResponse)
async def search_adrs(
    q: str = Query(min_length=1),
    user_id: UUID = Depends(get_current_user_id),
    handler: SearchAdrsByTitleQueryHandler = Depends(get_search_adrs_handler),
) -> SearchAdrsResponse:
    results = await handler.handle(SearchAdrsByTitleQuery(user_id=user_id, query=q))
    return SearchAdrsResponse(results=[_to_adr_summary(adr) for adr in results])


@router.get("/{adr_id}", response_model=AdrResponse)
async def get_adr(
    adr_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    handler: GetAdrQueryHandler = Depends(get_get_adr_handler),
) -> AdrResponse:
    try:
        adr = await handler.handle(GetAdrQuery(adr_id=adr_id, user_id=user_id))
    except AdrNotFound:
        _logger.info(
            "route.adrs.get_adr.rejected",
            adr_id=str(adr_id),
            status_code=404,
            reason="adr_not_found",
        )
        raise HTTPException(status_code=404, detail="ADR not found") from None

    return _to_adr_response(adr)


@router.patch("/{adr_id}", response_model=AdrResponse)
async def update_adr(
    adr_id: UUID,
    body: UpdateAdrRequest,
    user_id: UUID = Depends(get_current_user_id),
    update_handler: UpdateAdrContentCommandHandler = Depends(
        get_update_adr_content_handler
    ),
    get_handler: GetAdrQueryHandler = Depends(get_get_adr_handler),
) -> AdrResponse:
    await _handle_update(
        adr_id=adr_id,
        user_id=user_id,
        title=body.title,
        content=body.content,
        handler=update_handler,
        action="update_adr",
        success_status_code=200,
    )
    adr = await get_handler.handle(GetAdrQuery(adr_id=adr_id, user_id=user_id))
    return _to_adr_response(adr)


@router.post("/{adr_id}/save", status_code=204)
async def beacon_save_adr(
    adr_id: UUID,
    body: UpdateAdrRequest,
    user_id: UUID = Depends(get_current_user_id),
    handler: UpdateAdrContentCommandHandler = Depends(get_update_adr_content_handler),
) -> Response:
    await _handle_update(
        adr_id=adr_id,
        user_id=user_id,
        title=body.title,
        content=body.content,
        handler=handler,
        action="beacon_save_adr",
        success_status_code=204,
    )
    return Response(status_code=204)


async def _handle_update(
    *,
    adr_id: UUID,
    user_id: UUID,
    title: str | None,
    content: str | None,
    handler: UpdateAdrContentCommandHandler,
    action: str,
    success_status_code: int,
) -> None:
    adr_id_str = str(adr_id)
    try:
        await handler.handle(
            UpdateAdrContentCommand(
                adr_id=adr_id,
                user_id=user_id,
                title=title,
                content=content,
            )
        )
    except AdrNotFound:
        _log_update_rejected(
            action, adr_id_str, status_code=404, reason="adr_not_found"
        )
        raise HTTPException(status_code=404, detail="ADR not found") from None
    except AdrAccessDenied:
        _log_update_rejected(
            action, adr_id_str, status_code=403, reason="access_denied"
        )
        raise HTTPException(status_code=403, detail="Access denied") from None
    except AdrTitleAlreadyExists:
        _log_update_rejected(action, adr_id_str, status_code=409, reason="title_exists")
        raise HTTPException(
            status_code=409,
            detail="An ADR with this title already exists",
        ) from None
    except DomainError as exc:
        reason = _domain_error_reason(exc)
        _log_update_rejected(action, adr_id_str, status_code=400, reason=reason)
        raise HTTPException(
            status_code=400,
            detail=reason,
        ) from None

    _log_update_completed(action, adr_id_str, status_code=success_status_code)


def _log_update_rejected(
    action: str,
    adr_id: str,
    *,
    status_code: int,
    reason: str,
) -> None:
    if action == "update_adr":
        _logger.info(
            "route.adrs.update_adr.rejected",
            adr_id=adr_id,
            status_code=status_code,
            reason=reason,
        )
    else:
        _logger.info(
            "route.adrs.beacon_save_adr.rejected",
            adr_id=adr_id,
            status_code=status_code,
            reason=reason,
        )


def _log_update_completed(action: str, adr_id: str, *, status_code: int) -> None:
    if action == "update_adr":
        _logger.info(
            "route.adrs.update_adr.completed",
            adr_id=adr_id,
            status_code=status_code,
        )
    else:
        _logger.info(
            "route.adrs.beacon_save_adr.completed",
            adr_id=adr_id,
            status_code=status_code,
        )


def _to_review_status_response(status: AdrReviewStatus) -> ReviewStatusResponse:
    return ReviewStatusResponse(
        status=status.status,
        reviewed_at=status.reviewed_at,
        review_error=ReviewErrorResponse.from_metadata(status.review_error)
        if status.review_error is not None
        else None,
        annotation_counts=status.annotation_counts,
    )


def _to_adr_response(adr: AdrReadModel) -> AdrResponse:
    return AdrResponse(
        id=adr.id,
        title=adr.title,
        content=adr.content,
        status=adr.status,
        created_at=adr.created_at,
        updated_at=adr.updated_at,
        review_annotations=[
            ReviewAnnotationResponse(
                kind=annotation.kind,
                message=annotation.message,
                location=annotation.location,
                suggestion=annotation.suggestion,
            )
            for annotation in adr.review_annotations.annotations
        ]
        if adr.review_annotations is not None
        else None,
        reviewed_at=adr.reviewed_at,
        review_error=ReviewErrorResponse.from_metadata(adr.review_error)
        if adr.review_error is not None
        else None,
    )


def _to_adr_summary(adr: AdrReadModel) -> AdrSummary:
    return AdrSummary(
        id=adr.id,
        title=adr.title,
        status=adr.status,
        updated_at=adr.updated_at,
    )
