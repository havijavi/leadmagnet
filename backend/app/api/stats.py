from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_admin
from app.config import settings
from app.db import get_session
from app.models import DiscoveryRun, Lead
from app.schemas import StatsOut

router = APIRouter(dependencies=[Depends(require_admin)])


@router.get("", response_model=StatsOut)
async def stats(session: AsyncSession = Depends(get_session)) -> StatsOut:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    return StatsOut(
        leads_total=int(await session.scalar(select(func.count(Lead.id))) or 0),
        leads_new=int(await session.scalar(select(func.count(Lead.id)).where(Lead.status == "new")) or 0),
        leads_contacted=int(await session.scalar(select(func.count(Lead.id)).where(Lead.status == "contacted")) or 0),
        leads_replied=int(await session.scalar(select(func.count(Lead.id)).where(Lead.status == "replied")) or 0),
        high_fit_count=int(
            await session.scalar(
                select(func.count(Lead.id)).where(Lead.fit_score >= settings.NOTIFY_FIT_THRESHOLD)
            ) or 0
        ),
        discovery_runs_24h=int(
            await session.scalar(
                select(func.count(DiscoveryRun.id)).where(DiscoveryRun.created_at >= cutoff)
            ) or 0
        ),
        leads_enriched=int(
            await session.scalar(
                select(func.count(Lead.id)).where(Lead.enrichment_status == "enriched")
            ) or 0
        ),
        leads_pending_enrichment=int(
            await session.scalar(
                select(func.count(Lead.id)).where(Lead.enrichment_status == "pending")
            ) or 0
        ),
    )
