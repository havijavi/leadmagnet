from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_admin
from app.db import get_session
from app.models import SheetsConfig
from app.schemas import SheetsConfigIn, SheetsConfigOut, SheetsStatusOut
from app.services import google_sheets

router = APIRouter(dependencies=[Depends(require_admin)])


VALID_KINDS = {"leads", "outreach", "enrichment_runs"}


@router.get("/status", response_model=SheetsStatusOut)
async def status() -> SheetsStatusOut:
    return SheetsStatusOut(**google_sheets.status())


@router.get("/kinds")
async def kinds() -> dict:
    return {"kinds": sorted(VALID_KINDS)}


@router.get("", response_model=list[SheetsConfigOut])
async def list_configs(session: AsyncSession = Depends(get_session)) -> list[SheetsConfigOut]:
    rows = await session.scalars(select(SheetsConfig).order_by(SheetsConfig.created_at.desc()))
    return [SheetsConfigOut.model_validate(r) for r in rows]


@router.post("", response_model=SheetsConfigOut, status_code=201)
async def create_config(payload: SheetsConfigIn, session: AsyncSession = Depends(get_session)) -> SheetsConfigOut:
    if payload.sync_kind not in VALID_KINDS:
        raise HTTPException(400, f"invalid sync_kind, valid: {sorted(VALID_KINDS)}")
    data = payload.model_dump()
    sid = (data.get("spreadsheet_id") or "").strip()
    if "docs.google.com" in sid and "/d/" in sid:
        # Accept full URL pasted in spreadsheet_id field — extract the id.
        try:
            sid = sid.split("/d/")[1].split("/")[0]
        except IndexError:
            pass
    data["spreadsheet_id"] = sid
    if not data.get("spreadsheet_url"):
        data["spreadsheet_url"] = f"https://docs.google.com/spreadsheets/d/{sid}/edit"
    obj = SheetsConfig(**data)
    session.add(obj)
    await session.commit()
    await session.refresh(obj)
    return SheetsConfigOut.model_validate(obj)


@router.put("/{config_id}", response_model=SheetsConfigOut)
async def update_config(config_id: UUID, payload: SheetsConfigIn, session: AsyncSession = Depends(get_session)) -> SheetsConfigOut:
    obj = await session.get(SheetsConfig, config_id)
    if not obj:
        raise HTTPException(404, "config not found")
    for k, v in payload.model_dump().items():
        setattr(obj, k, v)
    await session.commit()
    await session.refresh(obj)
    return SheetsConfigOut.model_validate(obj)


@router.delete("/{config_id}", status_code=204)
async def delete_config(config_id: UUID, session: AsyncSession = Depends(get_session)) -> None:
    obj = await session.get(SheetsConfig, config_id)
    if obj:
        await session.delete(obj)
        await session.commit()


@router.post("/{config_id}/sync")
async def sync_now(config_id: UUID, bg: BackgroundTasks) -> dict:
    if not google_sheets.is_configured():
        raise HTTPException(400, "Google Sheets credentials not set in .env")
    bg.add_task(google_sheets.sync_config, config_id)
    return {"queued": True, "config_id": str(config_id)}


@router.post("/sync-all")
async def sync_all(bg: BackgroundTasks) -> dict:
    if not google_sheets.is_configured():
        raise HTTPException(400, "Google Sheets credentials not set in .env")
    bg.add_task(google_sheets.sync_all_active)
    return {"queued": True}
