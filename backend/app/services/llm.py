"""LLM client — DB-configured, multi-provider.

Each LLM call looks up the active LLMConfig row from the database. If none is
active, falls back to LLM_* env vars (legacy / first-boot bootstrap). If both
are empty, mock mode kicks in.

Two provider kinds are supported:

  * 'openai_compat' — anything that speaks the /v1/chat/completions schema:
      OpenAI, DeepSeek, Qwen (DashScope compat), Gemini (compat endpoint),
      OpenRouter, Ollama, vLLM, LM Studio, etc.

  * 'anthropic' — Claude. Different endpoint (/v1/messages), different auth
      header (x-api-key), different request/response shape.

Add a third kind by extending PROVIDER_KINDS and implementing the call in
LLMClient. Most providers don't need this — they just expose openai_compat.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Optional

import httpx
from sqlalchemy import select
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import settings

logger = logging.getLogger(__name__)


PROVIDER_KINDS = {"openai_compat", "anthropic"}


# ---------------------------------------------------------------------------
# Provider presets — used by the dashboard "+ New LLM" modal to fill defaults.
# Order matters: surfaced to the UI in this order.
# ---------------------------------------------------------------------------

PROVIDER_PRESETS: list[dict[str, Any]] = [
    {
        "id": "deepseek",
        "label": "DeepSeek",
        "provider_kind": "openai_compat",
        "base_url": "https://api.deepseek.com/v1",
        "model_placeholder": "deepseek-chat",
        "api_key_help": "Get at platform.deepseek.com → API keys. Starts with sk-",
    },
    {
        "id": "openai",
        "label": "OpenAI",
        "provider_kind": "openai_compat",
        "base_url": "https://api.openai.com/v1",
        "model_placeholder": "gpt-4o-mini",
        "api_key_help": "Get at platform.openai.com → API keys. Starts with sk-",
    },
    {
        "id": "anthropic",
        "label": "Anthropic (Claude)",
        "provider_kind": "anthropic",
        "base_url": "https://api.anthropic.com/v1",
        "model_placeholder": "claude-3-5-sonnet-20241022",
        "api_key_help": "Get at console.anthropic.com → API keys. Starts with sk-ant-",
    },
    {
        "id": "qwen",
        "label": "Qwen (DashScope)",
        "provider_kind": "openai_compat",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "model_placeholder": "qwen-plus",
        "api_key_help": "Get at dashscope.console.aliyun.com → API keys.",
    },
    {
        "id": "gemini",
        "label": "Google Gemini",
        "provider_kind": "openai_compat",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "model_placeholder": "gemini-2.0-flash",
        "api_key_help": "Get at aistudio.google.com → API keys.",
    },
    {
        "id": "openrouter",
        "label": "OpenRouter",
        "provider_kind": "openai_compat",
        "base_url": "https://openrouter.ai/api/v1",
        "model_placeholder": "anthropic/claude-3.5-sonnet",
        "api_key_help": "Get at openrouter.ai → Keys. Lets you use one key for many models.",
    },
    {
        "id": "ollama",
        "label": "Ollama (local)",
        "provider_kind": "openai_compat",
        "base_url": "http://host.docker.internal:11434/v1",
        "model_placeholder": "qwen2.5:14b",
        "api_key_help": "Run Ollama on the VPS host; the API key is a dummy string like 'ollama'.",
    },
    {
        "id": "custom",
        "label": "Custom (other OpenAI-compatible)",
        "provider_kind": "openai_compat",
        "base_url": "",
        "model_placeholder": "",
        "api_key_help": "Any service speaking POST /v1/chat/completions with Authorization: Bearer.",
    },
]


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------

class LLMError(RuntimeError):
    pass


@dataclass
class LLMClient:
    api_key: str
    base_url: str
    model: str
    provider_kind: str = "openai_compat"
    source: str = "env"  # 'env' | 'db' | 'none' — informational

    @property
    def is_mock(self) -> bool:
        return not self.api_key

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    async def complete(
        self,
        prompt: str,
        system: str = "You are a precise extraction engine. Follow instructions exactly.",
        json_mode: bool = False,
        temperature: float = 0.2,
        max_tokens: int = 2048,
    ) -> Any:
        if self.is_mock:
            return _mock(prompt, json_mode)
        if self.provider_kind == "anthropic":
            return await self._call_anthropic(prompt, system, json_mode, temperature, max_tokens)
        return await self._call_openai(prompt, system, json_mode, temperature, max_tokens)

    async def _call_openai(self, prompt, system, json_mode, temperature, max_tokens):
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        async with httpx.AsyncClient(timeout=120.0) as client:
            r = await client.post(
                f"{self.base_url.rstrip('/')}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            if r.status_code >= 400:
                logger.error("LLM error %s: %s", r.status_code, r.text[:500])
                raise LLMError(f"LLM call failed: HTTP {r.status_code} — {r.text[:200]}")
            data = r.json()

        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as e:
            raise LLMError(f"Malformed OpenAI-style response: {data}") from e

        return _coerce_json(content) if json_mode else content

    async def _call_anthropic(self, prompt, system, json_mode, temperature, max_tokens):
        # Anthropic doesn't have native JSON mode; we lean on _coerce_json to
        # parse the model's textual response. Reminding the model to output
        # JSON helps reliability.
        full_user = (
            prompt
            + "\n\nReturn ONLY a single JSON object, with no prose before or after."
            if json_mode
            else prompt
        )

        payload = {
            "model": self.model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "system": system,
            "messages": [{"role": "user", "content": full_user}],
        }

        async with httpx.AsyncClient(timeout=120.0) as client:
            r = await client.post(
                f"{self.base_url.rstrip('/')}/messages",
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            if r.status_code >= 400:
                logger.error("Anthropic error %s: %s", r.status_code, r.text[:500])
                raise LLMError(f"Anthropic call failed: HTTP {r.status_code} — {r.text[:200]}")
            data = r.json()

        try:
            # Anthropic returns content as a list of blocks.
            blocks = data["content"]
            text_parts = [b["text"] for b in blocks if b.get("type") == "text"]
            content = "".join(text_parts)
        except (KeyError, TypeError) as e:
            raise LLMError(f"Malformed Anthropic response: {data}") from e

        return _coerce_json(content) if json_mode else content


# ---------------------------------------------------------------------------
# Active-config lookup
# ---------------------------------------------------------------------------

async def get_active_client() -> LLMClient:
    """Fetch the active LLMConfig from the DB, falling back to env, then mock."""
    # Import here to avoid circular import at module load.
    from app.db import session_scope
    from app.models import LLMConfig

    try:
        async with session_scope() as session:
            cfg = await session.scalar(
                select(LLMConfig).where(LLMConfig.is_active.is_(True)).limit(1)
            )
            if cfg:
                return LLMClient(
                    api_key=cfg.api_key,
                    base_url=cfg.base_url,
                    model=cfg.model,
                    provider_kind=cfg.provider_kind,
                    source="db",
                )
    except Exception as e:  # pragma: no cover - defensive on first-boot races
        logger.warning("Could not load active LLMConfig from DB: %s", e)

    if settings.LLM_API_KEY:
        return LLMClient(
            api_key=settings.LLM_API_KEY,
            base_url=settings.LLM_BASE_URL,
            model=settings.LLM_MODEL,
            provider_kind="openai_compat",
            source="env",
        )

    return LLMClient(api_key="", base_url="", model="", source="none")


async def get_active_status() -> dict[str, Any]:
    """Used by /health and the LLM admin page."""
    from app.db import session_scope
    from app.models import LLMConfig

    async with session_scope() as session:
        cfg = await session.scalar(
            select(LLMConfig).where(LLMConfig.is_active.is_(True)).limit(1)
        )
        if cfg:
            return {
                "configured": True,
                "source": "db",
                "provider_kind": cfg.provider_kind,
                "base_url": cfg.base_url,
                "model": cfg.model,
                "config_id": str(cfg.id),
                "config_name": cfg.name,
            }
    if settings.LLM_API_KEY:
        return {
            "configured": True,
            "source": "env",
            "provider_kind": "openai_compat",
            "base_url": settings.LLM_BASE_URL,
            "model": settings.LLM_MODEL,
            "config_id": None,
            "config_name": ".env (LLM_API_KEY)",
        }
    return {
        "configured": False,
        "source": "none",
        "provider_kind": None,
        "base_url": None,
        "model": None,
        "config_id": None,
        "config_name": None,
    }


# ---------------------------------------------------------------------------
# Compatibility proxy — existing callers do `from app.services.llm import llm`
# and `await llm.complete(...)`. Keep that ergonomic.
# ---------------------------------------------------------------------------

class _LLMProxy:
    """Delegates every call to the currently-active client at call time."""

    async def complete(self, *args: Any, **kwargs: Any) -> Any:
        client = await get_active_client()
        return await client.complete(*args, **kwargs)

    @property
    def is_mock(self) -> bool:
        # Synchronous best-effort — used in a few logging paths. Reads env
        # only; the /health endpoint uses the async get_active_status() for
        # accurate UI display.
        return not settings.LLM_API_KEY


llm = _LLMProxy()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock(prompt: str, json_mode: bool) -> Any:
    """Canned responses for when no LLM is configured. Keeps the pipeline
    exerciseable end-to-end before the user adds a key."""
    lowered = prompt.lower()
    if json_mode and "extract" in lowered and "lead" in lowered:
        return {
            "leads": [
                {
                    "name": "Mock Founder",
                    "company": "Acme Demo Inc.",
                    "email": "founder@example.com",
                    "website": "https://example.com",
                    "role": "CEO",
                    "location": "Remote",
                    "project_summary": "Looking for a Next.js dev to rebuild marketing site with AI features.",
                    "match_reason": "Mentions Next.js and AI explicitly.",
                    "urgency": "high",
                    "fit_score": 85,
                }
            ]
        }
    if json_mode and "qualify" in lowered:
        return {
            "fit_score": 72,
            "urgency": "medium",
            "qualification_notes": "Mock qualification — add an LLM provider in the dashboard for real analysis.",
        }
    if json_mode and "search queries" in lowered:
        return {
            "queries": [
                "looking for next.js developer",
                "hiring AI integration consultant",
                "need branding designer SaaS",
            ]
        }
    if "draft" in lowered or "outreach" in lowered:
        return (
            "Subject: Quick idea for {company}\n\n"
            "Hi {name},\n\nNoticed your project on {source}. We help teams ship "
            "Next.js + AI features fast — happy to send a 60-second Loom of how we'd "
            "approach yours. Worth a look?\n\nBest,\n— [your name]"
        )
    if json_mode:
        return {}
    return "(mock response — add an LLM provider in the dashboard to enable real LLM calls)"


def _coerce_json(content: str) -> Any:
    content = content.strip()
    if content.startswith("```"):
        lines = content.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        content = "\n".join(lines)
    try:
        return json.loads(content)
    except json.JSONDecodeError as e:
        start = content.find("{")
        end = content.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(content[start : end + 1])
            except json.JSONDecodeError:
                pass
        raise LLMError(f"Could not parse JSON from LLM response: {e}")


def mask_key(key: str) -> str:
    """Show first 4 + last 4 chars only. Used in API responses."""
    if not key:
        return ""
    if len(key) <= 12:
        return "•" * len(key)
    return f"{key[:4]}…{key[-4:]}"
