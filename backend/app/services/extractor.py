"""LLM-driven lead extraction and qualification."""
from __future__ import annotations

import hashlib
import logging
from typing import Any, Optional

from app.services.llm import llm

logger = logging.getLogger(__name__)

EXTRACTION_PROMPT = """\
You are a lead-extraction engine. From the web content below, extract every distinct
opportunity that could become a paying client for the services I offer.

A lead is a person OR a company who:
- Has a project, problem, or job posting that plausibly matches at least one of my services
- Has any contact info (email, website, social handle) OR is identifiable enough to find later
- Is genuinely seeking help (not just discussing a topic)

Services I offer (treat these as the only relevant services — ignore opportunities outside this list):
{services}

Return ONLY a JSON object with this exact shape:
{{
  "leads": [
    {{
      "name": "person or company name",
      "company": "company if known else null",
      "email": "email if found else null",
      "website": "url if found else null",
      "role": "their role/title else null",
      "location": "remote, country, city, etc., else null",
      "project_summary": "1-2 sentences on what they need",
      "match_reason": "why they match my services, citing words from the source",
      "urgency": "low|medium|high",
      "fit_score": 0-100
    }}
  ]
}}

Rules:
- If nothing in the content qualifies, return {{"leads": []}}.
- Never invent contact info — leave it null if not in the source.
- fit_score: 80+ = obvious strong match with budget/urgency signals; 50-79 = plausible match; <50 = weak.

Source URL: {url}

Content:
---
{content}
---
"""

QUALIFY_PROMPT = """\
Re-score this single lead more carefully.

My services: {services}

Lead JSON:
{lead}

Return JSON: {{"fit_score": 0-100, "urgency": "low|medium|high", "qualification_notes": "1-2 sentence reasoning"}}.
"""

QUERY_GEN_PROMPT = """\
Generate {n} short, high-precision search queries that would surface NEW client leads
for someone who offers these services:

{services}

Targets: founders/CTOs posting on Hacker News Who Is Hiring, Reddit r/forhire,
ProductHunt, IndieHackers, Twitter, etc. Bias toward queries that match real wording
people use when describing pain rather than the buzzwords I'd use to sell.

Return JSON: {{"queries": ["...", "..."]}}.
"""

DRAFT_PROMPT = """\
Write a short, personal cold outreach email to this lead. Tone: {tone}. Max 90 words.

Lead:
{lead}

Source excerpt (their own words):
{excerpt}

My services:
{services}

{extra}

Output format:
Subject: ...
<blank line>
<body>

Rules:
- Reference one concrete detail from their post — show I read it.
- Pitch the smallest first step (15-min call OR 60-second Loom).
- No flattery, no "I noticed your impressive...", no emoji.
- Sign off with "— [your name]" so the user can fill it in.
"""


async def generate_queries(services: list[str], n: int = 5) -> list[str]:
    if not services:
        return []
    prompt = QUERY_GEN_PROMPT.format(services="\n".join(f"- {s}" for s in services), n=n)
    try:
        data = await llm.complete(prompt, json_mode=True)
        return data.get("queries", []) if isinstance(data, dict) else []
    except Exception as e:
        logger.warning("Query generation failed: %s", e)
        return []


async def extract_leads(content: str, *, url: str, services: list[str]) -> list[dict[str, Any]]:
    if not content.strip() or not services:
        return []
    truncated = content[:12000]
    prompt = EXTRACTION_PROMPT.format(
        services="\n".join(f"- {s}" for s in services),
        url=url,
        content=truncated,
    )
    try:
        data = await llm.complete(prompt, json_mode=True)
    except Exception as e:
        logger.warning("Extraction failed for %s: %s", url, e)
        return []
    if not isinstance(data, dict):
        return []
    leads = data.get("leads", []) or []
    out = []
    for lead in leads:
        if not isinstance(lead, dict):
            continue
        if not (lead.get("name") or lead.get("company") or lead.get("email")):
            continue
        out.append(lead)
    return out


async def qualify_lead(lead: dict[str, Any], services: list[str]) -> dict[str, Any]:
    prompt = QUALIFY_PROMPT.format(services=", ".join(services), lead=lead)
    try:
        data = await llm.complete(prompt, json_mode=True)
        if isinstance(data, dict):
            return {
                "fit_score": int(data.get("fit_score", lead.get("fit_score", 0))),
                "urgency": data.get("urgency", lead.get("urgency", "medium")),
                "qualification_notes": data.get("qualification_notes"),
            }
    except Exception as e:
        logger.warning("Qualification failed: %s", e)
    return {
        "fit_score": int(lead.get("fit_score", 0) or 0),
        "urgency": lead.get("urgency", "medium"),
        "qualification_notes": None,
    }


async def draft_outreach(
    lead: dict[str, Any],
    *,
    services: list[str],
    tone: str = "friendly",
    extra_context: Optional[str] = None,
) -> tuple[str, str]:
    prompt = DRAFT_PROMPT.format(
        tone=tone,
        lead=lead,
        excerpt=(lead.get("raw_excerpt") or lead.get("project_summary") or "")[:1500],
        services=", ".join(services),
        extra=f"Extra context: {extra_context}" if extra_context else "",
    )
    raw = await llm.complete(prompt, temperature=0.7)
    if not isinstance(raw, str):
        raw = str(raw)
    subject, body = _split_subject_body(raw)
    return subject, body


def _split_subject_body(text: str) -> tuple[str, str]:
    subject = ""
    body = text.strip()
    for line in text.splitlines():
        if line.lower().startswith("subject:"):
            subject = line.split(":", 1)[1].strip()
            body = text.split(line, 1)[1].lstrip("\n")
            break
    return subject or "Quick idea", body.strip()


def fingerprint_lead(lead: dict[str, Any]) -> str:
    """Stable hash for dedupe — email > website > name+url."""
    key = (
        (lead.get("email") or "").lower().strip()
        or (lead.get("website") or "").lower().strip()
        or f"{(lead.get('name') or '').lower().strip()}|{lead.get('source_url', '')}"
    )
    return hashlib.sha256(key.encode("utf-8")).hexdigest()
