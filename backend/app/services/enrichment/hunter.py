"""Hunter.io email finder (https://hunter.io/api). Free tier: 25 searches/month."""
from __future__ import annotations

import logging
from typing import Optional

import httpx

from app.config import settings
from app.services.enrichment.types import EnrichmentHit, Subject

logger = logging.getLogger(__name__)

BASE = "https://api.hunter.io/v2"


class HunterProvider:
    name = "hunter"
    fields = ["email", "domain", "company", "role"]

    def is_configured(self) -> bool:
        return bool(settings.HUNTER_API_KEY)

    async def enrich(self, subject: Subject) -> EnrichmentHit:
        if not self.is_configured():
            return EnrichmentHit(provider=self.name, error="HUNTER_API_KEY not set")

        domain = _normalize_domain(subject.domain or subject.website or _domain_from_email(subject.email))
        if not domain:
            return EnrichmentHit(provider=self.name, error="no domain to query")

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                if subject.name and not subject.email:
                    return await self._email_finder(client, domain, subject.name)
                # No name yet — pull the most likely contact for the domain.
                return await self._domain_search(client, domain)
        except Exception as e:
            logger.warning("Hunter call failed: %s", e)
            return EnrichmentHit(provider=self.name, error=str(e))

    async def _email_finder(self, client: httpx.AsyncClient, domain: str, full_name: str) -> EnrichmentHit:
        first, _, last = full_name.partition(" ")
        params = {
            "domain": domain,
            "first_name": first,
            "last_name": last or first,
            "api_key": settings.HUNTER_API_KEY,
        }
        r = await client.get(f"{BASE}/email-finder", params=params)
        r.raise_for_status()
        data = (r.json() or {}).get("data") or {}
        if not data.get("email"):
            return EnrichmentHit(provider=self.name, error="no email match", raw=data)
        return EnrichmentHit(
            provider=self.name,
            fields={
                "email": data.get("email"),
                "domain": domain,
                "company": data.get("company"),
                "role": data.get("position"),
            },
            confidence=int(data.get("score", 60)),
            raw=data,
        )

    async def _domain_search(self, client: httpx.AsyncClient, domain: str) -> EnrichmentHit:
        params = {"domain": domain, "limit": 5, "api_key": settings.HUNTER_API_KEY}
        r = await client.get(f"{BASE}/domain-search", params=params)
        r.raise_for_status()
        data = (r.json() or {}).get("data") or {}
        emails = data.get("emails") or []
        if not emails:
            return EnrichmentHit(provider=self.name, error="no emails for domain", raw=data)
        # Prefer the highest-scoring email.
        best = max(emails, key=lambda e: e.get("confidence", 0))
        return EnrichmentHit(
            provider=self.name,
            fields={
                "email": best.get("value"),
                "domain": domain,
                "company": data.get("organization"),
                "name": _full_name(best),
                "role": best.get("position"),
            },
            confidence=int(best.get("confidence", 50)),
            raw=data,
        )


def _normalize_domain(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    s = raw.lower().strip()
    s = s.replace("https://", "").replace("http://", "")
    s = s.split("/")[0]
    if s.startswith("www."):
        s = s[4:]
    return s or None


def _domain_from_email(email: Optional[str]) -> Optional[str]:
    if not email or "@" not in email:
        return None
    return email.split("@", 1)[1].lower()


def _full_name(e: dict) -> Optional[str]:
    first = e.get("first_name") or ""
    last = e.get("last_name") or ""
    full = f"{first} {last}".strip()
    return full or None


provider = HunterProvider()
