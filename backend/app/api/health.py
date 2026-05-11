from fastapi import APIRouter

from app.config import settings
from app.services import google_sheets
from app.services.enrichment import available_providers
from app.services.llm import get_active_status

router = APIRouter()


@router.get("/health")
async def health() -> dict:
    sheets_status = google_sheets.status()
    llm_status = await get_active_status()
    return {
        "status": "ok",
        "version": "0.5.0",
        # LLM status reflects whichever active config the DB has (or .env fallback).
        "llm_configured": llm_status["configured"],
        "llm_source": llm_status["source"],
        "llm_provider_kind": llm_status["provider_kind"],
        "llm_base_url": llm_status["base_url"],
        "llm_model": llm_status["model"],
        "llm_config_name": llm_status["config_name"],
        "llm_mock_mode": not llm_status["configured"],
        "smtp_configured": bool(settings.SMTP_HOST and settings.SMTP_FROM),
        "telegram_configured": bool(settings.TELEGRAM_BOT_TOKEN and settings.TELEGRAM_CHAT_ID),
        "webhook_configured": bool(settings.NOTIFY_WEBHOOK_URL),
        "enrichment_providers": available_providers(),
        "scheduler_enabled": settings.SCHEDULER_ENABLED,
        "google_sheets_configured": sheets_status["configured"],
        "google_sheets_service_account": sheets_status["service_account_email"],
    }
