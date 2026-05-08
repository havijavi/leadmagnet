from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional, Protocol


@dataclass
class Subject:
    """Whatever we know about a lead going into the enrichment waterfall."""
    name: Optional[str] = None
    company: Optional[str] = None
    email: Optional[str] = None
    domain: Optional[str] = None
    website: Optional[str] = None
    linkedin_url: Optional[str] = None
    role: Optional[str] = None
    location: Optional[str] = None

    def merge(self, fields: dict[str, Any]) -> "Subject":
        """Return a copy of this subject with non-None fields overlaid."""
        merged = self.__dict__.copy()
        for k, v in fields.items():
            if v and k in merged and not merged.get(k):
                merged[k] = v
        return Subject(**merged)

    def is_complete(self) -> bool:
        """We treat an enrichment as 'complete' if we have an email + a name + a company."""
        return bool(self.email and (self.name or self.company))


@dataclass
class EnrichmentHit:
    provider: str
    fields: dict[str, Any] = field(default_factory=dict)
    confidence: int = 50  # 0-100, used to break ties when two providers disagree
    raw: dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None


class Provider(Protocol):
    name: str
    fields: list[str]  # the fields this provider can plausibly fill

    def is_configured(self) -> bool: ...

    async def enrich(self, subject: Subject) -> EnrichmentHit: ...
