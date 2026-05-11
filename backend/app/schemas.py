from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class _Base(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------- Auth / users ----------

class UserOut(_Base):
    id: UUID
    email: str
    name: Optional[str]
    role: str
    is_active: bool
    last_login_at: Optional[datetime]
    created_at: datetime


class LoginRequest(BaseModel):
    email: str
    password: str


class LoginResponse(BaseModel):
    token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserOut


class SetupRequest(BaseModel):
    email: str
    password: str
    name: Optional[str] = None


class UserCreate(BaseModel):
    email: str
    password: str
    name: Optional[str] = None
    role: str = "member"  # admin | member | viewer
    is_active: bool = True


class UserUpdate(BaseModel):
    name: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None


class UserResetPassword(BaseModel):
    new_password: str


class PasswordChange(BaseModel):
    old_password: str
    new_password: str


class NeedsSetupOut(BaseModel):
    needs_setup: bool


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


# ---------- Discovery ----------

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


# ---------- Target lists ----------

class TargetListOut(_Base):
    id: UUID
    name: str
    description: Optional[str]
    row_count: int
    created_at: datetime


# ---------- Leads ----------

class LeadOut(_Base):
    id: UUID
    source_id: Optional[UUID]
    matched_service_id: Optional[UUID]
    target_list_id: Optional[UUID]

    name: Optional[str]
    company: Optional[str]
    email: Optional[str]
    website: Optional[str]
    location: Optional[str]
    role: Optional[str]
    linkedin_url: Optional[str]
    domain: Optional[str]

    project_summary: Optional[str]
    raw_excerpt: Optional[str]
    source_url: Optional[str]

    fit_score: int
    urgency: str
    qualification_notes: Optional[str]

    enrichment_status: str
    enrichment_data: dict
    enriched_at: Optional[datetime]

    research_summary: Optional[str]
    research_data: dict
    researched_at: Optional[datetime]

    status: str
    tags: list[str]
    created_at: datetime
    updated_at: datetime


class LeadUpdate(BaseModel):
    status: Optional[str] = None
    fit_score: Optional[int] = None
    qualification_notes: Optional[str] = None
    name: Optional[str] = None
    company: Optional[str] = None
    email: Optional[str] = None
    website: Optional[str] = None
    domain: Optional[str] = None
    linkedin_url: Optional[str] = None
    role: Optional[str] = None
    tags: Optional[list[str]] = None


class LeadCreate(BaseModel):
    name: Optional[str] = None
    company: Optional[str] = None
    email: Optional[str] = None
    website: Optional[str] = None
    domain: Optional[str] = None
    linkedin_url: Optional[str] = None
    role: Optional[str] = None
    location: Optional[str] = None
    target_list_id: Optional[UUID] = None
    tags: list[str] = Field(default_factory=list)


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
    status: Optional[str] = None


# ---------- Enrichment ----------

class EnrichmentRunOut(_Base):
    id: UUID
    lead_id: Optional[UUID]
    providers_tried: list[str]
    providers_hit: list[str]
    fields_filled: list[str]
    status: str
    error_message: Optional[str]
    raw_results: dict
    created_at: datetime


class EnrichmentRequest(BaseModel):
    lead_id: Optional[UUID] = None
    # Or supply identifiers directly for an ad-hoc enrichment:
    name: Optional[str] = None
    company: Optional[str] = None
    domain: Optional[str] = None
    email: Optional[str] = None
    linkedin_url: Optional[str] = None
    providers: Optional[list[str]] = None  # subset; default = all configured


class EnrichmentBatchRequest(BaseModel):
    lead_ids: Optional[list[UUID]] = None
    target_list_id: Optional[UUID] = None
    only_pending: bool = True
    providers: Optional[list[str]] = None


class ResearchRequest(BaseModel):
    lead_id: UUID
    deep: bool = False  # if true, also crawl the company website


# ---------- Schedules ----------

class ScheduledJobIn(BaseModel):
    name: str
    kind: str  # 'discovery' | 'enrichment_pending' | 'crm_sync'
    cron: str
    payload: dict[str, Any] = Field(default_factory=dict)
    is_active: bool = True


class ScheduledJobOut(_Base):
    id: UUID
    name: str
    kind: str
    cron: str
    payload: dict[str, Any]
    is_active: bool
    last_run_at: Optional[datetime]
    last_status: Optional[str]
    last_error: Optional[str]
    created_at: datetime


# ---------- CRM webhooks ----------

class CrmWebhookIn(BaseModel):
    name: str
    url: str
    secret: Optional[str] = None
    events: list[str] = Field(default_factory=lambda: ["lead.created", "lead.contacted", "lead.replied", "lead.won"])
    headers: dict[str, str] = Field(default_factory=dict)
    body_template: Optional[str] = None
    is_active: bool = True


class CrmWebhookOut(_Base):
    id: UUID
    name: str
    url: str
    events: list[str]
    headers: dict[str, str]
    body_template: Optional[str]
    is_active: bool
    last_fired_at: Optional[datetime]
    last_status_code: Optional[int]
    last_error: Optional[str]
    created_at: datetime


# ---------- LLM configurations ----------

class LLMConfigIn(BaseModel):
    name: str
    provider_kind: str  # 'openai_compat' | 'anthropic'
    base_url: str
    model: str
    api_key: str
    extra: dict[str, Any] = Field(default_factory=dict)


class LLMConfigUpdate(BaseModel):
    name: Optional[str] = None
    provider_kind: Optional[str] = None
    base_url: Optional[str] = None
    model: Optional[str] = None
    api_key: Optional[str] = None
    extra: Optional[dict[str, Any]] = None


class LLMConfigOut(_Base):
    id: UUID
    name: str
    provider_kind: str
    base_url: str
    model: str
    api_key_preview: str  # masked
    is_active: bool
    extra: dict[str, Any]
    created_at: datetime


class LLMTestRequest(BaseModel):
    # Either pass an existing config id…
    config_id: Optional[UUID] = None
    # …or supply an ad-hoc config to test before saving.
    provider_kind: Optional[str] = None
    base_url: Optional[str] = None
    model: Optional[str] = None
    api_key: Optional[str] = None


class LLMTestResult(BaseModel):
    ok: bool
    elapsed_ms: int
    sample_output: Optional[str] = None
    error: Optional[str] = None


class LLMActiveStatus(BaseModel):
    configured: bool
    source: str  # 'db' | 'env' | 'none'
    provider_kind: Optional[str] = None
    base_url: Optional[str] = None
    model: Optional[str] = None
    config_id: Optional[UUID] = None
    config_name: Optional[str] = None


# ---------- Google Sheets sync ----------

class SheetsConfigIn(BaseModel):
    name: str
    spreadsheet_id: str
    spreadsheet_url: Optional[str] = None
    worksheet_name: str = "Leads"
    sync_kind: str = "leads"  # leads | outreach | enrichment_runs
    filters: dict[str, Any] = Field(default_factory=dict)
    is_active: bool = True


class SheetsConfigOut(_Base):
    id: UUID
    name: str
    spreadsheet_id: str
    spreadsheet_url: Optional[str]
    worksheet_name: str
    sync_kind: str
    filters: dict[str, Any]
    is_active: bool
    last_synced_at: Optional[datetime]
    last_status: Optional[str]
    last_error: Optional[str]
    last_row_count: Optional[int]
    created_at: datetime


class SheetsStatusOut(BaseModel):
    configured: bool
    service_account_email: Optional[str]
    setup_hint: str


# ---------- Stats ----------

class StatsOut(BaseModel):
    leads_total: int
    leads_new: int
    leads_contacted: int
    leads_replied: int
    high_fit_count: int
    discovery_runs_24h: int
    leads_enriched: int
    leads_pending_enrichment: int
