"""Outbound CRM webhooks.

Fire-and-forget POSTs to user-configured URLs (HubSpot, Pipedrive, generic)
when lead-lifecycle events happen. Each webhook subscribes to a list of
events; the body is either the full lead JSON or a user-supplied template
(simple {{field}} substitution, no Jinja required).
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID

import httpx
from sqlalchemy import select

from app.db import session_scope
from app.models import CrmWebhook, Lead

logger = logging.getLogger(__name__)


async def fire_event(event: str, lead_id: UUID) -> None:
    """Fire a CRM event for a lead. Errors are logged but never raised."""
    payload = await _build_payload(event, lead_id)
    if payload is None:
        return

    async with session_scope() as session:
        webhooks = await session.scalars(
            select(CrmWebhook).where(CrmWebhook.is_active.is_(True))
        )
        targets = [w for w in webhooks if event in (w.events or [])]

    for w in targets:
        await _post(w, payload)


async def _build_payload(event: str, lead_id: UUID) -> Optional[dict]:
    async with session_scope() as session:
        lead = await session.get(Lead, lead_id)
        if not lead:
            return None
        return {
            "event": event,
            "fired_at": datetime.now(timezone.utc).isoformat(),
            "lead": {
                "id": str(lead.id),
                "name": lead.name,
                "company": lead.company,
                "email": lead.email,
                "website": lead.website,
                "domain": lead.domain,
                "linkedin_url": lead.linkedin_url,
                "role": lead.role,
                "location": lead.location,
                "project_summary": lead.project_summary,
                "fit_score": lead.fit_score,
                "urgency": lead.urgency,
                "status": lead.status,
                "tags": lead.tags or [],
                "research_summary": lead.research_summary,
                "source_url": lead.source_url,
                "created_at": lead.created_at.isoformat() if lead.created_at else None,
            },
        }


async def _post(webhook: CrmWebhook, payload: dict) -> None:
    body = (
        _render_template(webhook.body_template, payload)
        if webhook.body_template
        else json.dumps(payload)
    )
    headers = {"Content-Type": "application/json", **(webhook.headers or {})}
    if webhook.secret:
        sig = hmac.new(webhook.secret.encode(), body.encode(), hashlib.sha256).hexdigest()
        headers["X-LeadMagnet-Signature"] = f"sha256={sig}"

    err: Optional[str] = None
    code: Optional[int] = None
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            r = await client.post(webhook.url, content=body, headers=headers)
            code = r.status_code
            if r.status_code >= 400:
                err = f"HTTP {r.status_code}: {r.text[:200]}"
    except Exception as e:
        err = str(e)

    async with session_scope() as session:
        obj = await session.get(CrmWebhook, webhook.id)
        if obj:
            obj.last_fired_at = datetime.now(timezone.utc)
            obj.last_status_code = code
            obj.last_error = err

    if err:
        logger.warning("CRM webhook %s failed: %s", webhook.name, err)


def _render_template(tpl: str, payload: dict) -> str:
    """Tiny {{lead.field}} substitution. Keeps you out of Jinja-injection territory."""
    out = tpl
    flat = _flatten(payload)
    for key, val in flat.items():
        out = out.replace("{{" + key + "}}", _to_str(val))
    return out


def _flatten(d: dict, prefix: str = "") -> dict[str, Any]:
    flat: dict[str, Any] = {}
    for k, v in d.items():
        path = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            flat.update(_flatten(v, path))
        else:
            flat[path] = v
    return flat


def _to_str(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, (list, dict)):
        return json.dumps(v)
    return str(v)
