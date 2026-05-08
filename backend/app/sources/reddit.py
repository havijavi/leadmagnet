"""Reddit subreddit harvester via public .json endpoints (no auth needed)."""
from __future__ import annotations

import logging
from typing import Any

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


async def fetch(config: dict[str, Any]) -> list[tuple[str, str]]:
    subreddit = config.get("subreddit", "forhire")
    limit = int(config.get("limit", 50))
    sort = config.get("sort", "new")  # new|hot|top
    flair = config.get("flair")  # optional, e.g. "Hiring"

    url = f"https://www.reddit.com/r/{subreddit}/{sort}.json"
    params = {"limit": str(limit)}
    if flair:
        params["q"] = f'flair:"{flair}"'

    headers = {"User-Agent": settings.CRAWLER_USER_AGENT}
    async with httpx.AsyncClient(timeout=30.0, headers=headers) as client:
        r = await client.get(url, params=params)
        if r.status_code == 429:
            logger.warning("Reddit rate-limited for r/%s", subreddit)
            return []
        r.raise_for_status()
        data = r.json()

    out: list[tuple[str, str]] = []
    for child in data.get("data", {}).get("children", []):
        post = child.get("data") or {}
        if post.get("stickied"):
            continue
        title = post.get("title") or ""
        body = post.get("selftext") or ""
        permalink = post.get("permalink") or ""
        post_url = f"https://reddit.com{permalink}" if permalink else post.get("url", "")
        text = f"# {title}\n\n{body}".strip()
        if text:
            out.append((post_url, text))
    return out
