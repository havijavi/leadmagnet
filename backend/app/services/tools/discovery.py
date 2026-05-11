"""Discovery tools — list configured sources and trigger discovery runs."""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import select

from app.db import session_scope
from app.models import LeadSource
from app.workers.discovery_worker import run_discovery

logger = logging.getLogger(__name__)


async def list_sources(*, project_id: UUID) -> dict[str, Any]:
    async with session_scope() as session:
        rows = await session.scalars(
            select(LeadSource).order_by(LeadSource.created_at.desc())
        )
        sources = [
            {
                "id": str(s.id),
                "name": s.name,
                "kind": s.kind,
                "config": s.config or {},
                "is_active": s.is_active,
            }
            for s in rows
        ]
    return {"ok": True, "count": len(sources), "sources": sources}


async def trigger_discovery(
    *,
    project_id: UUID,
    source_ids: Optional[list[str]] = None,
    extra_urls: Optional[list[str]] = None,
) -> dict[str, Any]:
    parsed_ids: Optional[list[UUID]] = None
    if source_ids:
        try:
            parsed_ids = [UUID(s) for s in source_ids]
        except (TypeError, ValueError) as e:
            return {"ok": False, "error": f"invalid UUID in source_ids: {e}"}

    # Kick the worker off in the background. The chat returns immediately so
    # the LLM can continue the conversation; the user can watch runs on the
    # Discovery page.
    async def _bg() -> None:
        try:
            await run_discovery(source_ids=parsed_ids, extra_urls=extra_urls or [])
        except Exception as e:
            logger.exception("background discovery failed: %s", e)

    asyncio.create_task(_bg())

    return {
        "ok": True,
        "queued": True,
        "source_ids": source_ids or [],
        "extra_urls": extra_urls or [],
        "note": (
            "Discovery is now running in the background. The user can watch progress "
            "on the Discovery page in the dashboard. New leads will appear in All leads."
        ),
    }
