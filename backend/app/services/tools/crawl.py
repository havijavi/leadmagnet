"""Crawl-a-URL tool. Thin wrapper around our existing Crawl4AI service."""
from __future__ import annotations

import ipaddress
import logging
from typing import Any
from urllib.parse import urlparse
from uuid import UUID

from app.services.crawler import crawler

logger = logging.getLogger(__name__)

# Block obvious SSRF targets — the LLM shouldn't be able to make us hit our
# own internal services or RFC1918 addresses.
BLOCKED_HOSTS = {"localhost", "localhost.", "0.0.0.0", "metadata.google.internal", "instance-data"}


def _is_safe_url(url: str) -> tuple[bool, str]:
    try:
        parsed = urlparse(url)
    except Exception as e:
        return False, f"invalid URL: {e}"
    if parsed.scheme not in ("http", "https"):
        return False, "only http/https URLs are allowed"
    host = (parsed.hostname or "").lower()
    if not host:
        return False, "missing hostname"
    if host in BLOCKED_HOSTS:
        return False, f"blocked host: {host}"
    # Block private IP ranges to prevent reaching internal services.
    try:
        ip = ipaddress.ip_address(host)
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            return False, f"blocked private/loopback IP: {host}"
    except ValueError:
        # Not an IP literal — fine, hostnames resolve at fetch time. Crawl4AI's
        # outbound is via Playwright which respects the same network rules.
        pass
    return True, ""


async def crawl_url(*, project_id: UUID, url: str, max_chars: int = 8000) -> dict[str, Any]:
    ok, reason = _is_safe_url(url)
    if not ok:
        return {"ok": False, "error": reason}

    result = await crawler.crawl(url)
    if not result.success:
        return {
            "ok": False,
            "url": url,
            "error": result.error or "crawl failed (no content)",
        }
    md = (result.markdown or "")[: max(100, int(max_chars))]
    return {
        "ok": True,
        "url": result.url,
        "title": result.title,
        "markdown": md,
        "truncated": len(result.markdown or "") > max_chars,
        "link_count": len(result.links or []),
    }
