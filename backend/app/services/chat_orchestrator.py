"""Chat orchestrator — runs the tool-call loop for one user turn.

The flow per send-message request:

  1. Load project (system prompt + memory).
  2. Append the new user message to history; persist.
  3. Build the provider-shaped history.
  4. Loop, up to MAX_ITERATIONS:
       a. Ask the LLM with the current history + tool definitions.
       b. If the model returned text only → persist assistant message, done.
       c. If the model returned tool calls → execute each, persist the
          assistant message (with tool_calls) and one tool message per call,
          then loop.
  5. Return the list of newly-created messages.

Provider shape note: OpenAI-compat and Anthropic use different formats for the
tool-call replay. We persist our canonical shape in chat_messages and re-build
the provider history fresh from DB each iteration. That way the orchestrator
doesn't care which provider the LLM is on.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import session_scope
from app.models import ChatMessage, ChatProject
from app.services.llm import ChatTurn, LLMClient, ToolCall, get_active_client
from app.services.tools import execute_tool, tools_for_llm

logger = logging.getLogger(__name__)

# How many user/assistant pairs of recent history to send to the LLM. Older
# messages are dropped; the project's `memory` field is the durable carryover.
HISTORY_TAIL = 30
MAX_ITERATIONS_HARD_CAP = 12

DEFAULT_SYSTEM_PROMPT = """\
You are LeadMagnet Chat, an agent embedded in the LeadMagnet platform. Your job
is to help the user run their lead-generation work for this project.

Tools available to you (use them to actually do work, not just talk):
  - crawl_url: fetch any public webpage as Markdown
  - save_lead / search_leads / list_services: read & write the leads database
  - list_lead_sources / trigger_discovery_run: kick off background discovery
  - remember: record a durable fact / preference / decision for THIS project

Operating rules:
  1. Be concrete. When the user asks for leads, actually call tools and find them.
     When they ask about an existing site, crawl it first; don't speculate.
  2. Don't ask permission to call a tool — just call it and report what you found.
  3. After tool calls, summarize what you did + the result for the user in plain
     language. Don't dump raw JSON unless they ask for it.
  4. If the user mentions LinkedIn at scale (more than a handful of profiles),
     warn them up front: LinkedIn actively blocks scrapers. You can try a public
     URL but should recommend Sales Navigator / Apollo / Wiza / CSV import for
     real volume.
  5. Use the `remember` tool sparingly — only for things worth recalling next
     session (target customer profile, ICP decisions, ongoing commitments). Not
     for scratch notes.
  6. If a tool fails, explain what failed and propose a next step.
"""


async def run_chat_turn(
    *,
    project_id: UUID,
    user_message: str,
    max_iterations: int = 8,
) -> dict[str, Any]:
    """Run one user turn. Returns dict with new_messages + meta."""
    max_iter = max(1, min(int(max_iterations or 8), MAX_ITERATIONS_HARD_CAP))

    # Persist the user message immediately so it shows up even if the LLM fails.
    new_message_ids: list[UUID] = []
    async with session_scope() as session:
        project = await session.get(ChatProject, project_id)
        if not project:
            return {"error": "project not found", "new_messages": [], "iterations": 0, "finished_reason": "error"}
        user_msg = ChatMessage(project_id=project_id, role="user", content=user_message)
        session.add(user_msg)
        await session.flush()
        new_message_ids.append(user_msg.id)
        # Touch updated_at so the sidebar sort reflects activity.
        project.updated_at = datetime.now(timezone.utc)
        system_prompt = _compose_system_prompt(project)

    client = await get_active_client()
    if client.is_mock:
        async with session_scope() as session:
            assistant_msg = ChatMessage(
                project_id=project_id,
                role="assistant",
                content=(
                    "No LLM is active right now — go to **Admin → LLM providers** in "
                    "the sidebar, add a provider (DeepSeek is cheapest), and click "
                    "Activate. Then come back here and the chat will work."
                ),
            )
            session.add(assistant_msg)
            await session.flush()
            new_message_ids.append(assistant_msg.id)
        return await _result(new_message_ids, iterations=0, finished_reason="no_llm")

    finished_reason = "max_iterations"
    iterations = 0

    for iterations in range(1, max_iter + 1):
        # Re-build provider history fresh from DB each iteration so the
        # assistant + tool messages we just persisted are included.
        async with session_scope() as session:
            history_msgs = await _load_recent_messages(session, project_id, limit=HISTORY_TAIL * 4)
        provider_history = _to_provider_history(history_msgs, client.provider_kind)

        try:
            turn: ChatTurn = await client.chat_with_tools(
                provider_history,
                system=system_prompt,
                tools=tools_for_llm(),
            )
        except Exception as e:
            logger.exception("LLM chat failed")
            async with session_scope() as session:
                err_msg = ChatMessage(
                    project_id=project_id,
                    role="assistant",
                    content=f"_LLM call failed:_ `{e}`. Check the LLM provider config under Admin → LLM providers.",
                    error=str(e)[:500],
                )
                session.add(err_msg)
                await session.flush()
                new_message_ids.append(err_msg.id)
            finished_reason = "error"
            break

        # Persist the assistant message (text + tool_calls, if any).
        async with session_scope() as session:
            assistant_msg = ChatMessage(
                project_id=project_id,
                role="assistant",
                content=turn.text,
                tool_calls=_serialize_tool_calls(turn.tool_calls) if turn.tool_calls else None,
            )
            session.add(assistant_msg)
            await session.flush()
            new_message_ids.append(assistant_msg.id)

        if not turn.tool_calls:
            finished_reason = "final"
            break

        # Execute each tool call and persist the result.
        for call in turn.tool_calls:
            result = await execute_tool(call.name, call.arguments, project_id=project_id)
            content = json.dumps(result, default=str)[:8000]
            async with session_scope() as session:
                tool_msg = ChatMessage(
                    project_id=project_id,
                    role="tool",
                    content=content,
                    tool_call_id=call.id,
                    tool_name=call.name,
                    error=None if result.get("ok", True) else (result.get("error") or "tool error"),
                )
                session.add(tool_msg)
                await session.flush()
                new_message_ids.append(tool_msg.id)

        # Loop back: now the LLM sees the assistant turn + the tool results and
        # can either call more tools or write a final summary.

    return await _result(new_message_ids, iterations=iterations, finished_reason=finished_reason)


# ---------------------------------------------------------------------------
# History construction
# ---------------------------------------------------------------------------

def _compose_system_prompt(project: ChatProject) -> str:
    parts = [DEFAULT_SYSTEM_PROMPT.strip()]
    parts.append(
        f"\n=== Project: {project.name} ===\n"
        f"Description: {project.description or '(none)'}\n"
    )
    if project.system_prompt:
        parts.append(f"\nExtra project instructions:\n{project.system_prompt}\n")
    if project.memory:
        parts.append(
            f"\nDurable memory for this project (from previous chats):\n{project.memory}\n"
        )
    return "\n".join(parts)


async def _load_recent_messages(
    session: AsyncSession, project_id: UUID, limit: int
) -> list[ChatMessage]:
    # Fetch the last N messages, then return in chronological order.
    rows = await session.scalars(
        select(ChatMessage)
        .where(ChatMessage.project_id == project_id)
        .order_by(ChatMessage.created_at.desc())
        .limit(limit)
    )
    msgs = list(rows)
    msgs.reverse()
    return msgs


def _to_provider_history(messages: list[ChatMessage], provider_kind: str) -> list[dict[str, Any]]:
    """Convert our DB messages into the shape the given provider's chat-completions API expects."""
    if provider_kind == "anthropic":
        return _to_anthropic_history(messages)
    return _to_openai_history(messages)


