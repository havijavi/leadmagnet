import time
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_admin
from app.db import get_session
from app.models import LLMConfig
from app.schemas import (
    LLMActiveStatus,
    LLMConfigIn,
    LLMConfigOut,
    LLMConfigUpdate,
    LLMTestRequest,
    LLMTestResult,
)
from app.services.llm import (
    PROVIDER_KINDS,
    PROVIDER_PRESETS,
    LLMClient,
    get_active_status,
    mask_key,
)

router = APIRouter(dependencies=[Depends(require_admin)])


def _to_out(c: LLMConfig) -> LLMConfigOut:
    return LLMConfigOut(
        id=c.id,
        name=c.name,
        provider_kind=c.provider_kind,
        base_url=c.base_url,
        model=c.model,
        api_key_preview=mask_key(c.api_key or ""),
        is_active=c.is_active,
        extra=c.extra or {},
        created_at=c.created_at,
    )


# ---- presets / status (no DB) -------------------------------------------

@router.get("/presets")
async def list_presets() -> dict:
    """The list shown in the dashboard's 'Provider' dropdown when adding a config."""
    return {"presets": PROVIDER_PRESETS, "provider_kinds": sorted(PROVIDER_KINDS)}


@router.get("/active", response_model=LLMActiveStatus)
async def active() -> LLMActiveStatus:
    """Returns which LLM config (if any) is currently in use."""
    return LLMActiveStatus(**await get_active_status())


# ---- CRUD ---------------------------------------------------------------

@router.get("", response_model=list[LLMConfigOut])
async def list_configs(session: AsyncSession = Depends(get_session)) -> list[LLMConfigOut]:
    rows = await session.scalars(select(LLMConfig).order_by(LLMConfig.created_at.desc()))
    return [_to_out(r) for r in rows]


@router.post("", response_model=LLMConfigOut, status_code=201)
async def create_config(payload: LLMConfigIn, session: AsyncSession = Depends(get_session)) -> LLMConfigOut:
    if payload.provider_kind not in PROVIDER_KINDS:
        raise HTTPException(400, f"provider_kind must be one of {sorted(PROVIDER_KINDS)}")
    if not payload.api_key.strip():
        raise HTTPException(400, "api_key is required")
    if not payload.model.strip():
        raise HTTPException(400, "model is required")
    if not payload.base_url.strip():
        raise HTTPException(400, "base_url is required")

    obj = LLMConfig(
        name=payload.name.strip() or payload.model,
        provider_kind=payload.provider_kind,
        base_url=payload.base_url.strip(),
        model=payload.model.strip(),
        api_key=payload.api_key.strip(),
        is_active=False,  # explicit activate step
        extra=payload.extra or {},
    )
    session.add(obj)
    await session.commit()
    await session.refresh(obj)
    return _to_out(obj)


@router.patch("/{config_id}", response_model=LLMConfigOut)
async def update_config(
    config_id: UUID,
    payload: LLMConfigUpdate,
    session: AsyncSession = Depends(get_session),
) -> LLMConfigOut:
    obj = await session.get(LLMConfig, config_id)
    if not obj:
        raise HTTPException(404, "config not found")

    data = payload.model_dump(exclude_unset=True)
    if "provider_kind" in data and data["provider_kind"] not in PROVIDER_KINDS:
        raise HTTPException(400, f"provider_kind must be one of {sorted(PROVIDER_KINDS)}")
    # Empty api_key in a PATCH means "leave as-is" — never overwrite with blank.
    if "api_key" in data and not (data["api_key"] or "").strip():
        data.pop("api_key")

    for k, v in data.items():
        setattr(obj, k, v)
    await session.commit()
    await session.refresh(obj)
    return _to_out(obj)


@router.delete("/{config_id}", status_code=204)
async def delete_config(config_id: UUID, session: AsyncSession = Depends(get_session)) -> None:
    obj = await session.get(LLMConfig, config_id)
    if obj:
        await session.delete(obj)
        await session.commit()


# ---- activate / test ----------------------------------------------------

@router.post("/{config_id}/activate", response_model=LLMConfigOut)
async def activate(config_id: UUID, session: AsyncSession = Depends(get_session)) -> LLMConfigOut:
    """Marks one config as the active LLM; deactivates every other row in a single transaction."""
    obj = await session.get(LLMConfig, config_id)
    if not obj:
        raise HTTPException(404, "config not found")
    await session.execute(update(LLMConfig).values(is_active=False))
    obj.is_active = True
    await session.commit()
    await session.refresh(obj)
    return _to_out(obj)


@router.post("/{config_id}/deactivate", response_model=LLMConfigOut)
async def deactivate(config_id: UUID, session: AsyncSession = Depends(get_session)) -> LLMConfigOut:
    obj = await session.get(LLMConfig, config_id)
    if not obj:
        raise HTTPException(404, "config not found")
    obj.is_active = False
    await session.commit()
    await session.refresh(obj)
    return _to_out(obj)


@router.post("/test", response_model=LLMTestResult)
async def test_llm(payload: LLMTestRequest, session: AsyncSession = Depends(get_session)) -> LLMTestResult:
    """Smoke-test either a saved config (by id) or an ad-hoc one (provider_kind/base_url/model/api_key).

    Calls the model with a trivial prompt and reports latency + sample output.
    Useful as a 'before saving' validation in the dashboard.
    """
    if payload.config_id:
        cfg = await session.get(LLMConfig, payload.config_id)
        if not cfg:
            raise HTTPException(404, "config not found")
        client = LLMClient(
            api_key=cfg.api_key,
            base_url=cfg.base_url,
            model=cfg.model,
            provider_kind=cfg.provider_kind,
        )
    else:
        if not all([payload.provider_kind, payload.base_url, payload.model, payload.api_key]):
            raise HTTPException(400, "provide either config_id, or all of provider_kind/base_url/model/api_key")
        if payload.provider_kind not in PROVIDER_KINDS:
            raise HTTPException(400, f"provider_kind must be one of {sorted(PROVIDER_KINDS)}")
        client = LLMClient(
            api_key=payload.api_key,
            base_url=payload.base_url,
            model=payload.model,
            provider_kind=payload.provider_kind,
        )

    start = time.perf_counter()
    try:
        out = await client.complete(
            "Respond with the single word: pong",
            system="You are a connectivity test. Reply with one word only.",
            temperature=0,
            max_tokens=32,
        )
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        return LLMTestResult(
            ok=True,
            elapsed_ms=elapsed_ms,
            sample_output=str(out)[:200] if out else None,
        )
    except Exception as e:
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        return LLMTestResult(ok=False, elapsed_ms=elapsed_ms, error=str(e)[:500])
