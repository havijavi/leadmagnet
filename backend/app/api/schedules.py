from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_admin
from app.db import get_session
from app.models import ScheduledJob
from app.schemas import ScheduledJobIn, ScheduledJobOut
from app.services.scheduler import reload_jobs

router = APIRouter(dependencies=[Depends(require_admin)])


VALID_KINDS = {"discovery", "enrichment_pending", "crm_sync"}


@router.get("/kinds")
async def kinds() -> dict:
    return {"kinds": sorted(VALID_KINDS)}


@router.get("", response_model=list[ScheduledJobOut])
async def list_jobs(session: AsyncSession = Depends(get_session)) -> list[ScheduledJobOut]:
    rows = await session.scalars(select(ScheduledJob).order_by(ScheduledJob.created_at.desc()))
    return [ScheduledJobOut.model_validate(r) for r in rows]


@router.post("", response_model=ScheduledJobOut, status_code=201)
async def create_job(payload: ScheduledJobIn, session: AsyncSession = Depends(get_session)) -> ScheduledJobOut:
    if payload.kind not in VALID_KINDS:
        raise HTTPException(400, f"invalid kind, valid: {sorted(VALID_KINDS)}")
    obj = ScheduledJob(**payload.model_dump())
    session.add(obj)
    await session.commit()
    await session.refresh(obj)
    await reload_jobs()
    return ScheduledJobOut.model_validate(obj)


@router.put("/{job_id}", response_model=ScheduledJobOut)
async def update_job(job_id: UUID, payload: ScheduledJobIn, session: AsyncSession = Depends(get_session)) -> ScheduledJobOut:
    obj = await session.get(ScheduledJob, job_id)
    if not obj:
        raise HTTPException(404, "job not found")
    for k, v in payload.model_dump().items():
        setattr(obj, k, v)
    await session.commit()
    await session.refresh(obj)
    await reload_jobs()
    return ScheduledJobOut.model_validate(obj)


@router.delete("/{job_id}", status_code=204)
async def delete_job(job_id: UUID, session: AsyncSession = Depends(get_session)) -> None:
    obj = await session.get(ScheduledJob, job_id)
    if obj:
        await session.delete(obj)
        await session.commit()
        await reload_jobs()
