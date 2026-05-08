from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_admin
from app.db import get_session
from app.models import TargetList
from app.schemas import LeadCreate, TargetListOut
from app.workers.csv_import import import_csv

router = APIRouter(dependencies=[Depends(require_admin)])


@router.post("/csv")
async def upload_csv(
    file: UploadFile = File(...),
    name: str = Form(...),
    description: Optional[str] = Form(None),
) -> dict:
    if not (file.filename or "").lower().endswith(".csv"):
        raise HTTPException(400, "Only .csv files supported")
    blob = await file.read()
    if len(blob) > 5 * 1024 * 1024:
        raise HTTPException(413, "CSV must be <5MB; split larger files")
    result = await import_csv(blob, list_name=name, list_description=description)
    if not result.get("ok"):
        raise HTTPException(400, result.get("reason", "import failed"))
    return result


@router.get("/lists", response_model=list[TargetListOut])
async def list_target_lists(session: AsyncSession = Depends(get_session)) -> list[TargetListOut]:
    rows = await session.scalars(select(TargetList).order_by(TargetList.created_at.desc()))
    return [TargetListOut.model_validate(r) for r in rows]


@router.delete("/lists/{list_id}", status_code=204)
async def delete_target_list(list_id: UUID, session: AsyncSession = Depends(get_session)) -> None:
    obj = await session.get(TargetList, list_id)
    if obj:
        await session.delete(obj)
        await session.commit()


@router.post("/lead", response_model=dict, status_code=201)
async def create_lead_manual(payload: LeadCreate, session: AsyncSession = Depends(get_session)) -> dict:
    """Single-lead manual create. The fingerprint enforces dedupe."""
    from app.models import Lead
    from app.services.extractor import fingerprint_lead

    fp = fingerprint_lead(payload.model_dump())
    existing = await session.scalar(select(Lead).where(Lead.fingerprint == fp))
    if existing:
        return {"ok": False, "reason": "lead already exists", "lead_id": str(existing.id)}

    lead = Lead(
        target_list_id=payload.target_list_id,
        name=payload.name,
        company=payload.company,
        email=payload.email,
        website=payload.website,
        domain=payload.domain,
        linkedin_url=payload.linkedin_url,
        role=payload.role,
        location=payload.location,
        tags=payload.tags,
        status="new",
        enrichment_status="pending",
        fingerprint=fp,
        source_url="manual",
    )
    session.add(lead)
    await session.commit()
    await session.refresh(lead)
    return {"ok": True, "lead_id": str(lead.id)}
