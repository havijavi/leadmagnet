from fastapi import APIRouter

from app.config import settings
from app.services import google_sheets
from app.services.enrichment import available_providers
from app.services.llm import llm

router = APIRouter()


@router.get("/health")
async def health() -> dict:
    sheets_status = google_sheets.status()
    return {
        "status": "ok",
        "version": "0.3.0",
        "llm_provider": settings.LLM_PROVIDER,
        "llm_model": settings.LLM_MODEL,
        "llm_mock_mode": llm.is_mock,
        "smtp_configured": bool(settings.SMTP_HOST and settings.SMTP_FROM),
        "telegram_configured": bool(settings.TELEGRAM_BOT_TOKEN and settings.TELEGRAM_CHAT_ID),
        "webhook_configured": bool(settings.NOTIFY_WEBHOOK_URL),
        "enrichment_providers": available_providers(),
        "scheduler_enabled": settings.SCHEDULER_ENABLED,
        "google_sheets_configured": sheets_status["configured"],
        "google_sheets_service_account": sheets_status["service_account_email"],
    }
