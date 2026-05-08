"""End-to-end discovery worker: fetch a source -> extract leads -> qualify -> save -> notify."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Iterable, Optional
from uuid import UUID

from sqlalchemy import select

from app.config import settings
from app.db import session_scope
from app.models import DiscoveryRun, Lead, LeadSource, ServiceOffering
from app.services.crm_push import fire_event
from app.services.extractor import extract_leads, fingerprint_lead, qualify_lead
from app.services.notifier import notify_new_lead
from app.sources import REGISTRY

logger = logging.getLogger(__name__)


async def run_discovery(
    *,
    source_ids: Optional[list[UUID]] = None,
    service_id: Optional[UUID] = None,
    extra_urls: Optional[list[str]] = None,
) -> dict:
    """Discovery entry point. Safe to call from BackgroundTasks."""
    services = await _load_services(service_id)
    if not services:
        return {"ok": False, "reason": "no active services configured"}

    sources = await _load_sources(source_ids)
    extra_urls = extra_urls or []
    if not sources and not extra_urls:
        return {"ok": False, "reason": "no sources to run"}

    summary = {"runs": [], "leads_added": 0}

    for src in sources:
        run_id = await _start_run(src.id)
        leads_added = 0
        pages = 0
        error = None
        try:
            fetcher = REGISTRY.get(src.kind)
            if not fetcher:
                raise RuntimeError(f"unknown source kind {src.kind}")
            pages_data = await fetcher(src.config or {})
            pages = len(pages_data)
            for url, content in pages_data:
                leads_added += await _process_page(url, content, services, src_id=src.id, run_id=run_id)
        except Exception as e:
            logger.exception("Discovery run failed for source %s", src.id)
            error = str(e)
        await _finish_run(run_id, pages=pages, leads=leads_added, error=error)
        summary["runs"].append({
            "source_id": str(src.id),
            "source_name": src.name,
            "pages": pages,
            "leads_added": leads_added,
            "error": error,
        })
        summary["leads_added"] += leads_added

    if extra_urls:
        run_id = await _start_run(None)
        leads_added = 0
        try:
            from app.sources.generic_url import fetch as fetch_url
            pages_data = await fetch_url({"urls": extra_urls})
            for url, content in pages_data:
                leads_added += await _process_page(url, content, services, src_id=None, run_id=run_id)
        except Exception as e:
            logger.exception("Extra-URL discovery failed")
            await _finish_run(run_id, pages=len(extra_urls), leads=leads_added, error=str(e))
        else:
            await _finish_run(run_id, pages=len(extra_urls), leads=leads_added, error=None)
        summary["runs"].append({
            "source_id": None,
            "source_name": "ad-hoc URLs",
            "pages": len(extra_urls),
            "leads_added": leads_added,
            "error": None,
        })
        summary["leads_added"] += leads_added

    return {"ok": True, **summary}


async def _process_page(url: str, content: str, services: list[ServiceOffering], *, src_id: Optional[UUID], run_id: UUID) -> int:
    service_names = [s.name for s in services]
    raw_leads = await extract_leads(content, url=url, services=service_names)
    if not raw_leads:
        return 0

    added = 0
    new_lead_ids: list[UUID] = []
    async with session_scope() as session:
        for raw in raw_leads:
            raw["source_url"] = url
            qual = await qualify_lead(raw, service_names)
            fp = fingerprint_lead(raw)

            existing = await session.scalar(select(Lead).where(Lead.fingerprint == fp))
            if existing:
                continue

            best_service = _match_service(raw, services)
            lead = Lead(
                source_id=src_id,
                discovery_run_id=run_id,
                matched_service_id=best_service.id if best_service else None,
                name=raw.get("name"),
                company=raw.get("company"),
                email=raw.get("email"),
                website=raw.get("website"),
                domain=_domain_of(raw.get("website") or raw.get("email")),
                location=raw.get("location"),
                role=raw.get("role"),
                project_summary=raw.get("project_summary"),
                raw_excerpt=content[:2000],
                source_url=url,
                fit_score=qual["fit_score"],
                urgency=qual["urgency"],
                qualification_notes=qual.get("qualification_notes"),
                fingerprint=fp,
                raw_data=raw,
            )
            session.add(lead)
            await session.flush()
            new_lead_ids.append(lead.id)
            added += 1

            if lead.fit_score >= settings.NOTIFY_FIT_THRESHOLD:
                try:
                    await notify_new_lead({
                        "name": lead.name,
                        "company": lead.company,
                        "email": lead.email,
                        "website": lead.website,
                        "fit_score": lead.fit_score,
                        "urgency": lead.urgency,
                        "project_summary": lead.project_summary,
                        "source_url": lead.source_url,
                    })
                except Exception as e:
                    logger.warning("Notifier failed: %s", e)

    # Fire CRM webhooks AFTER the transaction has committed.
    for lid in new_lead_ids:
        try:
            await fire_event("lead.created", lid)
        except Exception as e:
            logger.warning("CRM push for lead.created failed: %s", e)

    return added


def _domain_of(s: Optional[str]) -> Optional[str]:
    if not s:
        return None
    if "@" in s:
        return s.split("@", 1)[1].lower()
    out = s.lower().replace("https://", "").replace("http://", "").split("/")[0]
    return out[4:] if out.startswith("www.") else out or None


def _match_service(raw: dict, services: list[ServiceOffering]) -> Optional[ServiceOffering]:
    text = " ".join(
        str(v) for v in (raw.get("project_summary"), raw.get("match_reason"), raw.get("role")) if v
    ).lower()
    best, best_hits = None, 0
    for svc in services:
        hits = sum(1 for kw in (svc.keywords or []) if kw.lower() in text)
        if svc.name.lower() in text:
            hits += 2
        if hits > best_hits:
            best, best_hits = svc, hits
    return best


async def _load_services(service_id: Optional[UUID]) -> list[ServiceOffering]:
    async with session_scope() as session:
        stmt = select(ServiceOffering).where(ServiceOffering.is_active.is_(True))
        if service_id:
            stmt = stmt.where(ServiceOffering.id == service_id)
        result = await session.scalars(stmt)
        return list(result)


async def _load_sources(source_ids: Optional[list[UUID]]) -> list[LeadSource]:
    async with session_scope() as session:
        stmt = select(LeadSource).where(LeadSource.is_active.is_(True))
        if source_ids:
            stmt = stmt.where(LeadSource.id.in_(source_ids))
        result = await session.scalars(stmt)
        return list(result)


async def _start_run(source_id: Optional[UUID]) -> UUID:
    async with session_scope() as session:
        run = DiscoveryRun(source_id=source_id, status="running", started_at=datetime.now(timezone.utc))
        session.add(run)
        await session.flush()
        return run.id


async def _finish_run(run_id: UUID, *, pages: int, leads: int, error: Optional[str]) -> None:
    async with session_scope() as session:
        run = await session.get(DiscoveryRun, run_id)
        if not run:
            return
        run.pages_crawled = pages
        run.leads_found = leads
        run.error_message = error
        run.status = "failed" if error else "completed"
        run.finished_at = datetime.now(timezone.utc)
        if run.source_id:
            src = await session.get(LeadSource, run.source_id)
            if src:
                src.last_run_at = run.finished_at
