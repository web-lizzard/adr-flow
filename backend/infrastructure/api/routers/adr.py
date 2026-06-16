"""HTTP routes for ADR create, read, update, beacon-save, and search."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response

from application.commands.create_adr import CreateAdrCommand, CreateAdrCommandHandler
from application.commands.update_adr_content import (
    UpdateAdrContentCommand,
    UpdateAdrContentCommandHandler,
)
from application.ports.adr_repository import AdrReadModel
from application.queries.get_adr import GetAdrQuery, GetAdrQueryHandler
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
    get_search_adrs_handler,
    get_update_adr_content_handler,
)
from infrastructure.api.schemas.adr import (
    AdrResponse,
    AdrSummary,
    CreateAdrRequest,
    CreateAdrResponse,
    SearchAdrsResponse,
    UpdateAdrRequest,
)

router = APIRouter(prefix="/adrs", tags=["adrs"])


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
        raise HTTPException(
            status_code=409,
            detail="An ADR with this title already exists",
        ) from None

    return CreateAdrResponse(id=adr_id)


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
    )
    return Response(status_code=204)


async def _handle_update(
    *,
    adr_id: UUID,
    user_id: UUID,
    title: str | None,
    content: str | None,
    handler: UpdateAdrContentCommandHandler,
) -> None:
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
        raise HTTPException(status_code=404, detail="ADR not found") from None
    except AdrAccessDenied:
        raise HTTPException(status_code=403, detail="Access denied") from None
    except AdrTitleAlreadyExists:
        raise HTTPException(
            status_code=409,
            detail="An ADR with this title already exists",
        ) from None
    except DomainError as exc:
        raise HTTPException(
            status_code=400,
            detail=exc.message or exc.kind,
        ) from None


def _to_adr_response(adr: AdrReadModel) -> AdrResponse:
    return AdrResponse(
        id=adr.id,
        title=adr.title,
        content=adr.content,
        status=adr.status,
        created_at=adr.created_at,
        updated_at=adr.updated_at,
    )


def _to_adr_summary(adr: AdrReadModel) -> AdrSummary:
    return AdrSummary(
        id=adr.id,
        title=adr.title,
        status=adr.status,
        updated_at=adr.updated_at,
    )
