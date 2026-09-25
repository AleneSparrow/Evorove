"""Multipart file uploads for the owner materials library.

Imported only when python-multipart is installed so the rest of the API
can boot in a slim test venv.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, UploadFile, status

from src.domain.auth import StaffUser
from src.persistence.marketing_materials_service import MarketingMaterialsError

from ..dependencies import (
    BusinessIdPath,
    UnitOfWorkFactory,
    get_unit_of_work_factory,
    require_own_business,
)
from ..errors import RequestDataError
from ..schemas import MarketingPacketResponse
from .marketing_materials import _packet, _service

router = APIRouter(
    prefix="/api/v1/businesses/{business_id}/marketing-materials",
    tags=["marketing materials"],
    dependencies=[Depends(require_own_business)],
)


@router.post("/files", response_model=MarketingPacketResponse, status_code=status.HTTP_201_CREATED)
async def add_file_asset(
    business_id: BusinessIdPath,
    user: Annotated[StaffUser, Depends(require_own_business)],
    unit_of_work_factory: Annotated[UnitOfWorkFactory, Depends(get_unit_of_work_factory)],
    file: UploadFile = File(...),
    kind: str = Form("media"),
) -> MarketingPacketResponse:
    del kind
    service = _service(unit_of_work_factory)
    content = await file.read()
    try:
        service.add_file_asset(business_id, filename=file.filename or "upload", content=content)
    except MarketingMaterialsError as exc:
        raise RequestDataError(str(exc)) from exc
    return _packet(service, business_id)
