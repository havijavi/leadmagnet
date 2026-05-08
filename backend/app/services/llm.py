"""OpenAI-compatible LLM client.

Works with DeepSeek, Qwen (DashScope compat mode), OpenAI, OpenRouter, Ollama,
or any other provider that exposes the /v1/chat/completions schema. If
LLM_API_KEY is empty we run in mock mode so the rest of the pipeline can be
exercised end-to-end before you commit to paying for tokens.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Optional

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import settings

logger = logging.getLogger(__name__)


class LLMError(RuntimeError):
    pass


class LLMClient:
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
    ) -> None:
        self.api_key = api_key if api_key is not None else settings.LLM_API_KEY
        self.base_url = (base_url or settings.LLM_BASE_URL).rstrip("/")
        self.model = model or settings.LLM_MODEL

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
            return self._mock(prompt, json_mode)

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
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            if r.status_code >= 400:
                logger.error("LLM error %s: %s", r.status_code, r.text[:500])
                raise LLMError(f"LLM call failed: {r.status_code}")
            data = r.json()

        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as e:
            raise LLMError(f"Malformed LLM response: {data}") from e

        if json_mode:
            return _coerce_json(content)
        return content

    def _mock(self, prompt: str, json_mode: bool) -> Any:
        """Plausible canned responses so the pipeline runs without an API key."""
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
                "qualification_notes": "Mock qualification — set LLM_API_KEY to get real analysis.",
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
        return "(mock response — set LLM_API_KEY to enable real LLM calls)"


def _coerce_json(content: str) -> Any:
    content = content.strip()
    if content.startswith("```"):
        # Strip fenced code blocks (some models add them even in JSON mode).
        lines = content.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        content = "\n".join(lines)
    try:
        return json.loads(content)
    except json.JSONDecodeError as e:
        # Last-ditch attempt: extract the first {...} block.
        start = content.find("{")
        end = content.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(content[start : end + 1])
            except json.JSONDecodeError:
                pass
        raise LLMError(f"Could not parse JSON from LLM response: {e}")


llm = LLMClient()
