"""Snov.io email finder (https://snov.io). Free tier: 50 credits / month.

Used as a fallback to Hunter — different sources, so it sometimes catches what
Hunter misses.
"""
from __future__ import annotations

import logging
from typing import Optional

import httpx

from app.config import settings
from app.services.enrichment.types import EnrichmentHit, Subject

logger = logging.getLogger(__name__)

BASE = "https://api.snov.io"


class SnovProvider:
    name = "snov"
    fields = ["email", "domain", "company"]

    def is_configured(self) -> bool:
        return bool(settings.SNOV_CLIENT_ID and settings.SNOV_CLIENT_SECRET)

    async def enrich(self, subject: Subject) -> EnrichmentHit:
        if not self.is_configured():
            return EnrichmentHit(provider=self.name, error="SNOV_CLIENT_ID/SECRET not set")

        domain = _normalize_domain(subject.domain or subject.website or _domain_from_email(subject.email))
        if not domain or not subject.name:
            return EnrichmentHit(provider=self.name, error="need name and domain")

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                token = await self._token(client)
                first, _, last = subject.name.partition(" ")
                payload = {
                    "access_token": token,
                    "firstName": first,
                    "lastName": last or first,
                    "domain": domain,
                }
                r = await client.post(f"{BASE}/v1/get-emails-from-names", data=payload)
                r.raise_for_status()
                data = r.json() or {}
            emails = (data.get("data") or {}).get("emails") or []
            if not emails:
                return EnrichmentHit(provider=self.name, error="no emails", raw=data)
            best = emails[0]
            return EnrichmentHit(
                provider=self.name,
                fields={
                    "email": best.get("email"),
                    "domain": domain,
                },
                confidence=70,
                raw=data,
            )
        except Exception as e:
            logger.warning("Snov call failed: %s", e)
            return EnrichmentHit(provider=self.name, error=str(e))

    async def _token(self, client: httpx.AsyncClient) -> str:
        r = await client.post(
            f"{BASE}/v1/oauth/access_token",
            data={
                "grant_type": "client_credentials",
                "client_id": settings.SNOV_CLIENT_ID,
                "client_secret": settings.SNOV_CLIENT_SECRET,
            },
        )
        r.raise_for_status()
        return (r.json() or {})["access_token"]


def _normalize_domain(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    s = raw.lower().strip().replace("https://", "").replace("http://", "")
    s = s.split("/")[0]
    return s[4:] if s.startswith("www.") else s


def _domain_from_email(email: Optional[str]) -> Optional[str]:
    if not email or "@" not in email:
        return None
    return email.split("@", 1)[1].lower()


provider = SnovProvider()
