"""HTTP/SOCKS proxy pool used by the crawler.

Policy:
  * Each `pick()` returns the active proxy with the OLDEST `last_used_at`
    (least-recently-used), skipping any whose `last_failure_at` is within
    the cooldown window.
  * `pick()` immediately stamps `last_used_at` so two concurrent crawls
    don't both grab the same one in a race.
  * Successful crawls call `mark_success()`; failures call `mark_failure()`
    which puts the proxy in cooldown.
  * If no proxy is available (none configured / all in cooldown), the
    crawler runs without a proxy. Degraded service > no service.

Wire-up: see `crawler.py`. Sources that use httpx directly (Reddit, HN
Algolia API) deliberately skip the pool — they hit public APIs and benefit
nothing from a residential proxy.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from urllib.parse import quote, urlparse, urlunparse
from uuid import UUID

import httpx
from sqlalchemy import func, or_, select, update

from app.db import session_scope
from app.models import Proxy

logger = logging.getLogger(__name__)


COOLDOWN = timedelta(minutes=30)
RECENT_USE_WINDOW = timedelta(minutes=5)
IP_ECHO_URL = "https://api.ipify.org?format=json"


@dataclass
class ProxyHandle:
    id: UUID
    label: str
    url: str

    def to_httpx(self) -> str:
        """Returns the URL in the form httpx wants."""
        return self.url

    def to_playwright(self) -> dict[str, str]:
        """Returns the dict form Playwright (and therefore Crawl4AI) wants."""
        p = urlparse(self.url)
        server = f"{p.scheme}://{p.hostname}"
        if p.port:
            server += f":{p.port}"
        cfg: dict[str, str] = {"server": server}
        if p.username:
            cfg["username"] = p.username
        if p.password:
            cfg["password"] = p.password
        return cfg


# ---------------------------------------------------------------------------
# Pool API
# ---------------------------------------------------------------------------

async def pick() -> Optional[ProxyHandle]:
    """Pick the least-recently-used active proxy outside cooldown. None if none available."""
    cutoff = datetime.now(timezone.utc) - COOLDOWN
    async with session_scope() as session:
        proxy = await session.scalar(
            select(Proxy)
            .where(Proxy.is_active.is_(True))
            .where(or_(Proxy.last_failure_at.is_(None), Proxy.last_failure_at < cutoff))
            .order_by(Proxy.last_used_at.asc().nulls_first())
            .limit(1)
        )
        if not proxy:
            return None
        proxy.last_used_at = datetime.now(timezone.utc)
        return ProxyHandle(id=proxy.id, label=proxy.label, url=proxy.url)


async def mark_success(proxy_id: UUID) -> None:
    async with session_scope() as session:
        await session.execute(
            update(Proxy)
            .where(Proxy.id == proxy_id)
            .values(success_count=Proxy.success_count + 1)
        )


async def mark_failure(proxy_id: UUID, error: str) -> None:
    async with session_scope() as session:
        await session.execute(
            update(Proxy)
            .where(Proxy.id == proxy_id)
            .values(
                failure_count=Proxy.failure_count + 1,
                last_failure_at=datetime.now(timezone.utc),
                last_error=(error or "")[:500],
            )
        )


async def pool_status() -> dict[str, int]:
    cutoff = datetime.now(timezone.utc) - COOLDOWN
    recent = datetime.now(timezone.utc) - RECENT_USE_WINDOW
    async with session_scope() as session:
        total = await session.scalar(select(func.count(Proxy.id))) or 0
        active = await session.scalar(
            select(func.count(Proxy.id)).where(Proxy.is_active.is_(True))
        ) or 0
        in_cooldown = await session.scalar(
            select(func.count(Proxy.id))
            .where(Proxy.is_active.is_(True))
            .where(Proxy.last_failure_at.is_not(None))
            .where(Proxy.last_failure_at >= cutoff)
        ) or 0
        in_use_recently = await session.scalar(
            select(func.count(Proxy.id))
            .where(Proxy.last_used_at.is_not(None))
            .where(Proxy.last_used_at >= recent)
        ) or 0
    return {
        "total": int(total),
        "active": int(active),
        "in_cooldown": int(in_cooldown),
        "in_use_recently": int(in_use_recently),
    }


# ---------------------------------------------------------------------------
# Test helper — proves the proxy actually changes our outbound IP
# ---------------------------------------------------------------------------

async def test_proxy_url(url: str) -> dict[str, Any]:
    """Hit ipify through the given proxy URL. Confirms the proxy works and
    reveals the IP the destination would see."""
    start = time.perf_counter()
    try:
        async with httpx.AsyncClient(proxy=url, timeout=15.0) as client:
            r = await client.get(IP_ECHO_URL)
            r.raise_for_status()
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        ip = (r.json() or {}).get("ip")
        return {"ok": True, "exit_ip": ip, "elapsed_ms": elapsed_ms}
    except Exception as e:
        return {
            "ok": False,
            "error": str(e)[:500],
            "elapsed_ms": int((time.perf_counter() - start) * 1000),
        }


# ---------------------------------------------------------------------------
# Parsing / masking helpers (used by API layer)
# ---------------------------------------------------------------------------

def normalize_url(raw: str) -> str:
    """Normalize whatever proxy format the user pastes into the canonical
    `scheme://user:pass@host:port` form httpx + Playwright both want.

    Accepted inputs:
      http://user:pass@host:port    — full URL, kept as-is
      socks5://user:pass@host:port  — same
      user:pass@host:port           — scheme defaulted to http://
      host:port:user:pass           — common paid-proxy export format
                                     (Webshare, IPRoyal, ProxyEmpire, etc.)
      host:port                     — bare endpoint, no auth
    """
    raw = (raw or "").strip()
    if not raw:
        return raw
    if "://" in raw:
        return raw

    # `host:port:user:pass` — 4 colon-separated parts.
    if raw.count(":") == 3:
        host, port, user, password = raw.split(":")
        if host and port:
            return f"http://{quote(user, safe='')}:{quote(password, safe='')}@{host}:{port}"

    # Otherwise assume bare `host:port` (or `user:pass@host:port`) — let
    # urlparse sort the rest out by prepending http://.
    return "http://" + raw


def mask_url(url: str) -> str:
    """Returns the proxy URL with the password obfuscated. Safe to show in UI/API."""
    try:
        p = urlparse(url)
    except Exception:
        return url
    if not p.password:
        return url
    netloc = ""
    if p.username:
        netloc += quote(p.username, safe="")
        netloc += ":***"
    netloc += "@" + (p.hostname or "")
    if p.port:
        netloc += f":{p.port}"
    return urlunparse((p.scheme, netloc, p.path, p.params, p.query, p.fragment))
