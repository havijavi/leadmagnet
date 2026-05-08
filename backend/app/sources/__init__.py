"""Lead-source registry.

Each source is a small async fetch() returning a list of (url, content) tuples,
which the discovery worker then feeds to the LLM extractor.
"""
from typing import Any, Awaitable, Callable

from app.sources import generic_url, google_search, hackernews, reddit

SourceFn = Callable[[dict[str, Any]], Awaitable[list[tuple[str, str]]]]

REGISTRY: dict[str, SourceFn] = {
    "hackernews": hackernews.fetch,
    "reddit": reddit.fetch,
    "google": google_search.fetch,
    "url": generic_url.fetch,
}
