from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_admin
from app.db import get_session
from app.models import Lead
from app.schemas import LeadOut, LeadUpdate
from app.services.crm_push import fire_event

router = APIRouter(dependencies=[Depends(require_admin)])


@router.get("", response_model=list[LeadOut])
async def list_leads(
    session: AsyncSession = Depends(get_session),
    status: Optional[str] = Query(None),
    enrichment_status: Optional[str] = Query(None),
    target_list_id: Optional[UUID] = Query(None),
    min_score: int = Query(0, ge=0, le=100),
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0),
) -> list[LeadOut]:
    stmt = select(Lead).where(Lead.fit_score >= min_score)
    if status:
        stmt = stmt.where(Lead.status == status)
    if enrichment_status:
        stmt = stmt.where(Lead.enrichment_status == enrichment_status)
    if target_list_id:
        stmt = stmt.where(Lead.target_list_id == target_list_id)
    stmt = stmt.order_by(desc(Lead.fit_score), desc(Lead.created_at)).limit(limit).offset(offset)
    rows = await session.scalars(stmt)
    return [LeadOut.model_validate(r) for r in rows]


@router.get("/{lead_id}", response_model=LeadOut)
async def get_lead(lead_id: UUID, session: AsyncSession = Depends(get_session)) -> LeadOut:
    obj = await session.get(Lead, lead_id)
    if not obj:
        raise HTTPException(404, "lead not found")
    return LeadOut.model_validate(obj)


@router.patch("/{lead_id}", response_model=LeadOut)
async def update_lead(
    lead_id: UUID,
    payload: LeadUpdate,
    session: AsyncSession = Depends(get_session),
) -> LeadOut:
    obj = await session.get(Lead, lead_id)
    if not obj:
        raise HTTPException(404, "lead not found")
    prev_status = obj.status
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(obj, k, v)
    await session.commit()
    await session.refresh(obj)

    if payload.status and payload.status != prev_status:
        evt = f"lead.{payload.status}"
        try:
            await fire_event(evt, lead_id)
        except Exception:
            pass
    return LeadOut.model_validate(obj)


@router.delete("/{lead_id}", status_code=204)
async def delete_lead(lead_id: UUID, session: AsyncSession = Depends(get_session)) -> None:
    obj = await session.get(Lead, lead_id)
    if obj:
        await session.delete(obj)
        await session.commit()
