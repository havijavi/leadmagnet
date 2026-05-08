"""Bulk enrichment worker — runs the waterfall for a batch of leads."""
from __future__ import annotations

import asyncio
import logging
from typing import Iterable, Optional
from uuid import UUID

from sqlalchemy import select

from app.db import session_scope
from app.models import Lead
from app.services.enrichment.types import Subject
from app.services.enrichment.waterfall import run_waterfall

logger = logging.getLogger(__name__)


async def enrich_lead(lead_id: UUID, providers: Optional[list[str]] = None) -> dict:
    async with session_scope() as session:
        lead = await session.get(Lead, lead_id)
        if not lead:
            return {"ok": False, "reason": "lead not found"}
        subject = _subject_from_lead(lead)
    return await run_waterfall(subject, only_providers=providers, lead_id=lead_id)


async def enrich_pending(limit: int = 25, providers: Optional[list[str]] = None) -> dict:
    async with session_scope() as session:
        rows = await session.scalars(
            select(Lead)
            .where(Lead.enrichment_status == "pending")
            .order_by(Lead.fit_score.desc(), Lead.created_at.desc())
            .limit(limit)
        )
        ids = [r.id for r in rows]
    return await enrich_batch(ids, providers=providers)


async def enrich_batch(lead_ids: Iterable[UUID], providers: Optional[list[str]] = None, *, concurrency: int = 4) -> dict:
    sem = asyncio.Semaphore(concurrency)

    async def _one(lid: UUID) -> dict:
        async with sem:
            try:
                return await enrich_lead(lid, providers=providers)
            except Exception as e:
                logger.exception("enrich_lead %s failed", lid)
                return {"ok": False, "reason": str(e)}

    results = await asyncio.gather(*[_one(lid) for lid in lead_ids])
    enriched = sum(1 for r in results if r.get("status") == "completed")
    partial = sum(1 for r in results if r.get("status") == "partial")
    failed = sum(1 for r in results if r.get("status") == "failed" or r.get("ok") is False)
    return {"ok": True, "total": len(results), "enriched": enriched, "partial": partial, "failed": failed}


def _subject_from_lead(lead: Lead) -> Subject:
    return Subject(
        name=lead.name,
        company=lead.company,
        email=lead.email,
        domain=lead.domain or _domain_from(lead.website or lead.email),
        website=lead.website,
        linkedin_url=lead.linkedin_url,
        role=lead.role,
        location=lead.location,
    )


def _domain_from(s: Optional[str]) -> Optional[str]:
    if not s:
        return None
    if "@" in s:
        return s.split("@", 1)[1].lower()
    out = s.lower().replace("https://", "").replace("http://", "").split("/")[0]
    return out[4:] if out.startswith("www.") else out or None
