"""Generic URL harvester — point Crawl4AI at any single page.

Useful for: a job board listing page, a directory, a Show HN thread, a
Google Sheet you're keeping yourself, etc.
"""
from __future__ import annotations

from typing import Any

from app.services.crawler import crawler


async def fetch(config: dict[str, Any]) -> list[tuple[str, str]]:
    urls = config.get("urls") or ([config["url"]] if config.get("url") else [])
    out: list[tuple[str, str]] = []
    for url in urls:
        result = await crawler.crawl(url)
        if result.success and result.markdown:
            out.append((url, result.markdown[:12000]))
    return out
