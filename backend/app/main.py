import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from app.api import (
    auth,
    campaigns,
    crm,
    discovery,
    enrichment,
    health,
    imports,
    leads,
    llm_configs,
    research,
    schedules,
    services,
    sheets,
    sources,
    stats,
    users,
)
from app.config import settings
from app.db import Base, engine, session_scope
from app.models import LLMConfig
from app.services import scheduler

logger = logging.getLogger(__name__)


async def _auto_migrate() -> None:
    """Create any tables added in newer versions of the codebase. Safe to run
    on every boot — Base.metadata.create_all skips tables that already exist
    with the right name. Existing data is untouched."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def _auto_import_env_llm() -> None:
    """If there are zero llm_configs rows AND the user has an LLM_API_KEY in
    .env, import that as an active DB config so the dashboard reflects what's
    actually being used. One-shot migration helper for existing deployments."""
    if not settings.LLM_API_KEY:
        return
    async with session_scope() as session:
        existing = await session.scalar(select(LLMConfig).limit(1))
        if existing:
            return
        session.add(
            LLMConfig(
                name=".env import",
                provider_kind="openai_compat",
                base_url=settings.LLM_BASE_URL,
                model=settings.LLM_MODEL,
                api_key=settings.LLM_API_KEY,
                is_active=True,
                extra={"imported_from": "env"},
            )
        )
        logger.info("Auto-imported LLM_API_KEY from .env as an active llm_configs row")


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        await _auto_migrate()
    except Exception as e:
        logger.exception("auto-migration failed: %s", e)
    try:
        await _auto_import_env_llm()
    except Exception as e:
        logger.exception("env-to-DB LLM import failed: %s", e)

    await scheduler.start()
    try:
        yield
    finally:
        await scheduler.stop()


app = FastAPI(
    title="LeadMagnet API",
    version="0.5.0",
    description=(
        "Self-hosted Apify + Clay replacement. Per-user accounts with three roles "
        "(admin / member / viewer); LLM providers (OpenAI, Anthropic, DeepSeek, "
        "Qwen, Gemini, Ollama, custom) managed from the dashboard. .env ADMIN_TOKEN "
        "remains a break-glass superuser."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(users.router, prefix="/api/users", tags=["users"])
app.include_router(stats.router, prefix="/api/stats", tags=["stats"])
app.include_router(services.router, prefix="/api/services", tags=["services"])
app.include_router(sources.router, prefix="/api/sources", tags=["sources"])
app.include_router(discovery.router, prefix="/api/discovery", tags=["discovery"])
app.include_router(leads.router, prefix="/api/leads", tags=["leads"])
app.include_router(campaigns.router, prefix="/api/campaigns", tags=["campaigns"])
app.include_router(enrichment.router, prefix="/api/enrichment", tags=["enrichment"])
app.include_router(imports.router, prefix="/api/import", tags=["import"])
app.include_router(research.router, prefix="/api/research", tags=["research"])
app.include_router(schedules.router, prefix="/api/schedules", tags=["schedules"])
app.include_router(crm.router, prefix="/api/crm", tags=["crm"])
app.include_router(sheets.router, prefix="/api/sheets", tags=["sheets"])
app.include_router(llm_configs.router, prefix="/api/llm-configs", tags=["llm-configs"])
