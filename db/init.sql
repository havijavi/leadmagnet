-- LeadMagnet database schema
-- Loaded once on first Postgres boot via docker-entrypoint-initdb.d.

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ----------------------------------------------------------------------------
-- Users with per-account login + role-based access.
-- Roles:
--   admin  - everything (services, sources, schedules, sheets, crm, users)
--   member - daily-use pipeline (discovery, enrichment, leads, outreach)
--   viewer - read-only on leads / campaigns / dashboard
-- ADMIN_TOKEN in .env still works as a break-glass superuser bearer token.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email TEXT UNIQUE NOT NULL,
    name TEXT,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'member',
    is_active BOOLEAN DEFAULT TRUE,
    last_login_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);

-- ----------------------------------------------------------------------------
-- Service offerings: what the user sells.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS service_offerings (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT NOT NULL,
    description TEXT,
    keywords TEXT[] DEFAULT '{}',
    target_industries TEXT[] DEFAULT '{}',
    min_budget_usd INTEGER,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ----------------------------------------------------------------------------
-- Lead sources: where to discover leads (HN, Reddit, custom URLs, search).
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS lead_sources (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    kind TEXT NOT NULL,
    name TEXT NOT NULL,
    config JSONB DEFAULT '{}'::jsonb,
    is_active BOOLEAN DEFAULT TRUE,
    schedule_cron TEXT,
    last_run_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ----------------------------------------------------------------------------
-- Discovery runs: one row per source-fetch job.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS discovery_runs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source_id UUID REFERENCES lead_sources(id) ON DELETE SET NULL,
    status TEXT NOT NULL DEFAULT 'queued',
    pages_crawled INTEGER DEFAULT 0,
    leads_found INTEGER DEFAULT 0,
    error_message TEXT,
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ----------------------------------------------------------------------------
-- Target lists: CSV imports / manually curated batches awaiting enrichment.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS target_lists (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT NOT NULL,
    description TEXT,
    row_count INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ----------------------------------------------------------------------------
-- Leads: the people / companies we're going after.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS leads (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source_id UUID REFERENCES lead_sources(id) ON DELETE SET NULL,
    discovery_run_id UUID REFERENCES discovery_runs(id) ON DELETE SET NULL,
    matched_service_id UUID REFERENCES service_offerings(id) ON DELETE SET NULL,
    target_list_id UUID REFERENCES target_lists(id) ON DELETE SET NULL,

    name TEXT,
    company TEXT,
    email TEXT,
    website TEXT,
    location TEXT,
    role TEXT,
    linkedin_url TEXT,
    domain TEXT,

    project_summary TEXT,
    raw_excerpt TEXT,
    source_url TEXT,

    fit_score INTEGER DEFAULT 0,
    urgency TEXT DEFAULT 'medium',
    qualification_notes TEXT,

    enrichment_status TEXT DEFAULT 'pending',  -- pending|partial|enriched|failed
    enrichment_data JSONB DEFAULT '{}'::jsonb, -- merged waterfall output
    enriched_at TIMESTAMPTZ,

    research_summary TEXT,
    research_data JSONB DEFAULT '{}'::jsonb,   -- LLM deep-research output
    researched_at TIMESTAMPTZ,

    status TEXT NOT NULL DEFAULT 'new',
    fingerprint TEXT UNIQUE,
    raw_data JSONB DEFAULT '{}'::jsonb,
    tags TEXT[] DEFAULT '{}',

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_leads_status ON leads(status);
CREATE INDEX IF NOT EXISTS idx_leads_fit_score ON leads(fit_score DESC);
CREATE INDEX IF NOT EXISTS idx_leads_created_at ON leads(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_leads_email ON leads(email) WHERE email IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_leads_domain ON leads(domain) WHERE domain IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_leads_target_list ON leads(target_list_id);

-- ----------------------------------------------------------------------------
-- Outreach messages.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS outreach_messages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    lead_id UUID NOT NULL REFERENCES leads(id) ON DELETE CASCADE,
    direction TEXT NOT NULL DEFAULT 'outbound',
    channel TEXT NOT NULL DEFAULT 'email',
    subject TEXT,
    body TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft',
    error_message TEXT,
    scheduled_at TIMESTAMPTZ,
    sent_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_outreach_lead ON outreach_messages(lead_id);
CREATE INDEX IF NOT EXISTS idx_outreach_status ON outreach_messages(status);

-- ----------------------------------------------------------------------------
-- Enrichment runs: audit trail of which provider returned what.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS enrichment_runs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    lead_id UUID REFERENCES leads(id) ON DELETE CASCADE,
    providers_tried TEXT[] DEFAULT '{}',
    providers_hit TEXT[] DEFAULT '{}',
    fields_filled TEXT[] DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'completed',  -- completed|partial|failed
    error_message TEXT,
    raw_results JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_enrichment_lead ON enrichment_runs(lead_id);

-- ----------------------------------------------------------------------------
-- Scheduled jobs: APScheduler persistence layer (we use it as a simple list,
-- the scheduler itself loads jobs from this table on startup).
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS scheduled_jobs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT NOT NULL,
    kind TEXT NOT NULL,                  -- 'discovery' | 'enrichment_pending' | 'crm_sync'
    cron TEXT NOT NULL,                  -- 5-field cron expression, UTC
    payload JSONB DEFAULT '{}'::jsonb,
    is_active BOOLEAN DEFAULT TRUE,
    last_run_at TIMESTAMPTZ,
    last_status TEXT,
    last_error TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ----------------------------------------------------------------------------
-- CRM webhook configs: push lead events to HubSpot / Pipedrive / generic JSON.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS crm_webhooks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT NOT NULL,
    url TEXT NOT NULL,
    secret TEXT,
    events TEXT[] DEFAULT '{lead.created,lead.contacted,lead.replied,lead.won}',
    headers JSONB DEFAULT '{}'::jsonb,
    body_template TEXT,                  -- optional Jinja-style template; null = full lead json
    is_active BOOLEAN DEFAULT TRUE,
    last_fired_at TIMESTAMPTZ,
    last_status_code INTEGER,
    last_error TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ----------------------------------------------------------------------------
-- Lead-chat projects — per-business chat threads with persistent memory
-- the active LLM can read on every turn.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS chat_projects (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT NOT NULL,
    description TEXT,
    system_prompt TEXT,
    memory TEXT,                       -- free-form notes injected into every turn
    is_pinned BOOLEAN DEFAULT FALSE,
    created_by UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_chat_projects_updated ON chat_projects(updated_at DESC);

-- One row per message. Tool calls + tool results live in here too, so the
-- full provider-replayable history is just `SELECT * FROM chat_messages
-- WHERE project_id=? ORDER BY created_at`.
CREATE TABLE IF NOT EXISTS chat_messages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id UUID NOT NULL REFERENCES chat_projects(id) ON DELETE CASCADE,
    role TEXT NOT NULL,                -- 'user' | 'assistant' | 'tool'
    content TEXT,
    tool_calls JSONB,                  -- assistant turns can request tools
    tool_call_id TEXT,                 -- tool results link back to the call id
    tool_name TEXT,
    error TEXT,                        -- populated when a tool call failed
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_chat_messages_project ON chat_messages(project_id, created_at);
-- chat_projects.updated_at is maintained by SQLAlchemy onupdate, no trigger.

-- ----------------------------------------------------------------------------
-- LLM provider configurations.
-- Multiple rows allowed; only one row is `is_active=TRUE` at a time and that's
-- what the backend uses for all LLM calls. If no row is active, the backend
-- falls back to the LLM_* env vars (legacy / bootstrap path).
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS llm_configs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT NOT NULL,                -- friendly label e.g. "DeepSeek prod"
    provider_kind TEXT NOT NULL,       -- 'openai_compat' | 'anthropic'
    base_url TEXT NOT NULL,
    model TEXT NOT NULL,
    api_key TEXT NOT NULL,             -- plaintext; column is sensitive
    is_active BOOLEAN DEFAULT FALSE,
    extra JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_llm_configs_active ON llm_configs(is_active);

-- ----------------------------------------------------------------------------
-- Google Sheets sync configurations.
-- One row per spreadsheet/worksheet target. Triggered manually or by a
-- scheduled_jobs row of kind='sheets_sync'.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS sheets_configs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT NOT NULL,
    spreadsheet_id TEXT NOT NULL,
    spreadsheet_url TEXT,
    worksheet_name TEXT NOT NULL DEFAULT 'Leads',
    sync_kind TEXT NOT NULL DEFAULT 'leads',  -- 'leads' | 'outreach' | 'enrichment_runs'
    filters JSONB DEFAULT '{}'::jsonb,        -- e.g. {"min_fit_score": 60, "status": "new"}
    is_active BOOLEAN DEFAULT TRUE,
    last_synced_at TIMESTAMPTZ,
    last_status TEXT,
    last_error TEXT,
    last_row_count INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ----------------------------------------------------------------------------
-- Updated-at trigger.
-- ----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION touch_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS leads_touch ON leads;
CREATE TRIGGER leads_touch
BEFORE UPDATE ON leads
FOR EACH ROW EXECUTE FUNCTION touch_updated_at();

-- ----------------------------------------------------------------------------
-- Seed sources so the dashboard isn't empty on first boot.
-- ----------------------------------------------------------------------------
INSERT INTO lead_sources (kind, name, config) VALUES
    ('hackernews', 'HN: Who Is Hiring (latest)', '{"thread": "who_is_hiring"}'),
    ('hackernews', 'HN: Who Wants To Be Hired (latest)', '{"thread": "who_wants_to_be_hired"}'),
    ('reddit', 'r/forhire', '{"subreddit": "forhire", "limit": 50}'),
    ('reddit', 'r/SaaS', '{"subreddit": "SaaS", "limit": 50}')
ON CONFLICT DO NOTHING;
