from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_member
from app.db import get_session
from app.models import DiscoveryRun, ServiceOffering
from app.schemas import DiscoveryRunOut, DiscoveryTrigger
from app.services.extractor import generate_queries
from app.workers.discovery_worker import run_discovery

router = APIRouter(dependencies=[Depends(require_member)])


@router.post("/run", status_code=202)
async def trigger(payload: DiscoveryTrigger, bg: BackgroundTasks) -> dict:
    bg.add_task(
        run_discovery,
        source_ids=payload.source_ids,
        service_id=payload.service_id,
        extra_urls=payload.extra_urls,
    )
    return {"queued": True}


@router.post("/suggest-queries")
async def suggest_queries(session: AsyncSession = Depends(get_session)) -> dict:
    services = await session.scalars(
        select(ServiceOffering).where(ServiceOffering.is_active.is_(True))
    )
    service_names = [s.name for s in services]
    queries = await generate_queries(service_names, n=8)
    return {"services": service_names, "queries": queries}


@router.get("/runs", response_model=list[DiscoveryRunOut])
async def list_runs(
    session: AsyncSession = Depends(get_session),
    limit: int = 50,
) -> list[DiscoveryRunOut]:
    rows = await session.scalars(
        select(DiscoveryRun).order_by(DiscoveryRun.created_at.desc()).limit(limit)
    )
    return [DiscoveryRunOut.model_validate(r) for r in rows]
