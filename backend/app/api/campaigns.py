from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_admin
from app.db import get_session
from app.models import Lead, OutreachMessage, ServiceOffering
from app.schemas import (
    OutreachDraftIn,
    OutreachMessageOut,
    OutreachUpdate,
)
from app.services.emailer import EmailerError, emailer
from app.services.extractor import draft_outreach

router = APIRouter(dependencies=[Depends(require_admin)])


@router.get("", response_model=list[OutreachMessageOut])
async def list_messages(session: AsyncSession = Depends(get_session)) -> list[OutreachMessageOut]:
    rows = await session.scalars(
        select(OutreachMessage).order_by(OutreachMessage.created_at.desc())
    )
    return [OutreachMessageOut.model_validate(r) for r in rows]


@router.get("/by-lead/{lead_id}", response_model=list[OutreachMessageOut])
async def by_lead(lead_id: UUID, session: AsyncSession = Depends(get_session)) -> list[OutreachMessageOut]:
    rows = await session.scalars(
        select(OutreachMessage).where(OutreachMessage.lead_id == lead_id).order_by(OutreachMessage.created_at)
    )
    return [OutreachMessageOut.model_validate(r) for r in rows]


@router.post("/draft", response_model=OutreachMessageOut, status_code=201)
async def draft(payload: OutreachDraftIn, session: AsyncSession = Depends(get_session)) -> OutreachMessageOut:
    lead = await session.get(Lead, payload.lead_id)
    if not lead:
        raise HTTPException(404, "lead not found")

    services = await session.scalars(
        select(ServiceOffering).where(ServiceOffering.is_active.is_(True))
    )
    service_names = [s.name for s in services]

    lead_dict = {
        "name": lead.name,
        "company": lead.company,
        "role": lead.role,
        "project_summary": lead.project_summary,
        "raw_excerpt": lead.raw_excerpt,
        "source_url": lead.source_url,
    }
    subject, body = await draft_outreach(
        lead_dict,
        services=service_names,
        tone=payload.tone,
        extra_context=payload.extra_context,
    )
    msg = OutreachMessage(
        lead_id=lead.id,
        direction="outbound",
        channel="email",
        subject=subject,
        body=body,
        status="draft",
    )
    session.add(msg)
    await session.commit()
    await session.refresh(msg)
    return OutreachMessageOut.model_validate(msg)


@router.patch("/{message_id}", response_model=OutreachMessageOut)
async def update_message(
    message_id: UUID,
    payload: OutreachUpdate,
    session: AsyncSession = Depends(get_session),
) -> OutreachMessageOut:
    obj = await session.get(OutreachMessage, message_id)
    if not obj:
        raise HTTPException(404, "message not found")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(obj, k, v)
    await session.commit()
    await session.refresh(obj)
    return OutreachMessageOut.model_validate(obj)


@router.post("/{message_id}/send", response_model=OutreachMessageOut)
async def send(message_id: UUID, session: AsyncSession = Depends(get_session)) -> OutreachMessageOut:
    msg = await session.get(OutreachMessage, message_id)
    if not msg:
        raise HTTPException(404, "message not found")
    if msg.status == "sent":
        raise HTTPException(400, "already sent")

    lead = await session.get(Lead, msg.lead_id)
    if not lead:
        raise HTTPException(400, "lead vanished")
    if not lead.email:
        raise HTTPException(400, "lead has no email — fill it in before sending")

    try:
        await emailer.send(to=lead.email, subject=msg.subject or "Hi", body=msg.body)
    except EmailerError as e:
        msg.status = "failed"
        msg.error_message = str(e)
        await session.commit()
        await session.refresh(msg)
        raise HTTPException(500, str(e))

    msg.status = "sent"
    msg.sent_at = datetime.now(timezone.utc)
    msg.error_message = None
    lead.status = "contacted"
    await session.commit()
    await session.refresh(msg)
    return OutreachMessageOut.model_validate(msg)
