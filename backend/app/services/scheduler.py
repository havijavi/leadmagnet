"""APScheduler integration.

Loads every active row in scheduled_jobs at startup, registers it with the
in-process AsyncIOScheduler, and re-syncs when rows change. This is the
n8n-replacement for cron-style automation.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select, update

from app.config import settings
from app.db import session_scope
from app.models import ScheduledJob

logger = logging.getLogger(__name__)


_scheduler: Optional[AsyncIOScheduler] = None


def get_scheduler() -> AsyncIOScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = AsyncIOScheduler(timezone="UTC")
    return _scheduler


async def start() -> None:
    if not settings.SCHEDULER_ENABLED:
        logger.info("Scheduler disabled by SCHEDULER_ENABLED=false")
        return
    sched = get_scheduler()
    if sched.running:
        return
    await reload_jobs()
    sched.start()
    logger.info("APScheduler started with %d job(s)", len(sched.get_jobs()))


async def stop() -> None:
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)


async def reload_jobs() -> None:
    """Drop all jobs and re-register from DB. Cheap — call after CRUD."""
    sched = get_scheduler()
    for j in sched.get_jobs():
        j.remove()
    async with session_scope() as session:
        rows = await session.scalars(select(ScheduledJob).where(ScheduledJob.is_active.is_(True)))
        rows = list(rows)
    for row in rows:
        try:
            sched.add_job(
                _run_job,
                CronTrigger.from_crontab(row.cron, timezone="UTC"),
                kwargs={"job_id": row.id, "kind": row.kind, "payload": row.payload or {}},
                id=str(row.id),
                replace_existing=True,
                misfire_grace_time=3600,
                coalesce=True,
            )
        except Exception as e:
            logger.warning("Bad cron %r for job %s: %s", row.cron, row.name, e)


async def _run_job(job_id: UUID, kind: str, payload: dict[str, Any]) -> None:
    started = datetime.now(timezone.utc)
    err: Optional[str] = None
    try:
        if kind == "discovery":
            from app.workers.discovery_worker import run_discovery
            await run_discovery(
                source_ids=payload.get("source_ids"),
                service_id=payload.get("service_id"),
                extra_urls=payload.get("extra_urls") or [],
            )
        elif kind == "enrichment_pending":
            from app.workers.enrichment_worker import enrich_pending
            await enrich_pending(limit=int(payload.get("limit", 25)))
        elif kind == "crm_sync":
            # Re-fire 'lead.created' for any lead that's been created but never CRM-synced.
            # Implemented as a no-op stub for now — users can add custom logic here.
            logger.info("crm_sync job %s noop", job_id)
        else:
            err = f"unknown kind: {kind}"
    except Exception as e:
        logger.exception("Scheduled job %s failed", job_id)
        err = str(e)

    async with session_scope() as session:
        await session.execute(
            update(ScheduledJob)
            .where(ScheduledJob.id == job_id)
            .values(
                last_run_at=started,
                last_status="failed" if err else "ok",
                last_error=err,
            )
        )
