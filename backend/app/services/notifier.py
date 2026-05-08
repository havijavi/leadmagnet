"""Multi-channel new-lead notifier.

Each lead that scores at or above NOTIFY_FIT_THRESHOLD pings every configured
channel. Channels not configured are skipped silently — there is no fan-out
penalty for leaving Telegram or webhook blank.
"""
from __future__ import annotations

import logging
from typing import Any

import httpx

from app.config import settings
from app.services.emailer import emailer

logger = logging.getLogger(__name__)


async def notify_new_lead(lead: dict[str, Any]) -> None:
    text = _format_lead(lead)
    await _telegram(text)
    await _webhook({"event": "new_lead", "lead": lead, "text": text})
    await _email_digest(text, lead)


async def _telegram(text: str) -> None:
    if not (settings.TELEGRAM_BOT_TOKEN and settings.TELEGRAM_CHAT_ID):
        return
    url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            await client.post(
                url,
                json={
                    "chat_id": settings.TELEGRAM_CHAT_ID,
                    "text": text,
                    "parse_mode": "Markdown",
                    "disable_web_page_preview": False,
                },
            )
    except Exception as e:
        logger.warning("Telegram notify failed: %s", e)


async def _webhook(payload: dict[str, Any]) -> None:
    if not settings.NOTIFY_WEBHOOK_URL:
        return
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            await client.post(settings.NOTIFY_WEBHOOK_URL, json=payload)
    except Exception as e:
        logger.warning("Webhook notify failed: %s", e)


async def _email_digest(text: str, lead: dict[str, Any]) -> None:
    if not (settings.NOTIFY_EMAIL and emailer.configured):
        return
    subject = f"[LeadMagnet] New lead — {lead.get('name') or lead.get('company') or 'unknown'}"
    try:
        await emailer.send(to=settings.NOTIFY_EMAIL, subject=subject, body=text)
    except Exception as e:
        logger.warning("Email notify failed: %s", e)


def _format_lead(lead: dict[str, Any]) -> str:
    name = lead.get("name") or lead.get("company") or "Unknown"
    score = lead.get("fit_score", 0)
    urgency = lead.get("urgency", "?")
    summary = lead.get("project_summary") or ""
    url = lead.get("source_url") or ""
    email = lead.get("email") or "—"
    site = lead.get("website") or "—"
    return (
        f"*New lead* — *{name}* (fit {score}, urgency {urgency})\n\n"
        f"{summary}\n\n"
        f"Email: {email}\nWebsite: {site}\nSource: {url}"
    )
