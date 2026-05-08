"""Google-style search via a self-hosted SearXNG instance.

Why not Google directly? Google rate-limits hard and bans scrapers fast.
SearXNG (https://github.com/searxng/searxng) is a self-hostable meta-search
engine with a JSON API. Set SEARXNG_URL in .env to enable.

If SEARXNG_URL is unset we return [] — the rest of the pipeline still runs,
you just won't get search-driven discovery.
"""
from __future__ import annotations

import logging
from typing import Any

import httpx

from app.config import settings
from app.services.crawler import crawler

logger = logging.getLogger(__name__)


async def fetch(config: dict[str, Any]) -> list[tuple[str, str]]:
    if not settings.SEARXNG_URL:
        logger.info("SEARXNG_URL not set — google_search returns nothing.")
        return []

    queries = config.get("queries") or []
    if isinstance(queries, str):
        queries = [queries]
    max_results_per_query = int(config.get("max_results_per_query", 5))

    out: list[tuple[str, str]] = []
    async with httpx.AsyncClient(timeout=30.0) as client:
        for q in queries:
            try:
                r = await client.get(
                    f"{settings.SEARXNG_URL.rstrip('/')}/search",
                    params={"q": q, "format": "json", "language": "en"},
                )
                r.raise_for_status()
                results = (r.json() or {}).get("results", [])[:max_results_per_query]
            except Exception as e:
                logger.warning("SearXNG query failed (%s): %s", q, e)
                continue

            for result in results:
                target = result.get("url")
                if not target:
                    continue
                page = await crawler.crawl(target)
                if page.success and page.markdown:
                    out.append((target, page.markdown[:8000]))
    return out
