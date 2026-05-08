from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class _Base(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------- Service offerings ----------

class ServiceOfferingIn(BaseModel):
    name: str
    description: Optional[str] = None
    keywords: list[str] = Field(default_factory=list)
    target_industries: list[str] = Field(default_factory=list)
    min_budget_usd: Optional[int] = None
    is_active: bool = True


class ServiceOfferingOut(_Base):
    id: UUID
    name: str
    description: Optional[str]
    keywords: list[str]
    target_industries: list[str]
    min_budget_usd: Optional[int]
    is_active: bool
    created_at: datetime


# ---------- Lead sources ----------

class LeadSourceIn(BaseModel):
    kind: str
    name: str
    config: dict[str, Any] = Field(default_factory=dict)
    is_active: bool = True
    schedule_cron: Optional[str] = None


class LeadSourceOut(_Base):
    id: UUID
    kind: str
    name: str
    config: dict[str, Any]
    is_active: bool
    schedule_cron: Optional[str]
    last_run_at: Optional[datetime]
    created_at: datetime


# ---------- Discovery runs ----------

class DiscoveryRunOut(_Base):
    id: UUID
    source_id: Optional[UUID]
    status: str
    pages_crawled: int
    leads_found: int
    error_message: Optional[str]
    started_at: Optional[datetime]
    finished_at: Optional[datetime]
    created_at: datetime


class DiscoveryTrigger(BaseModel):
    source_ids: Optional[list[UUID]] = None
    service_id: Optional[UUID] = None
    extra_urls: list[str] = Field(default_factory=list)


# ---------- Leads ----------

class LeadOut(_Base):
    id: UUID
    source_id: Optional[UUID]
    matched_service_id: Optional[UUID]
    name: Optional[str]
    company: Optional[str]
    email: Optional[str]
    website: Optional[str]
    location: Optional[str]
    role: Optional[str]
    project_summary: Optional[str]
    raw_excerpt: Optional[str]
    source_url: Optional[str]
    fit_score: int
    urgency: str
    qualification_notes: Optional[str]
    status: str
    created_at: datetime
    updated_at: datetime


class LeadUpdate(BaseModel):
    status: Optional[str] = None
    fit_score: Optional[int] = None
    qualification_notes: Optional[str] = None
    name: Optional[str] = None
    email: Optional[str] = None


# ---------- Outreach ----------

class OutreachDraftIn(BaseModel):
    lead_id: UUID
    tone: str = "friendly"
    extra_context: Optional[str] = None


class OutreachMessageOut(_Base):
    id: UUID
    lead_id: UUID
    direction: str
    channel: str
    subject: Optional[str]
    body: str
    status: str
    error_message: Optional[str]
    sent_at: Optional[datetime]
    created_at: datetime


class OutreachUpdate(BaseModel):
    subject: Optional[str] = None
    body: Optional[str] = None
    status: Optional[str] = None  # 'approved' to mark for send


class StatsOut(BaseModel):
    leads_total: int
    leads_new: int
    leads_contacted: int
    leads_replied: int
    high_fit_count: int
    discovery_runs_24h: int
