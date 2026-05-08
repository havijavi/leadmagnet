"""Hacker News 'Who is hiring' / 'Who wants to be hired' threads.

Uses the official Algolia search API (no key required) to find the most recent
monthly thread, then pulls each top-level comment via the official Firebase
API.
"""
from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

ALGOLIA_SEARCH = "https://hn.algolia.com/api/v1/search"
HN_ITEM = "https://hacker-news.firebaseio.com/v0/item/{id}.json"

THREAD_QUERIES = {
    "who_is_hiring": "Ask HN: Who is hiring?",
    "who_wants_to_be_hired": "Ask HN: Who wants to be hired?",
    "freelancer_seeking_freelancer": "Ask HN: Freelancer? Seeking freelancer?",
}


async def fetch(config: dict[str, Any]) -> list[tuple[str, str]]:
    thread_kind = config.get("thread", "who_is_hiring")
    limit = int(config.get("limit", 30))
    query = THREAD_QUERIES.get(thread_kind, THREAD_QUERIES["who_is_hiring"])

    async with httpx.AsyncClient(timeout=30.0) as client:
        # Find the latest matching thread.
        r = await client.get(
            ALGOLIA_SEARCH,
            params={"query": query, "tags": "story", "hitsPerPage": 5},
        )
        r.raise_for_status()
        hits = r.json().get("hits", [])
        thread_hits = [h for h in hits if query.lower() in (h.get("title") or "").lower()]
        if not thread_hits:
            logger.warning("No HN thread found for %r", query)
            return []
        story = thread_hits[0]
        story_id = story["objectID"]

        # Fetch the story to get its top-level comment ids.
        story_resp = await client.get(HN_ITEM.format(id=story_id))
        story_resp.raise_for_status()
        story_data = story_resp.json()
        comment_ids: list[int] = (story_data.get("kids") or [])[:limit]

        # Fan out for comments.
        out: list[tuple[str, str]] = []
        for cid in comment_ids:
            try:
                cr = await client.get(HN_ITEM.format(id=cid))
                cr.raise_for_status()
                c = cr.json() or {}
                if c.get("deleted") or c.get("dead"):
                    continue
                text = _strip_html(c.get("text") or "")
                if not text.strip():
                    continue
                url = f"https://news.ycombinator.com/item?id={cid}"
                out.append((url, text))
            except Exception as e:
                logger.debug("HN comment %s failed: %s", cid, e)
        return out


def _strip_html(html: str) -> str:
    from bs4 import BeautifulSoup

    return BeautifulSoup(html, "lxml").get_text("\n", strip=True)