def _to_openai_history(messages: list[ChatMessage]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for m in messages:
        if m.role == "user":
            out.append({"role": "user", "content": m.content or ""})
        elif m.role == "assistant":
            entry: dict[str, Any] = {"role": "assistant", "content": m.content or ""}
            if m.tool_calls:
                entry["content"] = m.content or None
                entry["tool_calls"] = [
                    {
                        "id": tc["id"],
                        "type": "function",
                        "function": {
                            "name": tc["name"],
                            "arguments": json.dumps(tc.get("arguments") or {}),
                        },
                    }
                    for tc in m.tool_calls
                ]
            out.append(entry)
        elif m.role == "tool":
            out.append({
                "role": "tool",
                "tool_call_id": m.tool_call_id or "",
                "content": m.content or "",
            })
    return out


def _to_anthropic_history(messages: list[ChatMessage]) -> list[dict[str, Any]]:
    """Anthropic represents tool results as user messages with structured content."""
    out: list[dict[str, Any]] = []
    pending_tool_results: list[dict[str, Any]] = []

    def _flush_tool_results():
        if pending_tool_results:
            out.append({"role": "user", "content": pending_tool_results.copy()})
            pending_tool_results.clear()

    for m in messages:
        if m.role == "user":
            _flush_tool_results()
            out.append({"role": "user", "content": m.content or ""})
        elif m.role == "assistant":
            _flush_tool_results()
            blocks: list[dict[str, Any]] = []
            if m.content:
                blocks.append({"type": "text", "text": m.content})
            for tc in (m.tool_calls or []):
                blocks.append({
                    "type": "tool_use",
                    "id": tc["id"],
                    "name": tc["name"],
                    "input": tc.get("arguments") or {},
                })
            out.append({"role": "assistant", "content": blocks or [{"type": "text", "text": ""}]})
        elif m.role == "tool":
            pending_tool_results.append({
                "type": "tool_result",
                "tool_use_id": m.tool_call_id or "",
                "content": m.content or "",
                **({"is_error": True} if m.error else {}),
            })
    _flush_tool_results()
    return out


def _serialize_tool_calls(calls: list[ToolCall]) -> list[dict[str, Any]]:
    return [{"id": c.id, "name": c.name, "arguments": c.arguments} for c in calls]


async def _result(
    new_message_ids: list[UUID], *, iterations: int, finished_reason: str
) -> dict[str, Any]:
    async with session_scope() as session:
        rows = await session.scalars(
            select(ChatMessage)
            .where(ChatMessage.id.in_(new_message_ids))
            .order_by(ChatMessage.created_at)
        )
        messages = list(rows)
    return {
        "new_messages": messages,
        "iterations": iterations,
        "finished_reason": finished_reason,
    }
