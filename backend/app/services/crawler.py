"""Thin Crawl4AI wrapper with proxy-pool integration.

Two stages per request:
  1. Try Crawl4AI (Playwright + stealth). Picks an LRU proxy from the pool
     if one is available; runs direct otherwise.
  2. If that fails, fall back to a plain httpx GET (same proxy reused so we
     stay consistent in case of geo-restrictions). This catches Cloudflare-
     protected static pages where Playwright won't add value.

Both stages report success/failure back to the pool so it can rotate away
from misbehaving proxies.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Optional

from app.config import settings
from app.services import proxy_pool

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
    proxy_label: Optional[str] = None  # which proxy was used, if any


class Crawler:
    def __init__(self, concurrency: Optional[int] = None) -> None:
        self.concurrency = concurrency or settings.CRAWLER_CONCURRENCY
        self._sem = asyncio.Semaphore(self.concurrency)

    async def crawl(self, url: str, *, wait_for_selector: Optional[str] = None) -> CrawlResult:
        async with self._sem:
            proxy = await proxy_pool.pick()
            proxy_label = proxy.label if proxy else None

            try:
                from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig

                browser_kwargs: dict = {
                    "headless": True,
                    "user_agent": settings.CRAWLER_USER_AGENT,
                }
                if proxy:
                    browser_kwargs["proxy_config"] = proxy.to_playwright()
                browser_cfg = BrowserConfig(**browser_kwargs)

                run_cfg = CrawlerRunConfig(
                    word_count_threshold=10,
                    page_timeout=45000,
                    wait_for=wait_for_selector,
                )
                async with AsyncWebCrawler(config=browser_cfg) as crawler:
                    result = await crawler.arun(url=url, config=run_cfg)
                    if not result.success:
                        if proxy:
                            await proxy_pool.mark_failure(proxy.id, result.error_message or "crawl4ai failed")
                        return await self._fallback(
                            url,
                            error=result.error_message or "crawl failed",
                            proxy=proxy,
                            proxy_label=proxy_label,
                        )
                    md = getattr(result, "markdown", None) or ""
                    if hasattr(md, "raw_markdown"):
                        md = md.raw_markdown

                    if proxy:
                        await proxy_pool.mark_success(proxy.id)

                    return CrawlResult(
                        url=url,
                        markdown=str(md) or "",
                        cleaned_html=getattr(result, "cleaned_html", "") or "",
                        links=_links_from_result(result),
                        title=getattr(result, "metadata", {}).get("title") if hasattr(result, "metadata") else None,
                        success=True,
                        proxy_label=proxy_label,
                    )
            except Exception as e:
                logger.warning("Crawl4AI failed for %s (proxy=%s): %s", url, proxy_label, e)
                if proxy:
                    await proxy_pool.mark_failure(proxy.id, str(e))
                return await self._fallback(url, error=str(e), proxy=proxy, proxy_label=proxy_label)

    async def _fallback(
        self,
        url: str,
        *,
        error: str,
        proxy: Optional[proxy_pool.ProxyHandle] = None,
        proxy_label: Optional[str] = None,
    ) -> CrawlResult:
        import httpx
        from bs4 import BeautifulSoup

        client_kwargs: dict = {"timeout": 30.0, "follow_redirects": True}
        if proxy:
            client_kwargs["proxy"] = proxy.to_httpx()

        try:
            async with httpx.AsyncClient(**client_kwargs) as client:
                r = await client.get(url, headers={"User-Agent": settings.CRAWLER_USER_AGENT})
            soup = BeautifulSoup(r.text, "lxml")
            title = soup.title.string.strip() if soup.title and soup.title.string else None
            for tag in soup(["script", "style", "noscript"]):
                tag.decompose()
            text = soup.get_text("\n", strip=True)
            links = [a.get("href") for a in soup.find_all("a", href=True)]
            ok = r.status_code < 400
            if proxy:
                if ok:
                    await proxy_pool.mark_success(proxy.id)
                else:
                    await proxy_pool.mark_failure(proxy.id, f"HTTP {r.status_code}")
            return CrawlResult(
                url=url,
                markdown=text,
                cleaned_html=str(soup),
                links=[l for l in links if l],
                title=title,
                success=ok,
                error=None if ok else f"HTTP {r.status_code}",
                proxy_label=proxy_label,
            )
        except Exception as e:
            if proxy:
                await proxy_pool.mark_failure(proxy.id, str(e))
            return CrawlResult(
                url=url,
                markdown="",
                cleaned_html="",
                links=[],
                title=None,
                success=False,
                error=f"{error}; fallback failed: {e}",
                proxy_label=proxy_label,
            )


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
