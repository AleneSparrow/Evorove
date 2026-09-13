"""Owner marketing packet for cycle 2 wording. Refresh publishes a snapshot."""

from typing import Annotated

from fastapi import APIRouter, Depends, status

from src.domain.auth import StaffUser
from src.persistence.marketing_materials_service import (
    MarketingMaterialsError,
    MarketingMaterialsService,
)

from ..dependencies import (
    BusinessIdPath,
    UnitOfWorkFactory,
    get_unit_of_work_factory,
    require_own_business,
)
from ..errors import RequestDataError
from ..schemas import (
    MarketingAssetSchema,
    MarketingGuidanceSchema,
    MarketingPacketResponse,
    MarketingTextAssetRequest,
)


router = APIRouter(
    prefix="/api/v1/businesses/{business_id}/marketing-materials",
    tags=["marketing materials"],
    dependencies=[Depends(require_own_business)],
)


def _service(factory: UnitOfWorkFactory) -> MarketingMaterialsService:
    return MarketingMaterialsService(factory)


def _packet(service: MarketingMaterialsService, business_id: str) -> MarketingPacketResponse:
    assets, guidance = service.list_packet(business_id)
    pending = True
    if guidance is not None:
        snapshot = _snapshot_of(assets)
        pending = snapshot != guidance.snapshot_text
    elif assets:
        pending = True
    else:
        pending = False
    return MarketingPacketResponse(
        assets=tuple(MarketingAssetSchema.from_domain(asset) for asset in assets),
        guidance=MarketingGuidanceSchema.from_domain(guidance) if guidance is not None else None,
        pending=pending,
    )


def _snapshot_of(assets) -> str:
    from src.domain.marketing_materials import encode_snapshot

    return encode_snapshot(assets)


@router.get("", response_model=MarketingPacketResponse)
def get_packet(
    business_id: BusinessIdPath,
    user: Annotated[StaffUser, Depends(require_own_business)],
    unit_of_work_factory: Annotated[UnitOfWorkFactory, Depends(get_unit_of_work_factory)],
) -> MarketingPacketResponse:
    return _packet(_service(unit_of_work_factory), business_id)


@router.post("", response_model=MarketingPacketResponse, status_code=status.HTTP_201_CREATED)
def add_text_asset(
    business_id: BusinessIdPath,
    body: MarketingTextAssetRequest,
    user: Annotated[StaffUser, Depends(require_own_business)],
    unit_of_work_factory: Annotated[UnitOfWorkFactory, Depends(get_unit_of_work_factory)],
) -> MarketingPacketResponse:
    service = _service(unit_of_work_factory)
    try:
        service.add_text_asset(business_id, kind=body.kind, title=body.title, body_text=body.body_text)
    except MarketingMaterialsError as exc:
        raise RequestDataError(str(exc)) from exc
    return _packet(service, business_id)


@router.post("/activate", response_model=MarketingPacketResponse)
def activate_packet(
    business_id: BusinessIdPath,
    user: Annotated[StaffUser, Depends(require_own_business)],
    unit_of_work_factory: Annotated[UnitOfWorkFactory, Depends(get_unit_of_work_factory)],
) -> MarketingPacketResponse:
    service = _service(unit_of_work_factory)
    try:
        service.activate(business_id)
    except MarketingMaterialsError as exc:
        raise RequestDataError(str(exc)) from exc
    return _packet(service, business_id)
