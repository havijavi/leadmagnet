from typing import Optional
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_member
from app.db import get_session
from app.models import EnrichmentRun, Lead
from app.schemas import (
    EnrichmentBatchRequest,
    EnrichmentRequest,
    EnrichmentRunOut,
)
from app.services.enrichment import available_providers
from app.services.enrichment.types import Subject
from app.services.enrichment.waterfall import run_waterfall
from app.workers.enrichment_worker import enrich_batch, enrich_lead, enrich_pending

router = APIRouter(dependencies=[Depends(require_member)])


@router.get("/providers")
async def providers() -> dict:
    return {"providers": available_providers()}


@router.post("/run")
async def run(payload: EnrichmentRequest) -> dict:
    if payload.lead_id:
        return await enrich_lead(payload.lead_id, providers=payload.providers)
    subject = Subject(
        name=payload.name,
        company=payload.company,
        email=payload.email,
        domain=payload.domain,
        linkedin_url=payload.linkedin_url,
    )
    return await run_waterfall(subject, only_providers=payload.providers, lead_id=None)


@router.post("/batch", status_code=202)
async def batch(payload: EnrichmentBatchRequest, bg: BackgroundTasks, session: AsyncSession = Depends(get_session)) -> dict:
    if payload.lead_ids:
        bg.add_task(enrich_batch, payload.lead_ids, payload.providers)
        return {"queued": True, "count": len(payload.lead_ids)}
    if payload.target_list_id:
        rows = await session.scalars(
            select(Lead.id).where(Lead.target_list_id == payload.target_list_id)
        )
        ids = [r for r in rows]
        bg.add_task(enrich_batch, ids, payload.providers)
        return {"queued": True, "count": len(ids)}
    bg.add_task(enrich_pending, 50, payload.providers)
    return {"queued": True, "count": "pending leads (up to 50)"}


@router.get("/runs", response_model=list[EnrichmentRunOut])
async def runs(
    session: AsyncSession = Depends(get_session),
    lead_id: Optional[UUID] = None,
    limit: int = 50,
) -> list[EnrichmentRunOut]:
    stmt = select(EnrichmentRun).order_by(EnrichmentRun.created_at.desc()).limit(limit)
    if lead_id:
        stmt = stmt.where(EnrichmentRun.lead_id == lead_id)
    rows = await session.scalars(stmt)
    return [EnrichmentRunOut.model_validate(r) for r in rows]
