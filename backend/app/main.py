from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import campaigns, discovery, health, leads, services, sources, stats


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Schema is created by db/init.sql when Postgres boots; nothing to do here yet.
    yield


app = FastAPI(
    title="LeadMagnet API",
    version="0.1.0",
    description="Open-source Apify-replacement plus a built-in lead generation, qualification, and outreach pipeline.",
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
app.include_router(stats.router, prefix="/api/stats", tags=["stats"])
app.include_router(services.router, prefix="/api/services", tags=["services"])
app.include_router(sources.router, prefix="/api/sources", tags=["sources"])
app.include_router(discovery.router, prefix="/api/discovery", tags=["discovery"])
app.include_router(leads.router, prefix="/api/leads", tags=["leads"])
app.include_router(campaigns.router, prefix="/api/campaigns", tags=["campaigns"])
