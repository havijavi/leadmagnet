from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_admin
from app.db import get_session
from app.models import CrmWebhook
from app.schemas import CrmWebhookIn, CrmWebhookOut
from app.services.crm_push import fire_event

router = APIRouter(dependencies=[Depends(require_admin)])


@router.get("", response_model=list[CrmWebhookOut])
async def list_webhooks(session: AsyncSession = Depends(get_session)) -> list[CrmWebhookOut]:
    rows = await session.scalars(select(CrmWebhook).order_by(CrmWebhook.created_at.desc()))
    return [CrmWebhookOut.model_validate(r) for r in rows]


@router.post("", response_model=CrmWebhookOut, status_code=201)
async def create_webhook(payload: CrmWebhookIn, session: AsyncSession = Depends(get_session)) -> CrmWebhookOut:
    obj = CrmWebhook(**payload.model_dump())
    session.add(obj)
    await session.commit()
    await session.refresh(obj)
    return CrmWebhookOut.model_validate(obj)


@router.put("/{webhook_id}", response_model=CrmWebhookOut)
async def update_webhook(webhook_id: UUID, payload: CrmWebhookIn, session: AsyncSession = Depends(get_session)) -> CrmWebhookOut:
    obj = await session.get(CrmWebhook, webhook_id)
    if not obj:
        raise HTTPException(404, "webhook not found")
    for k, v in payload.model_dump().items():
        setattr(obj, k, v)
    await session.commit()
    await session.refresh(obj)
    return CrmWebhookOut.model_validate(obj)


@router.delete("/{webhook_id}", status_code=204)
async def delete_webhook(webhook_id: UUID, session: AsyncSession = Depends(get_session)) -> None:
    obj = await session.get(CrmWebhook, webhook_id)
    if obj:
        await session.delete(obj)
        await session.commit()


@router.post("/{webhook_id}/test")
async def test_webhook(webhook_id: UUID, session: AsyncSession = Depends(get_session)) -> dict:
    """Fire a test 'lead.created' event for the most recent lead, if any."""
    from app.models import Lead

    obj = await session.get(CrmWebhook, webhook_id)
    if not obj:
        raise HTTPException(404, "webhook not found")
    lead = await session.scalar(select(Lead).order_by(Lead.created_at.desc()).limit(1))
    if not lead:
        raise HTTPException(400, "no leads to test with — create at least one lead first")
    await fire_event("lead.created", lead.id)
    return {"ok": True, "fired_for_lead": str(lead.id)}
