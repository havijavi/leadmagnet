from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_admin, require_any
from app.db import get_session
from app.models import ServiceOffering
from app.schemas import ServiceOfferingIn, ServiceOfferingOut

router = APIRouter()


@router.get("", response_model=list[ServiceOfferingOut], dependencies=[Depends(require_any)])
async def list_services(session: AsyncSession = Depends(get_session)) -> list[ServiceOfferingOut]:
    rows = await session.scalars(select(ServiceOffering).order_by(ServiceOffering.created_at.desc()))
    return [ServiceOfferingOut.model_validate(r) for r in rows]


@router.post("", response_model=ServiceOfferingOut, status_code=201, dependencies=[Depends(require_admin)])
async def create_service(
    payload: ServiceOfferingIn,
    session: AsyncSession = Depends(get_session),
) -> ServiceOfferingOut:
    obj = ServiceOffering(**payload.model_dump())
    session.add(obj)
    await session.commit()
    await session.refresh(obj)
    return ServiceOfferingOut.model_validate(obj)


@router.put("/{service_id}", response_model=ServiceOfferingOut, dependencies=[Depends(require_admin)])
async def update_service(
    service_id: UUID,
    payload: ServiceOfferingIn,
    session: AsyncSession = Depends(get_session),
) -> ServiceOfferingOut:
    obj = await session.get(ServiceOffering, service_id)
    if not obj:
        raise HTTPException(404, "service not found")
    for k, v in payload.model_dump().items():
        setattr(obj, k, v)
    await session.commit()
    await session.refresh(obj)
    return ServiceOfferingOut.model_validate(obj)


@router.delete("/{service_id}", status_code=204, dependencies=[Depends(require_admin)])
async def delete_service(service_id: UUID, session: AsyncSession = Depends(get_session)) -> None:
    obj = await session.get(ServiceOffering, service_id)
    if obj:
        await session.delete(obj)
        await session.commit()
