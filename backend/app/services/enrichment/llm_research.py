"""LLM-driven prospect research.

This is the Clay-style "AI research on prospects" step. It takes whatever
structured fields + website excerpt the earlier waterfall stages produced, and
asks the LLM to synthesize a prospect dossier:

  * company_one_liner
  * employee_estimate
  * tech_stack_guess
  * recent_signals
  * pain_points
  * outreach_hooks
  * fit_score (re-scored against the user's services)

Output is stored on the lead as research_summary + research_data. Costs ~1
LLM call per lead, so cheap with DeepSeek/Qwen.
"""
from __future__ import annotations

import logging

from sqlalchemy import select

from app.db import session_scope
from app.models import ServiceOffering
from app.services.enrichment.types import EnrichmentHit, Subject
from app.services.llm import llm

logger = logging.getLogger(__name__)


RESEARCH_PROMPT = """\
Build a concise prospect research dossier from the structured + unstructured
inputs below. Be specific. Do not invent facts — if a field is unknown, say
"unknown".

My services (used to score fit):
{services}

Known fields about the prospect:
{subject}

Website excerpt:
---
{excerpt}
---

Return JSON with this exact shape:
{{
  "summary": "2-3 sentence dossier — who they are, what they do, why I should care",
  "company_one_liner": "...",
  "employee_estimate": "1-10 | 11-50 | 51-200 | 201-1000 | 1000+ | unknown",
  "tech_stack_guess": ["..."],
  "recent_signals": ["fundraise/launch/hire/etc"],
  "pain_points": ["..."],
  "outreach_hooks": ["concrete details I can reference in a cold email"],
  "fit_score": 0-100
}}
"""


class LLMResearchProvider:
    name = "llm_research"
    fields = ["research_summary", "research_data", "fit_score"]

    def is_configured(self) -> bool:
        # We always run; mock mode just returns canned output.
        return True

    async def enrich(self, subject: Subject) -> EnrichmentHit:
        services = await _service_names()
        # The website provider stuffs an excerpt into raw — best-effort pull.
        excerpt = (getattr(subject, "_research_excerpt", None) or "")[:4000]

        prompt = RESEARCH_PROMPT.format(
            services="\n".join(f"- {s}" for s in services) or "(none configured)",
            subject=_subject_block(subject),
            excerpt=excerpt or "(no website content available)",
        )

        try:
            data = await llm.complete(prompt, json_mode=True)
        except Exception as e:
            logger.warning("LLM research failed: %s", e)
            return EnrichmentHit(provider=self.name, error=str(e))

        if not isinstance(data, dict):
            return EnrichmentHit(provider=self.name, error="bad LLM response")

        summary = data.get("summary") or data.get("company_one_liner")
        return EnrichmentHit(
            provider=self.name,
            fields={
                "research_summary": summary,
                "research_data": data,
                "fit_score": int(data.get("fit_score", 0) or 0),
            },
            confidence=int(data.get("fit_score", 50) or 50),
            raw=data,
        )


def _subject_block(s: Subject) -> str:
    bits = []
    for k in ("name", "company", "email", "website", "domain", "linkedin_url", "role", "location"):
        v = getattr(s, k, None)
        if v:
            bits.append(f"  {k}: {v}")
    return "\n".join(bits) or "  (only the website excerpt below)"


async def _service_names() -> list[str]:
    async with session_scope() as session:
        rows = await session.scalars(select(ServiceOffering).where(ServiceOffering.is_active.is_(True)))
        return [r.name for r in rows]


provider = LLMResearchProvider()
