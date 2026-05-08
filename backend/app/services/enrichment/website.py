"""Website crawl enrichment.

Given a domain or URL we already know, fetch the home page (and a few obvious
sub-pages: /about, /team, /contact) and pull whatever signal we can: company
name from <title>, emails from text, social/LinkedIn URLs from links, location
from contact pages.

Free, fast, and the most reliable single source of "what does this company
even do".
"""
from __future__ import annotations

import logging
import re
from typing import Optional

from app.services.crawler import crawler
from app.services.enrichment.types import EnrichmentHit, Subject

logger = logging.getLogger(__name__)

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
LINKEDIN_RE = re.compile(r"https?://(?:www\.)?linkedin\.com/(?:in|company)/[a-zA-Z0-9._\-/?=&%]+", re.I)
TWITTER_RE = re.compile(r"https?://(?:www\.)?(?:twitter|x)\.com/[a-zA-Z0-9_]+", re.I)


class WebsiteProvider:
    name = "website"
    fields = ["company", "email", "linkedin_url", "domain", "location", "research_excerpt"]

    def is_configured(self) -> bool:
        return True  # Crawl4AI works with no keys.

    async def enrich(self, subject: Subject) -> EnrichmentHit:
        target = _resolve_target(subject)
        if not target:
            return EnrichmentHit(provider=self.name, error="no website / domain to crawl")

        try:
            home = await crawler.crawl(target)
        except Exception as e:
            return EnrichmentHit(provider=self.name, error=str(e))

        if not home.success or not (home.markdown or home.cleaned_html):
            return EnrichmentHit(provider=self.name, error=home.error or "empty crawl")

        text = home.markdown or ""
        html = home.cleaned_html or ""
        out: dict = {"website": target, "domain": _domain_of(target)}

        if home.title and not subject.company:
            out["company"] = _clean_title(home.title)

        emails = _extract_emails(text + " " + html, prefer_domain=out["domain"])
        if emails and not subject.email:
            out["email"] = emails[0]

        m = LINKEDIN_RE.search(html)
        if m and not subject.linkedin_url:
            out["linkedin_url"] = m.group(0).split("?")[0]

        # Capture an excerpt the LLM can chew on later for "research".
        out["research_excerpt"] = (home.markdown or "")[:4000]

        confidence = 70 if (out.get("company") or out.get("email")) else 40

        return EnrichmentHit(
            provider=self.name,
            fields={k: v for k, v in out.items() if v},
            confidence=confidence,
            raw={"links_found": len(home.links), "title": home.title},
        )


def _resolve_target(subject: Subject) -> Optional[str]:
    if subject.website:
        return _ensure_scheme(subject.website)
    if subject.domain:
        return _ensure_scheme(subject.domain)
    if subject.email and "@" in subject.email:
        return _ensure_scheme(subject.email.split("@", 1)[1])
    return None


def _ensure_scheme(s: str) -> str:
    s = s.strip()
    return s if s.startswith(("http://", "https://")) else f"https://{s}"


def _domain_of(url: str) -> str:
    s = url.replace("https://", "").replace("http://", "").split("/")[0]
    return s[4:] if s.startswith("www.") else s


def _clean_title(t: str) -> str:
    parts = re.split(r"[|—–\-]", t)
    parts = [p.strip() for p in parts if p.strip()]
    return parts[0] if parts else t.strip()


def _extract_emails(text: str, *, prefer_domain: Optional[str]) -> list[str]:
    found = list({m.group(0) for m in EMAIL_RE.finditer(text)})
    junk = ("example.com", "yourdomain", "sentry", "wixpress", "@2x", "@3x")
    found = [e for e in found if not any(j in e.lower() for j in junk)]
    if prefer_domain:
        found.sort(key=lambda e: 0 if e.lower().endswith(prefer_domain) else 1)
    return found


provider = WebsiteProvider()
