"""Thin Crawl4AI wrapper.

Crawl4AI is the LLM-friendly scraper from https://github.com/unclecode/crawl4ai.
We use it for two reasons:
  1. It produces clean Markdown well-suited to feeding into an LLM.
  2. It handles JS-heavy sites via Playwright stealth mode out of the box.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Optional

from app.config import settings

logger = logging.getLogger(__name__)


@dataclass
class CrawlResult:
    url: str
    markdown: str
    cleaned_html: str
    links: list[str]
    title: Optional[str]
    success: bool
    error: Optional[str] = None


class Crawler:
    """Crawl4AI wrapper with a graceful fallback to plain httpx fetch.

    Some hosts (CDN-shielded, logged-in, etc.) block headless browsers; on
    failure we fall back to a plain HTML GET so the discovery pipeline still
    yields *something* the LLM can chew on.
    """

    def __init__(self, concurrency: Optional[int] = None) -> None:
        self.concurrency = concurrency or settings.CRAWLER_CONCURRENCY
        self._sem = asyncio.Semaphore(self.concurrency)

    async def crawl(self, url: str, *, wait_for_selector: Optional[str] = None) -> CrawlResult:
        async with self._sem:
            try:
                from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig

                browser_cfg = BrowserConfig(headless=True, user_agent=settings.CRAWLER_USER_AGENT)
                run_cfg = CrawlerRunConfig(
                    word_count_threshold=10,
                    page_timeout=45000,
                    wait_for=wait_for_selector,
                )
                async with AsyncWebCrawler(config=browser_cfg) as crawler:
                    result = await crawler.arun(url=url, config=run_cfg)
                    if not result.success:
                        return await self._fallback(url, error=result.error_message or "crawl failed")
                    md = getattr(result, "markdown", None) or ""
                    if hasattr(md, "raw_markdown"):
                        md = md.raw_markdown
                    return CrawlResult(
                        url=url,
                        markdown=str(md) or "",
                        cleaned_html=getattr(result, "cleaned_html", "") or "",
                        links=_links_from_result(result),
                        title=getattr(result, "metadata", {}).get("title") if hasattr(result, "metadata") else None,
                        success=True,
                    )
            except Exception as e:  # pragma: no cover - defensive
                logger.warning("Crawl4AI failed for %s: %s", url, e)
                return await self._fallback(url, error=str(e))

    async def _fallback(self, url: str, *, error: str) -> CrawlResult:
        import httpx
        from bs4 import BeautifulSoup

        try:
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                r = await client.get(url, headers={"User-Agent": settings.CRAWLER_USER_AGENT})
            soup = BeautifulSoup(r.text, "lxml")
            title = soup.title.string.strip() if soup.title and soup.title.string else None
            for tag in soup(["script", "style", "noscript"]):
                tag.decompose()
            text = soup.get_text("\n", strip=True)
            links = [a.get("href") for a in soup.find_all("a", href=True)]
            return CrawlResult(
                url=url,
                markdown=text,
                cleaned_html=str(soup),
                links=[l for l in links if l],
                title=title,
                success=r.status_code < 400,
                error=None if r.status_code < 400 else f"HTTP {r.status_code}",
            )
        except Exception as e:
            return CrawlResult(url=url, markdown="", cleaned_html="", links=[], title=None, success=False, error=f"{error}; fallback failed: {e}")


def _links_from_result(result) -> list[str]:
    raw = getattr(result, "links", None)
    if not raw:
        return []
    if isinstance(raw, dict):
        out = []
        for bucket in raw.values():
            if isinstance(bucket, list):
                for item in bucket:
                    href = item.get("href") if isinstance(item, dict) else item
                    if href:
                        out.append(href)
        return out
    if isinstance(raw, list):
        return [l if isinstance(l, str) else l.get("href", "") for l in raw if l]
    return []


crawler = Crawler()
