-- LeadMagnet database schema
-- Loaded once on first Postgres boot via docker-entrypoint-initdb.d.

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Services the user offers (e.g. "Next.js development", "AI integrations").
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

-- Lead sources (Hacker News, Reddit, Google search, custom URLs).
CREATE TABLE IF NOT EXISTS lead_sources (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    kind TEXT NOT NULL,        -- 'hackernews' | 'reddit' | 'google' | 'url'
    name TEXT NOT NULL,
    config JSONB DEFAULT '{}'::jsonb,
    is_active BOOLEAN DEFAULT TRUE,
    schedule_cron TEXT,        -- optional, for future scheduler
    last_run_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Discovery runs (one per source-trigger).
CREATE TABLE IF NOT EXISTS discovery_runs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source_id UUID REFERENCES lead_sources(id) ON DELETE SET NULL,
    status TEXT NOT NULL DEFAULT 'queued',  -- queued|running|completed|failed
    pages_crawled INTEGER DEFAULT 0,
    leads_found INTEGER DEFAULT 0,
    error_message TEXT,
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- The leads themselves.
CREATE TABLE IF NOT EXISTS leads (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source_id UUID REFERENCES lead_sources(id) ON DELETE SET NULL,
    discovery_run_id UUID REFERENCES discovery_runs(id) ON DELETE SET NULL,
    matched_service_id UUID REFERENCES service_offerings(id) ON DELETE SET NULL,

    name TEXT,
    company TEXT,
    email TEXT,
    website TEXT,
    location TEXT,
    role TEXT,

    project_summary TEXT,
    raw_excerpt TEXT,
    source_url TEXT,

    fit_score INTEGER DEFAULT 0,         -- 0-100, LLM-assigned
    urgency TEXT DEFAULT 'medium',       -- low|medium|high
    qualification_notes TEXT,

    status TEXT NOT NULL DEFAULT 'new',  -- new|reviewed|contacted|replied|won|lost|trash
    fingerprint TEXT UNIQUE,             -- hash for dedupe
    raw_data JSONB DEFAULT '{}'::jsonb,

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_leads_status ON leads(status);
CREATE INDEX IF NOT EXISTS idx_leads_fit_score ON leads(fit_score DESC);
CREATE INDEX IF NOT EXISTS idx_leads_created_at ON leads(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_leads_email ON leads(email) WHERE email IS NOT NULL;

-- Outreach campaigns (one per lead, may have multiple messages later).
CREATE TABLE IF NOT EXISTS outreach_messages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    lead_id UUID NOT NULL REFERENCES leads(id) ON DELETE CASCADE,
    direction TEXT NOT NULL DEFAULT 'outbound',  -- outbound|inbound
    channel TEXT NOT NULL DEFAULT 'email',
    subject TEXT,
    body TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft',         -- draft|approved|sent|failed|replied
    error_message TEXT,
    scheduled_at TIMESTAMPTZ,
    sent_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_outreach_lead ON outreach_messages(lead_id);
CREATE INDEX IF NOT EXISTS idx_outreach_status ON outreach_messages(status);

-- Trigger to auto-update leads.updated_at.
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

-- Seed a couple of sources so the dashboard isn't empty on first boot.
INSERT INTO lead_sources (kind, name, config) VALUES
    ('hackernews', 'HN: Who Is Hiring (latest)', '{"thread": "who_is_hiring"}'),
    ('hackernews', 'HN: Who Wants To Be Hired (latest)', '{"thread": "who_wants_to_be_hired"}'),
    ('reddit', 'r/forhire', '{"subreddit": "forhire", "limit": 50}'),
    ('reddit', 'r/SaaS', '{"subreddit": "SaaS", "limit": 50}')
ON CONFLICT DO NOTHING;
