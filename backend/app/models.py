import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import ARRAY, Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    name: Mapped[Optional[str]] = mapped_column(Text)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(Text, default="member")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ServiceOffering(Base):
    __tablename__ = "service_offerings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    keywords: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    target_industries: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    min_budget_usd: Mapped[Optional[int]] = mapped_column(Integer)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class LeadSource(Base):
    __tablename__ = "lead_sources"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    config: Mapped[dict] = mapped_column(JSONB, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    schedule_cron: Mapped[Optional[str]] = mapped_column(Text)
    last_run_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DiscoveryRun(Base):
    __tablename__ = "discovery_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("lead_sources.id", ondelete="SET NULL"))
    status: Mapped[str] = mapped_column(Text, default="queued")
    pages_crawled: Mapped[int] = mapped_column(Integer, default=0)
    leads_found: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class TargetList(Base):
    __tablename__ = "target_lists"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    row_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Lead(Base):
    __tablename__ = "leads"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("lead_sources.id", ondelete="SET NULL"))
    discovery_run_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("discovery_runs.id", ondelete="SET NULL"))
    matched_service_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("service_offerings.id", ondelete="SET NULL"))
    target_list_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("target_lists.id", ondelete="SET NULL"))

    name: Mapped[Optional[str]] = mapped_column(Text)
    company: Mapped[Optional[str]] = mapped_column(Text)
    email: Mapped[Optional[str]] = mapped_column(Text)
    website: Mapped[Optional[str]] = mapped_column(Text)
    location: Mapped[Optional[str]] = mapped_column(Text)
    role: Mapped[Optional[str]] = mapped_column(Text)
    linkedin_url: Mapped[Optional[str]] = mapped_column(Text)
    domain: Mapped[Optional[str]] = mapped_column(Text)

    project_summary: Mapped[Optional[str]] = mapped_column(Text)
    raw_excerpt: Mapped[Optional[str]] = mapped_column(Text)
    source_url: Mapped[Optional[str]] = mapped_column(Text)

    fit_score: Mapped[int] = mapped_column(Integer, default=0)
    urgency: Mapped[str] = mapped_column(Text, default="medium")
    qualification_notes: Mapped[Optional[str]] = mapped_column(Text)

    enrichment_status: Mapped[str] = mapped_column(Text, default="pending")
    enrichment_data: Mapped[dict] = mapped_column(JSONB, default=dict)
    enriched_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    research_summary: Mapped[Optional[str]] = mapped_column(Text)
    research_data: Mapped[dict] = mapped_column(JSONB, default=dict)
    researched_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    status: Mapped[str] = mapped_column(Text, default="new")
    fingerprint: Mapped[Optional[str]] = mapped_column(Text, unique=True)
    raw_data: Mapped[dict] = mapped_column(JSONB, default=dict)
    tags: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    messages: Mapped[list["OutreachMessage"]] = relationship(back_populates="lead", cascade="all, delete-orphan")


class OutreachMessage(Base):
    __tablename__ = "outreach_messages"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lead_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("leads.id", ondelete="CASCADE"), nullable=False)
    direction: Mapped[str] = mapped_column(Text, default="outbound")
    channel: Mapped[str] = mapped_column(Text, default="email")
    subject: Mapped[Optional[str]] = mapped_column(Text)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, default="draft")
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    scheduled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    lead: Mapped["Lead"] = relationship(back_populates="messages")


class EnrichmentRun(Base):
    __tablename__ = "enrichment_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lead_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("leads.id", ondelete="CASCADE"))
    providers_tried: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    providers_hit: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    fields_filled: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    status: Mapped[str] = mapped_column(Text, default="completed")
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    raw_results: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ScheduledJob(Base):
    __tablename__ = "scheduled_jobs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    cron: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_run_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    last_status: Mapped[Optional[str]] = mapped_column(Text)
    last_error: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Proxy(Base):
    __tablename__ = "proxies"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    label: Mapped[str] = mapped_column(Text, nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_used_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    last_failure_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[Optional[str]] = mapped_column(Text)
    success_count: Mapped[int] = mapped_column(Integer, default=0)
    failure_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ChatProject(Base):
    __tablename__ = "chat_projects"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    system_prompt: Mapped[Optional[str]] = mapped_column(Text)
    memory: Mapped[Optional[str]] = mapped_column(Text)
    is_pinned: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    messages: Mapped[list["ChatMessage"]] = relationship(
        back_populates="project", cascade="all, delete-orphan", order_by="ChatMessage.created_at"
    )


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("chat_projects.id", ondelete="CASCADE"), nullable=False)
    role: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[Optional[str]] = mapped_column(Text)
    tool_calls: Mapped[Optional[dict]] = mapped_column(JSONB)
    tool_call_id: Mapped[Optional[str]] = mapped_column(Text)
    tool_name: Mapped[Optional[str]] = mapped_column(Text)
    error: Mapped[Optional[str]] = mapped_column(Text)
    # Provider-specific fields we must echo back on subsequent turns:
    #   DeepSeek reasoner -> {"reasoning_content": "..."}
    #   Anthropic thinking -> {"blocks": [...]} (preserves signed thinking blocks)
    provider_extra: Mapped[Optional[dict]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    project: Mapped["ChatProject"] = relationship(back_populates="messages")


class LLMConfig(Base):
    __tablename__ = "llm_configs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    provider_kind: Mapped[str] = mapped_column(Text, nullable=False)  # 'openai_compat' | 'anthropic'
    base_url: Mapped[str] = mapped_column(Text, nullable=False)
    model: Mapped[str] = mapped_column(Text, nullable=False)
    api_key: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)
    extra: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SheetsConfig(Base):
    __tablename__ = "sheets_configs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    spreadsheet_id: Mapped[str] = mapped_column(Text, nullable=False)
    spreadsheet_url: Mapped[Optional[str]] = mapped_column(Text)
    worksheet_name: Mapped[str] = mapped_column(Text, default="Leads")
    sync_kind: Mapped[str] = mapped_column(Text, default="leads")
    filters: Mapped[dict] = mapped_column(JSONB, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    last_status: Mapped[Optional[str]] = mapped_column(Text)
    last_error: Mapped[Optional[str]] = mapped_column(Text)
    last_row_count: Mapped[Optional[int]] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CrmWebhook(Base):
    __tablename__ = "crm_webhooks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    secret: Mapped[Optional[str]] = mapped_column(Text)
    events: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    headers: Mapped[dict] = mapped_column(JSONB, default=dict)
    body_template: Mapped[Optional[str]] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_fired_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    last_status_code: Mapped[Optional[int]] = mapped_column(Integer)
    last_error: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
