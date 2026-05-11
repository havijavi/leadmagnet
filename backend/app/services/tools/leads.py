"""Lead-management tools for the chat agent."""
from __future__ import annotations

import logging
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import or_, select

from app.db import session_scope
from app.models import Lead, ServiceOffering
from app.services.extractor import fingerprint_lead

logger = logging.getLogger(__name__)


async def save_lead(
    *,
    project_id: UUID,
    name: Optional[str] = None,
    company: Optional[str] = None,
    email: Optional[str] = None,
    website: Optional[str] = None,
    domain: Optional[str] = None,
    linkedin_url: Optional[str] = None,
    role: Optional[str] = None,
    location: Optional[str] = None,
    project_summary: Optional[str] = None,
    fit_score: Optional[int] = None,
    urgency: Optional[str] = None,
    source_url: Optional[str] = None,
    tags: Optional[list[str]] = None,
) -> dict[str, Any]:
    if not (name or company or email or website or linkedin_url):
        return {"ok": False, "error": "need at least one of: name, company, email, website, linkedin_url"}

    raw = {
        "name": name,
        "company": company,
        "email": email,
        "website": website,
        "domain": domain,
        "linkedin_url": linkedin_url,
        "role": role,
        "location": location,
        "source_url": source_url or f"chat://project/{project_id}",
    }
    fp = fingerprint_lead(raw)

    async with session_scope() as session:
        existing = await session.scalar(select(Lead).where(Lead.fingerprint == fp))
        if existing:
            return {
                "ok": False,
                "duplicate": True,
                "existing_lead_id": str(existing.id),
                "error": "a matching lead already exists (deduped by email/website/name+source)",
            }

        lead = Lead(
            name=name,
            company=company,
            email=email,
            website=website,
            domain=domain or _domain_of(website or email),
            linkedin_url=linkedin_url,
            role=role,
            location=location,
            project_summary=project_summary,
            fit_score=int(fit_score) if fit_score is not None else 0,
            urgency=urgency or "medium",
            source_url=source_url or f"chat://project/{project_id}",
            tags=tags or [],
            status="new",
            enrichment_status="pending",
            fingerprint=fp,
            raw_data={"created_via": "chat_tool", "chat_project_id": str(project_id)},
        )
        session.add(lead)
        await session.flush()
        lead_id = str(lead.id)

    return {"ok": True, "lead_id": lead_id, "fingerprint": fp[:12]}


async def search_leads(
    *,
    project_id: UUID,
    query: Optional[str] = None,
    status: Optional[str] = None,
    min_fit_score: Optional[int] = None,
    limit: int = 20,
) -> dict[str, Any]:
    limit = max(1, min(int(limit or 20), 100))
    async with session_scope() as session:
        stmt = select(Lead).order_by(Lead.fit_score.desc(), Lead.created_at.desc()).limit(limit)
        if query:
            like = f"%{query.lower()}%"
            stmt = stmt.where(
                or_(
                    Lead.name.ilike(like),
                    Lead.company.ilike(like),
                    Lead.email.ilike(like),
                    Lead.website.ilike(like),
                    Lead.domain.ilike(like),
                )
            )
        if status:
            stmt = stmt.where(Lead.status == status)
        if min_fit_score is not None:
            stmt = stmt.where(Lead.fit_score >= int(min_fit_score))
        rows = await session.scalars(stmt)
        leads = [
            {
                "id": str(l.id),
                "name": l.name,
                "company": l.company,
                "email": l.email,
                "website": l.website,
                "fit_score": l.fit_score,
                "status": l.status,
                "project_summary": l.project_summary,
                "source_url": l.source_url,
            }
            for l in rows
        ]
    return {"ok": True, "count": len(leads), "leads": leads}


async def list_services(*, project_id: UUID) -> dict[str, Any]:
    async with session_scope() as session:
        rows = await session.scalars(
            select(ServiceOffering).where(ServiceOffering.is_active.is_(True))
        )
        services = [
            {
                "id": str(s.id),
                "name": s.name,
                "description": s.description,
                "keywords": s.keywords or [],
                "target_industries": s.target_industries or [],
            }
            for s in rows
        ]
    return {"ok": True, "count": len(services), "services": services}


def _domain_of(s: Optional[str]) -> Optional[str]:
    if not s:
        return None
    if "@" in s:
        return s.split("@", 1)[1].lower()
    out = s.lower().replace("https://", "").replace("http://", "").split("/")[0]
    return out[4:] if out.startswith("www.") else out or None
