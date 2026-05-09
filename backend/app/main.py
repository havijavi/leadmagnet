from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import (
    auth,
    campaigns,
    crm,
    discovery,
    enrichment,
    health,
    imports,
    leads,
    research,
    schedules,
    services,
    sheets,
    sources,
    stats,
    users,
)
from app.services import scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    await scheduler.start()
    try:
        yield
    finally:
        await scheduler.stop()


app = FastAPI(
    title="LeadMagnet API",
    version="0.4.1",
    description=(
        "Self-hosted Apify + Clay replacement. Per-user accounts with three roles "
        "(admin / member / viewer); .env ADMIN_TOKEN remains a break-glass superuser."
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
