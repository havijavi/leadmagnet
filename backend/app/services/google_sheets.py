"""Google Sheets sync — replaces NocoDB as the spreadsheet view.

Auth model: a single Google service account, configured in .env. Each sheets
config row points at a spreadsheet ID + worksheet name. Sync is one-way
(LeadMagnet → Sheets) and idempotent — every run rewrites the sheet from the
current DB state, so re-running is safe and reordering rows in the sheet is
non-destructive (your edits get overwritten next sync).

Setup checklist for the user:
  1. Google Cloud Console → enable "Google Sheets API"
  2. IAM → Service Accounts → create → download JSON key
  3. Either inline the JSON in GOOGLE_SHEETS_CREDENTIALS_JSON, or mount the
     file and set GOOGLE_SHEETS_CREDENTIALS_FILE.
  4. Open your target sheet, click Share, add the service-account email
     (`client_email` field of the JSON) as an Editor.
  5. Copy the spreadsheet ID from the URL (the long bit between /d/ and /edit)
     and create a sheets_config row in the dashboard.
"""
from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import select

from app.config import settings
from app.db import session_scope
from app.models import EnrichmentRun, Lead, OutreachMessage, SheetsConfig

logger = logging.getLogger(__name__)


@dataclass
class SyncResult:
    rows: int
    status: str  # 'completed' | 'failed'
    error: Optional[str] = None


# -- credentials ------------------------------------------------------------

def _load_creds_info() -> Optional[dict]:
    """Return the parsed service-account JSON (or None if not configured)."""
    if settings.GOOGLE_SHEETS_CREDENTIALS_JSON:
        try:
            return json.loads(settings.GOOGLE_SHEETS_CREDENTIALS_JSON)
        except json.JSONDecodeError as e:
            logger.error("GOOGLE_SHEETS_CREDENTIALS_JSON is not valid JSON: %s", e)
            return None
    if settings.GOOGLE_SHEETS_CREDENTIALS_FILE:
        try:
            with open(settings.GOOGLE_SHEETS_CREDENTIALS_FILE) as fh:
                return json.load(fh)
        except (OSError, json.JSONDecodeError) as e:
            logger.error("Cannot read service-account JSON from %s: %s", settings.GOOGLE_SHEETS_CREDENTIALS_FILE, e)
            return None
    return None


def is_configured() -> bool:
    return _load_creds_info() is not None


def service_account_email() -> Optional[str]:
    info = _load_creds_info()
    return info.get("client_email") if info else None


def status() -> dict:
    info = _load_creds_info()
    if not info:
        return {
            "configured": False,
            "service_account_email": None,
            "setup_hint": (
                "Create a Google Cloud service account, download the JSON key, "
                "and set GOOGLE_SHEETS_CREDENTIALS_JSON (or _FILE) in .env. "
                "Then share each target sheet with the service-account email."
            ),
        }
    return {
        "configured": True,
        "service_account_email": info.get("client_email"),
        "setup_hint": (
            f"Share each Google Sheet with {info.get('client_email')} as Editor, "
            "then add a sync configuration with the spreadsheet ID."
        ),
    }


# -- sync entry points -----------------------------------------------------

async def sync_config(config_id: UUID) -> SyncResult:
    async with session_scope() as session:
        cfg = await session.get(SheetsConfig, config_id)
        if not cfg:
            return SyncResult(rows=0, status="failed", error="config not found")
        config_snapshot = _snapshot(cfg)

    rows, headers = await _build_rows(config_snapshot)

    result = await _write_to_sheet(
        spreadsheet_id=config_snapshot["spreadsheet_id"],
        worksheet_name=config_snapshot["worksheet_name"],
        headers=headers,
        rows=rows,
    )

    async with session_scope() as session:
        cfg = await session.get(SheetsConfig, config_id)
        if cfg:
            cfg.last_synced_at = datetime.now(timezone.utc)
            cfg.last_status = result.status
            cfg.last_error = result.error
            cfg.last_row_count = result.rows
    return result


async def sync_all_active() -> dict:
    async with session_scope() as session:
        rows = await session.scalars(select(SheetsConfig).where(SheetsConfig.is_active.is_(True)))
        ids = [r.id for r in rows]
    summary = {"configs": len(ids), "ok": 0, "failed": 0}
    for cid in ids:
        r = await sync_config(cid)
        summary["ok" if r.status == "completed" else "failed"] += 1
    return summary


def _snapshot(cfg: SheetsConfig) -> dict:
    return {
        "id": cfg.id,
        "spreadsheet_id": cfg.spreadsheet_id,
        "worksheet_name": cfg.worksheet_name,
        "sync_kind": cfg.sync_kind,
        "filters": dict(cfg.filters or {}),
    }


# -- row builders per sync_kind --------------------------------------------

LEAD_HEADERS = [
    "id", "name", "company", "email", "domain", "website", "linkedin_url",
    "role", "location", "fit_score", "urgency", "status", "enrichment_status",
    "tags", "research_summary", "project_summary", "source_url", "created_at",
    "updated_at",
]

