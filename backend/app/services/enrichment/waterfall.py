"""Waterfall orchestrator.

Runs providers in priority order, merging their results into the running
Subject. Stops early when the lead is "complete enough" to save the user
budget on the slower/paid providers.

Audit trail (which provider returned what, which fields it filled, errors)
is persisted as an EnrichmentRun row.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Iterable, Optional
from uuid import UUID

from sqlalchemy import select

from app.db import session_scope
from app.models import EnrichmentRun, Lead
from app.services.crm_push import fire_event
from app.services.enrichment import PROVIDERS
from app.services.enrichment.types import EnrichmentHit, Provider, Subject

logger = logging.getLogger(__name__)


async def run_waterfall(
    subject: Subject,
    *,
    only_providers: Optional[Iterable[str]] = None,
    lead_id: Optional[UUID] = None,
) -> dict:
    """Run the waterfall and return {subject, hits, status}.

    If lead_id is provided, the lead row is updated in place and an
    EnrichmentRun audit row is written.
    """
    selected = _select_providers(only_providers)
    hits: list[EnrichmentHit] = []
    providers_tried: list[str] = []
    providers_hit: list[str] = []
    fields_filled: set[str] = set()

    for p in selected:
        if not p.is_configured():
            continue
        providers_tried.append(p.name)

        # The website provider produces an excerpt the LLM-research provider
        # consumes — pass it via a private attribute.
        if hasattr(subject, "_research_excerpt"):
            pass  # already set
        try:
            hit = await p.enrich(subject)
        except Exception as e:
            logger.exception("provider %s blew up", p.name)
            hit = EnrichmentHit(provider=p.name, error=str(e))
        hits.append(hit)

        if hit.error or not hit.fields:
            continue
        providers_hit.append(p.name)

        # Stash research excerpt on the subject so llm_research sees it.
        if "research_excerpt" in hit.fields:
            object.__setattr__(subject, "_research_excerpt", hit.fields.pop("research_excerpt"))

        before = subject.__dict__.copy()
        subject = subject.merge(hit.fields)
        for k, v in subject.__dict__.items():
            if v and not before.get(k):
                fields_filled.add(k)

        if subject.is_complete():
            # We have email + name/company. The remaining providers are usually
            # the LLM research one — keep going only if it hasn't run yet.
            if any(p.name == "llm_research" for p in selected if p.name not in providers_tried):
                continue
            # else: short-circuit
            # (we still always run llm_research when present, since it adds research_*)
            pass

    status = (
        "completed" if providers_hit else
        "partial" if any(h.fields for h in hits) else
        "failed"
    )

    raw = {h.provider: {"fields": h.fields, "confidence": h.confidence, "error": h.error} for h in hits}

    if lead_id is not None:
        await _persist(lead_id, subject, hits, providers_tried, providers_hit, fields_filled, status, raw)

    return {
        "subject": subject.__dict__,
        "providers_tried": providers_tried,
        "providers_hit": providers_hit,
        "fields_filled": sorted(fields_filled),
        "status": status,
        "raw": raw,
    }


def _select_providers(only: Optional[Iterable[str]]) -> list[Provider]:
    if not only:
        return list(PROVIDERS)
    keep = set(only)
    return [p for p in PROVIDERS if p.name in keep]


async def _persist(
    lead_id: UUID,
    subject: Subject,
    hits: list[EnrichmentHit],
    providers_tried: list[str],
    providers_hit: list[str],
    fields_filled: set[str],
    status: str,
    raw: dict,
) -> None:
    async with session_scope() as session:
        lead = await session.get(Lead, lead_id)
        if not lead:
            return

        # Persist scalar fields the waterfall has discovered.
        merged = subject.__dict__
        for col in ("name", "company", "email", "website", "domain", "linkedin_url", "role", "location"):
            v = merged.get(col)
            if v and not getattr(lead, col, None):
                setattr(lead, col, v)

        # Research output goes onto its own columns.
        research_hit = next((h for h in hits if h.provider == "llm_research" and h.fields), None)
        if research_hit:
            lead.research_summary = research_hit.fields.get("research_summary") or lead.research_summary
            lead.research_data = research_hit.fields.get("research_data") or lead.research_data or {}
            lead.researched_at = datetime.now(timezone.utc)
            new_score = research_hit.fields.get("fit_score")
            if isinstance(new_score, int) and new_score > (lead.fit_score or 0):
                lead.fit_score = new_score

        lead.enrichment_data = {**(lead.enrichment_data or {}), **{p: r for p, r in raw.items()}}
        lead.enrichment_status = status if status != "failed" else "failed"
        if status != "failed":
            lead.enriched_at = datetime.now(timezone.utc)

        run = EnrichmentRun(
            lead_id=lead_id,
            providers_tried=providers_tried,
            providers_hit=providers_hit,
            fields_filled=sorted(fields_filled),
            status=status,
            error_message=None if providers_hit else _aggregate_errors(hits),
            raw_results=raw,
        )
        session.add(run)

    # Fire CRM webhook for the enrichment event (after commit).
    try:
        await fire_event("lead.enriched", lead_id)
    except Exception as e:
        logger.warning("CRM push for lead.enriched failed: %s", e)


def _aggregate_errors(hits: list[EnrichmentHit]) -> Optional[str]:
    errs = [f"{h.provider}: {h.error}" for h in hits if h.error]
    return "; ".join(errs) if errs else None
