"""Waterfall enrichment.

Each provider implements the same `Provider` protocol: take a `Subject`
(whatever identifiers we know so far) and return `EnrichmentHit` (the
fields it could fill plus a confidence). The waterfall runs them in priority
order and short-circuits as soon as the lead is "complete enough".

Add a new provider by dropping a module in this folder, exporting a
`provider: Provider` instance, and adding it to PROVIDERS below.
"""
from __future__ import annotations

from app.services.enrichment.types import EnrichmentHit, Provider, Subject  # re-export
from app.services.enrichment import (
    hunter,
    llm_research,
    snov,
    website,
)

PROVIDERS: list[Provider] = [
    # cheaper / faster first; specific (email-finder) before general (LLM synth)
    website.provider,
    hunter.provider,
    snov.provider,
    llm_research.provider,
]


def available_providers() -> list[dict]:
    return [
        {"name": p.name, "configured": p.is_configured(), "fields": p.fields}
        for p in PROVIDERS
    ]