OUTREACH_HEADERS = [
    "id", "lead_id", "subject", "body", "status", "direction",
    "sent_at", "error_message", "created_at",
]

ENRICHMENT_HEADERS = [
    "id", "lead_id", "status", "providers_tried", "providers_hit",
    "fields_filled", "error_message", "created_at",
]


async def _build_rows(snapshot: dict) -> tuple[list[list[Any]], list[str]]:
    kind = snapshot["sync_kind"]
    filters = snapshot["filters"]

    if kind == "leads":
        return await _build_lead_rows(filters), LEAD_HEADERS
    if kind == "outreach":
        return await _build_outreach_rows(filters), OUTREACH_HEADERS
    if kind == "enrichment_runs":
        return await _build_enrichment_rows(filters), ENRICHMENT_HEADERS
    raise ValueError(f"unknown sync_kind {kind!r}")


async def _build_lead_rows(filters: dict) -> list[list[Any]]:
    async with session_scope() as session:
        stmt = select(Lead)
        if "min_fit_score" in filters:
            stmt = stmt.where(Lead.fit_score >= int(filters["min_fit_score"]))
        if "status" in filters:
            stmt = stmt.where(Lead.status == filters["status"])
        if "enrichment_status" in filters:
            stmt = stmt.where(Lead.enrichment_status == filters["enrichment_status"])
        stmt = stmt.order_by(Lead.fit_score.desc(), Lead.created_at.desc())
        leads = list(await session.scalars(stmt))

    return [
        [
            str(l.id),
            l.name or "",
            l.company or "",
            l.email or "",
            l.domain or "",
            l.website or "",
            l.linkedin_url or "",
            l.role or "",
            l.location or "",
            l.fit_score or 0,
            l.urgency or "",
            l.status or "",
            l.enrichment_status or "",
            ", ".join(l.tags or []),
            (l.research_summary or "")[:1000],
            (l.project_summary or "")[:1000],
            l.source_url or "",
            l.created_at.isoformat() if l.created_at else "",
            l.updated_at.isoformat() if l.updated_at else "",
        ]
        for l in leads
    ]


async def _build_outreach_rows(filters: dict) -> list[list[Any]]:
    async with session_scope() as session:
        stmt = select(OutreachMessage).order_by(OutreachMessage.created_at.desc())
        if "status" in filters:
            stmt = stmt.where(OutreachMessage.status == filters["status"])
        msgs = list(await session.scalars(stmt))
    return [
        [
            str(m.id),
            str(m.lead_id),
            m.subject or "",
            (m.body or "")[:5000],
            m.status,
            m.direction,
            m.sent_at.isoformat() if m.sent_at else "",
            m.error_message or "",
            m.created_at.isoformat() if m.created_at else "",
        ]
        for m in msgs
    ]


async def _build_enrichment_rows(filters: dict) -> list[list[Any]]:
    async with session_scope() as session:
        stmt = select(EnrichmentRun).order_by(EnrichmentRun.created_at.desc())
        if "status" in filters:
            stmt = stmt.where(EnrichmentRun.status == filters["status"])
        runs = list(await session.scalars(stmt))
    return [
        [
            str(r.id),
            str(r.lead_id) if r.lead_id else "",
            r.status,
            ", ".join(r.providers_tried or []),
            ", ".join(r.providers_hit or []),
            ", ".join(r.fields_filled or []),
            r.error_message or "",
            r.created_at.isoformat() if r.created_at else "",
        ]
        for r in runs
    ]


# -- gspread write (sync, runs in executor) --------------------------------

async def _write_to_sheet(
    *,
    spreadsheet_id: str,
    worksheet_name: str,
    headers: list[str],
    rows: list[list[Any]],
) -> SyncResult:
    info = _load_creds_info()
    if not info:
        return SyncResult(rows=0, status="failed", error="Google credentials not configured")

    def _do_write() -> SyncResult:
        try:
            import gspread
            from google.oauth2.service_account import Credentials
        except ImportError as e:
            return SyncResult(rows=0, status="failed", error=f"missing dep: {e}")

        try:
            creds = Credentials.from_service_account_info(
                info,
                scopes=["https://www.googleapis.com/auth/spreadsheets"],
            )
            client = gspread.authorize(creds)
            sh = client.open_by_key(spreadsheet_id)
            try:
                ws = sh.worksheet(worksheet_name)
            except gspread.WorksheetNotFound:
                ws = sh.add_worksheet(worksheet_name, rows=max(len(rows) + 100, 100), cols=max(len(headers), 20))

            ws.clear()
            data = [headers] + rows
            if data:
                ws.update(values=data, range_name="A1")
            return SyncResult(rows=len(rows), status="completed")
        except Exception as e:
            logger.exception("Sheet write failed")
            return SyncResult(rows=0, status="failed", error=str(e))

    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _do_write)
