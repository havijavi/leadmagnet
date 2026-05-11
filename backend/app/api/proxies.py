from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_admin
from app.db import get_session
from app.models import Proxy
from app.schemas import (
    ProxyBulkIn,
    ProxyIn,
    ProxyOut,
    ProxyPoolStatus,
    ProxyTestRequest,
    ProxyTestResult,
    ProxyUpdate,
)
from app.services import proxy_pool

router = APIRouter(dependencies=[Depends(require_admin)])


def _to_out(p: Proxy) -> ProxyOut:
    return ProxyOut(
        id=p.id,
        label=p.label,
        url_preview=proxy_pool.mask_url(p.url),
        is_active=p.is_active,
        success_count=p.success_count or 0,
        failure_count=p.failure_count or 0,
        last_used_at=p.last_used_at,
        last_failure_at=p.last_failure_at,
        last_error=p.last_error,
        created_at=p.created_at,
    )


# ---- status ------------------------------------------------------------

@router.get("/status", response_model=ProxyPoolStatus)
async def status() -> ProxyPoolStatus:
    return ProxyPoolStatus(**await proxy_pool.pool_status())


# ---- CRUD --------------------------------------------------------------

@router.get("", response_model=list[ProxyOut])
async def list_proxies(session: AsyncSession = Depends(get_session)) -> list[ProxyOut]:
    rows = await session.scalars(select(Proxy).order_by(Proxy.created_at.desc()))
    return [_to_out(r) for r in rows]


@router.post("", response_model=ProxyOut, status_code=201)
async def create_proxy(payload: ProxyIn, session: AsyncSession = Depends(get_session)) -> ProxyOut:
    url = proxy_pool.normalize_url(payload.url)
    if not url:
        raise HTTPException(400, "url is required")
    if not payload.label.strip():
        raise HTTPException(400, "label is required")
    obj = Proxy(label=payload.label.strip(), url=url, is_active=payload.is_active)
    session.add(obj)
    await session.commit()
    await session.refresh(obj)
    return _to_out(obj)


@router.post("/bulk", response_model=list[ProxyOut], status_code=201)
async def bulk_create(payload: ProxyBulkIn, session: AsyncSession = Depends(get_session)) -> list[ProxyOut]:
    """Paste many proxy URLs (one per line). Labels auto-generated as
    'prefix-1', 'prefix-2', etc., starting from the next unused number."""
    lines = [proxy_pool.normalize_url(u) for u in payload.urls if u and u.strip()]
    if not lines:
        raise HTTPException(400, "no proxy URLs provided")

    prefix = payload.label_prefix.strip() or "proxy"
    existing = await session.scalars(select(Proxy.label))
    existing_labels = set(existing)
    next_n = 1
    created: list[Proxy] = []
    for url in lines:
        while f"{prefix}-{next_n}" in existing_labels:
            next_n += 1
        label = f"{prefix}-{next_n}"
        existing_labels.add(label)
        obj = Proxy(label=label, url=url, is_active=True)
        session.add(obj)
        created.append(obj)
        next_n += 1
    await session.commit()
    for c in created:
        await session.refresh(c)
    return [_to_out(c) for c in created]


@router.patch("/{proxy_id}", response_model=ProxyOut)
async def update_proxy(
    proxy_id: UUID, payload: ProxyUpdate, session: AsyncSession = Depends(get_session)
) -> ProxyOut:
    obj = await session.get(Proxy, proxy_id)
    if not obj:
        raise HTTPException(404, "proxy not found")
    data = payload.model_dump(exclude_unset=True)
    if "url" in data:
        if data["url"]:
            data["url"] = proxy_pool.normalize_url(data["url"])
        else:
            data.pop("url")  # never overwrite with blank
    if "label" in data and not data["label"].strip():
        raise HTTPException(400, "label cannot be empty")
    for k, v in data.items():
        setattr(obj, k, v)
    await session.commit()
    await session.refresh(obj)
    return _to_out(obj)


@router.delete("/{proxy_id}", status_code=204)
async def delete_proxy(proxy_id: UUID, session: AsyncSession = Depends(get_session)) -> None:
    obj = await session.get(Proxy, proxy_id)
    if obj:
        await session.delete(obj)
        await session.commit()


@router.post("/repair")
async def repair_proxies() -> dict:
    """Re-parses every stored proxy URL, fixing rows that were imported under
    the pre-v0.7.1 parser (where ip:port:user:pass got stored as
    http://ip:port:user:pass instead of being decoded). Idempotent — safe to
    run any time. Also clears cooldown on rows it fixes so they're
    immediately re-testable."""
    return {"ok": True, **await proxy_pool.repair_all()}


@router.post("/{proxy_id}/reset", response_model=ProxyOut)
async def reset_proxy(proxy_id: UUID, session: AsyncSession = Depends(get_session)) -> ProxyOut:
    """Clear failure counts + cooldown so the proxy is immediately re-eligible."""
    obj = await session.get(Proxy, proxy_id)
    if not obj:
        raise HTTPException(404, "proxy not found")
    obj.failure_count = 0
    obj.last_failure_at = None
    obj.last_error = None
    await session.commit()
    await session.refresh(obj)
    return _to_out(obj)


# ---- test --------------------------------------------------------------

@router.post("/test", response_model=ProxyTestResult)
async def test_proxy(
    payload: ProxyTestRequest, session: AsyncSession = Depends(get_session)
) -> ProxyTestResult:
    if payload.proxy_id:
        obj = await session.get(Proxy, payload.proxy_id)
        if not obj:
            raise HTTPException(404, "proxy not found")
        url = obj.url
    elif payload.url:
        url = proxy_pool.normalize_url(payload.url)
    else:
        raise HTTPException(400, "supply either proxy_id or url")
    result = await proxy_pool.test_proxy_url(url)

    # If we tested a saved proxy, update its stats too.
    if payload.proxy_id:
        if result.get("ok"):
            await proxy_pool.mark_success(payload.proxy_id)
        else:
            await proxy_pool.mark_failure(payload.proxy_id, result.get("error", "test failed"))

    return ProxyTestResult(
        ok=result.get("ok", False),
        exit_ip=result.get("exit_ip"),
        elapsed_ms=result.get("elapsed_ms", 0),
        error=result.get("error"),
    )
