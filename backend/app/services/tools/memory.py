"""Project-memory tool — append a fact to chat_projects.memory."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from app.db import session_scope
from app.models import ChatProject


async def remember(*, project_id: UUID, note: str) -> dict[str, Any]:
    note = (note or "").strip()
    if not note:
        return {"ok": False, "error": "note is empty"}
    if len(note) > 1000:
        return {"ok": False, "error": "note must be under 1000 chars; condense first"}

    async with session_scope() as session:
        project = await session.get(ChatProject, project_id)
        if not project:
            return {"ok": False, "error": "project not found"}
        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        existing = (project.memory or "").strip()
        entry = f"- ({stamp}) {note}"
        project.memory = f"{existing}\n{entry}".strip() if existing else entry
    return {"ok": True, "stored": entry}
