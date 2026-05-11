from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import CurrentUser, require_member
from app.db import get_session
from app.models import ChatMessage, ChatProject
from app.schemas import (
    ChatMessageOut,
    ChatProjectIn,
    ChatProjectOut,
    ChatProjectUpdate,
    ChatSendRequest,
    ChatSendResponse,
)
from app.services.chat_orchestrator import run_chat_turn

router = APIRouter(dependencies=[Depends(require_member)])


def _to_out(p: ChatProject, message_count: int = 0, last_message_at=None) -> ChatProjectOut:
    return ChatProjectOut(
        id=p.id,
        name=p.name,
        description=p.description,
        system_prompt=p.system_prompt,
        memory=p.memory,
        is_pinned=p.is_pinned,
        message_count=message_count,
        last_message_at=last_message_at,
        created_at=p.created_at,
        updated_at=p.updated_at,
    )


# ---- projects ----------------------------------------------------------

@router.get("/projects", response_model=list[ChatProjectOut])
async def list_projects(session: AsyncSession = Depends(get_session)) -> list[ChatProjectOut]:
    rows = await session.scalars(
        select(ChatProject).order_by(ChatProject.is_pinned.desc(), ChatProject.updated_at.desc())
    )
    projects = list(rows)
    # Cheap per-project counts in one query.
    if projects:
        counts = await session.execute(
            select(
                ChatMessage.project_id,
                func.count(ChatMessage.id),
                func.max(ChatMessage.created_at),
            )
            .where(ChatMessage.project_id.in_([p.id for p in projects]))
            .group_by(ChatMessage.project_id)
        )
        by_id = {row[0]: (row[1], row[2]) for row in counts.all()}
    else:
        by_id = {}
    return [_to_out(p, *(by_id.get(p.id, (0, None)))) for p in projects]


@router.post("/projects", response_model=ChatProjectOut, status_code=201)
async def create_project(
    payload: ChatProjectIn,
    current: CurrentUser = Depends(require_member),
    session: AsyncSession = Depends(get_session),
) -> ChatProjectOut:
    name = payload.name.strip()
    if not name:
        raise HTTPException(400, "name is required")
    project = ChatProject(
        name=name,
        description=payload.description,
        system_prompt=payload.system_prompt,
        memory=payload.memory,
        is_pinned=payload.is_pinned,
        created_by=None if current.is_superuser else UUID(current.id),
    )
    session.add(project)
    await session.commit()
    await session.refresh(project)
    return _to_out(project)


@router.get("/projects/{project_id}", response_model=ChatProjectOut)
async def get_project(project_id: UUID, session: AsyncSession = Depends(get_session)) -> ChatProjectOut:
    project = await session.get(ChatProject, project_id)
    if not project:
        raise HTTPException(404, "project not found")
    count = await session.scalar(
        select(func.count(ChatMessage.id)).where(ChatMessage.project_id == project_id)
    ) or 0
    last_at = await session.scalar(
        select(func.max(ChatMessage.created_at)).where(ChatMessage.project_id == project_id)
    )
    return _to_out(project, count, last_at)


@router.patch("/projects/{project_id}", response_model=ChatProjectOut)
async def update_project(
    project_id: UUID,
    payload: ChatProjectUpdate,
    session: AsyncSession = Depends(get_session),
) -> ChatProjectOut:
    project = await session.get(ChatProject, project_id)
    if not project:
        raise HTTPException(404, "project not found")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(project, k, v)
    await session.commit()
    await session.refresh(project)
    return _to_out(project)


@router.delete("/projects/{project_id}", status_code=204)
async def delete_project(project_id: UUID, session: AsyncSession = Depends(get_session)) -> None:
    project = await session.get(ChatProject, project_id)
    if project:
        await session.delete(project)
        await session.commit()


# ---- messages ----------------------------------------------------------

@router.get("/projects/{project_id}/messages", response_model=list[ChatMessageOut])
async def list_messages(
    project_id: UUID,
    session: AsyncSession = Depends(get_session),
    limit: int = 200,
) -> list[ChatMessageOut]:
    rows = await session.scalars(
        select(ChatMessage)
        .where(ChatMessage.project_id == project_id)
        .order_by(ChatMessage.created_at)
        .limit(max(1, min(limit, 1000)))
    )
    return [ChatMessageOut.model_validate(r) for r in rows]


@router.post("/projects/{project_id}/messages", response_model=ChatSendResponse)
async def send_message(
    project_id: UUID,
    payload: ChatSendRequest,
    session: AsyncSession = Depends(get_session),
) -> ChatSendResponse:
    project = await session.get(ChatProject, project_id)
    if not project:
        raise HTTPException(404, "project not found")
    content = (payload.content or "").strip()
    if not content:
        raise HTTPException(400, "message content is required")
    if len(content) > 16000:
        raise HTTPException(400, "message too long (max 16000 chars)")

    result = await run_chat_turn(
        project_id=project_id,
        user_message=content,
        max_iterations=payload.max_tool_iterations,
    )
    return ChatSendResponse(
        project_id=project_id,
        new_messages=[ChatMessageOut.model_validate(m) for m in result.get("new_messages", [])],
        iterations=result.get("iterations", 0),
        finished_reason=result.get("finished_reason", "error"),
    )


# ---- tool registry introspection (helpful for debugging in the dashboard) -

@router.get("/tools")
async def list_tools() -> dict:
    from app.services.tools import TOOLS
    return {
        "tools": [
            {
                "name": t.name,
                "description": t.description,
                "parameters_schema": t.parameters_schema,
            }
            for t in TOOLS
        ]
    }
