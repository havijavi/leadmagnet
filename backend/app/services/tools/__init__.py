"""Lead-chat tool registry.

Each tool is an async function that takes (project_id, **kwargs) and returns
a JSON-serializable dict. Tools are exposed to the LLM as a list of name +
description + JSON-schema parameters; the LLM picks which one(s) to call.

Add a new tool by:
  1. Writing an async fn returning a dict
  2. Adding a TOOL entry below with a JSON Schema for its arguments
The schema is shown to the LLM verbatim — be precise about what each param does.

Safety: every tool runs server-side under the chat user's session, so it has
the same DB access as the user. Tools that take outbound action (e.g. emails)
should require an explicit user confirmation pattern, not be free-for-all.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Awaitable, Callable
from uuid import UUID

from app.services.tools import (
    crawl,
    discovery as discovery_tools,
    leads as lead_tools,
    memory as memory_tools,
)

logger = logging.getLogger(__name__)


@dataclass
class ToolDef:
    name: str
    description: str
    parameters_schema: dict[str, Any]
    handler: Callable[..., Awaitable[dict[str, Any]]]


TOOLS: list[ToolDef] = [
    ToolDef(
        name="crawl_url",
        description=(
            "Fetch a public URL with Crawl4AI (headless browser, stealth mode) and "
            "return its main content as Markdown. Use this whenever the user asks "
            "you to read, look at, or extract data from a webpage. Works for almost "
            "any public site (bold.org, ProductHunt, GitHub, blogs, company pages, "
            "etc.). LinkedIn aggressively blocks scrapers and will usually fail at "
            "anything beyond a single profile preview — warn the user before "
            "attempting LinkedIn at scale."
        ),
        parameters_schema={
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "The HTTPS URL to fetch."},
                "max_chars": {
                    "type": "integer",
                    "description": "Truncate the returned markdown to this many chars. Default 8000.",
                    "default": 8000,
                },
            },
            "required": ["url"],
        },
        handler=crawl.crawl_url,
    ),
    ToolDef(
        name="save_lead",
        description=(
            "Persist a new lead in the LeadMagnet database. Use this after you've "
            "identified a real prospect (with at least a name or company plus some "
            "way to contact them: email, website, or LinkedIn). Returns the lead id."
        ),
        parameters_schema={
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "company": {"type": "string"},
                "email": {"type": "string"},
                "website": {"type": "string"},
                "domain": {"type": "string"},
                "linkedin_url": {"type": "string"},
                "role": {"type": "string"},
                "location": {"type": "string"},
                "project_summary": {
                    "type": "string",
                    "description": "1-2 sentences on what they need / why they're a fit.",
                },
                "fit_score": {"type": "integer", "minimum": 0, "maximum": 100},
                "urgency": {"type": "string", "enum": ["low", "medium", "high"]},
                "source_url": {
                    "type": "string",
                    "description": "Where you found them. URL of the page / post.",
                },
                "tags": {"type": "array", "items": {"type": "string"}},
            },
        },
        handler=lead_tools.save_lead,
    ),
    ToolDef(
        name="search_leads",
        description=(
            "Search existing leads in the database. Use to check if a prospect "
            "already exists before saving a duplicate, or to recall leads relevant "
            "to the current chat."
        ),
        parameters_schema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Free-text matched against name/company/email/website (case-insensitive).",
                },
                "status": {
                    "type": "string",
                    "enum": ["new", "reviewed", "contacted", "replied", "won", "lost", "trash"],
                },
                "min_fit_score": {"type": "integer", "minimum": 0, "maximum": 100},
                "limit": {"type": "integer", "default": 20, "minimum": 1, "maximum": 100},
            },
        },
        handler=lead_tools.search_leads,
    ),
    ToolDef(
        name="list_lead_sources",
        description="List all configured lead sources (HN threads, Reddit subreddits, custom URLs, etc.).",
        parameters_schema={"type": "object", "properties": {}},
        handler=discovery_tools.list_sources,
    ),
    ToolDef(
        name="trigger_discovery_run",
        description=(
            "Kick off a discovery run over one or more configured sources. Returns "
            "immediately with the run ids; the actual scraping runs in the background. "
            "The user can watch progress on the Discovery page in the dashboard."
        ),
        parameters_schema={
            "type": "object",
            "properties": {
                "source_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "UUID strings of sources from list_lead_sources. Empty = all active sources.",
                },
                "extra_urls": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional list of ad-hoc URLs to crawl in addition to the configured sources.",
                },
            },
        },
        handler=discovery_tools.trigger_discovery,
    ),
    ToolDef(
        name="list_services",
        description="List the user's configured service offerings (what they sell). Important context when qualifying leads.",
        parameters_schema={"type": "object", "properties": {}},
        handler=lead_tools.list_services,
    ),
    ToolDef(
        name="remember",
        description=(
            "Append a short note to this chat project's persistent memory. The note "
            "becomes available in every future turn of THIS project's chat. Use it "
            "to record durable facts: target customer profile, decisions made, "
            "preferences, ongoing tasks, etc. Do NOT use it as a scratchpad — only "
            "for things worth remembering across sessions."
        ),
        parameters_schema={
            "type": "object",
            "properties": {
                "note": {
                    "type": "string",
                    "description": "The fact / decision / preference to remember, one to two sentences.",
                },
            },
            "required": ["note"],
        },
        handler=memory_tools.remember,
    ),
]


TOOLS_BY_NAME: dict[str, ToolDef] = {t.name: t for t in TOOLS}


def tools_for_llm() -> list[dict[str, Any]]:
    """Strip handlers out for sending to the LLM."""
    return [
        {"name": t.name, "description": t.description, "parameters_schema": t.parameters_schema}
        for t in TOOLS
    ]


async def execute_tool(name: str, arguments: dict[str, Any], project_id: UUID) -> dict[str, Any]:
    """Look up + run a tool. Returns a dict; never raises (errors get embedded)."""
    tool = TOOLS_BY_NAME.get(name)
    if not tool:
        return {"ok": False, "error": f"unknown tool: {name}"}
    try:
        return await tool.handler(project_id=project_id, **(arguments or {}))
    except TypeError as e:
        return {"ok": False, "error": f"bad arguments for {name}: {e}"}
    except Exception as e:
        logger.exception("tool %s failed", name)
        return {"ok": False, "error": str(e)[:500]}
