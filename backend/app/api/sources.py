from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_admin
from app.db import get_session
from app.models import LeadSource
from app.schemas import LeadSourceIn, LeadSourceOut
from app.sources import REGISTRY

router = APIRouter(dependencies=[Depends(require_admin)])


@router.get("/kinds")
async def list_kinds() -> dict:
    return {"kinds": sorted(REGISTRY.keys())}


@router.get("", response_model=list[LeadSourceOut])
async def list_sources(session: AsyncSession = Depends(get_session)) -> list[LeadSourceOut]:
    rows = await session.scalars(select(LeadSource).order_by(LeadSource.created_at.desc()))
    return [LeadSourceOut.model_validate(r) for r in rows]


@router.post("", response_model=LeadSourceOut, status_code=201)
async def create_source(payload: LeadSourceIn, session: AsyncSession = Depends(get_session)) -> LeadSourceOut:
    if payload.kind not in REGISTRY:
        raise HTTPException(400, f"unknown kind {payload.kind!r}; valid: {sorted(REGISTRY)}")
    obj = LeadSource(**payload.model_dump())
    session.add(obj)
    await session.commit()
    await session.refresh(obj)
    return LeadSourceOut.model_validate(obj)


@router.put("/{source_id}", response_model=LeadSourceOut)
async def update_source(
    source_id: UUID,
    payload: LeadSourceIn,
    session: AsyncSession = Depends(get_session),
) -> LeadSourceOut:
    obj = await session.get(LeadSource, source_id)
    if not obj:
        raise HTTPException(404, "source not found")
    for k, v in payload.model_dump().items():
        setattr(obj, k, v)
    await session.commit()
    await session.refresh(obj)
    return LeadSourceOut.model_validate(obj)


@router.delete("/{source_id}", status_code=204)
async def delete_source(source_id: UUID, session: AsyncSession = Depends(get_session)) -> None:
    obj = await session.get(LeadSource, source_id)
    if obj:
        await session.delete(obj)
        await session.commit()
