from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_member
from app.db import get_session
from app.models import Lead
from app.schemas import ResearchRequest
from app.services.enrichment.types import Subject
from app.services.enrichment.waterfall import run_waterfall

router = APIRouter(dependencies=[Depends(require_member)])


@router.post("/run")
async def research(payload: ResearchRequest, session: AsyncSession = Depends(get_session)) -> dict:
    """Deep research on a single lead.

    Always runs website + llm_research providers; skips email finders to save
    Hunter/Snov credits when the user just wants AI research.
    """
    lead = await session.get(Lead, payload.lead_id)
    if not lead:
        raise HTTPException(404, "lead not found")

    subject = Subject(
        name=lead.name,
        company=lead.company,
        email=lead.email,
        website=lead.website,
        domain=lead.domain,
        linkedin_url=lead.linkedin_url,
        role=lead.role,
        location=lead.location,
    )
    providers = ["website", "llm_research"] if payload.deep else ["llm_research"]
    return await run_waterfall(subject, only_providers=providers, lead_id=payload.lead_id)
