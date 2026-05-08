# LeadMagnet

> Self-hosted, open-source replacement for **Apify + Clay** on a single VPS. Drop in your DeepSeek or Qwen API key and let it find work for you.

LeadMagnet stitches together best-in-class open-source tools so you can replace Apify (scraping/orchestration), Clay (waterfall enrichment + AI research), and a chunk of an outbound stack — all on one Contabo box.

## What it replaces

### Apify

| Apify feature              | Replacement                                   |
| -------------------------- | --------------------------------------------- |
| Actors / scraping API      | [Crawl4AI](https://github.com/unclecode/crawl4ai) + Playwright |
| Job orchestration          | FastAPI workers + APScheduler (in-process)    |
| AI extraction              | DeepSeek / Qwen / OpenAI / Ollama (any OpenAI-compat API) |
| Storage / datasets         | PostgreSQL                                    |
| Console UI                 | Next.js dashboard + NocoDB spreadsheet view   |

### Clay

| Clay feature               | Replacement                                   |
| -------------------------- | --------------------------------------------- |
| Multi-source waterfall enrichment | Pluggable provider chain: Website → Hunter.io → Snov.io → LLM research |
| Web scraping for prospect data    | Crawl4AI (already in stack)            |
| AI research on prospects   | DeepSeek/Qwen prompt → structured dossier (employee est, tech stack, signals, hooks) |
| Workflow automation / cron | APScheduler — discovery / enrichment on cron  |
| Spreadsheet-style UI       | NocoDB on the same Postgres                   |
| CRM push                   | Generic webhooks (HubSpot, Pipedrive, Slack, anything) with HMAC signing |
| LinkedIn data extraction   | Crawl4AI fallback fetches public OG/meta tags |
| CSV target list import     | Built-in `/api/import/csv` upload             |

## What it does end-to-end

1. You declare what you sell (e.g. "Next.js + Stripe SaaS MVPs in 4 weeks").
2. **Discovery**: scrape HN *Who's Hiring*, Reddit, ProductHunt, IndieHackers, custom URLs. LLM extracts structured leads + scores fit.
3. **Enrichment waterfall**: for each lead, run Website → Hunter.io → Snov.io → LLM research, merging results, until we have email + name + dossier. Audit trail of which provider returned what.
4. **AI research**: deep dossier per prospect — company one-liner, employee estimate, tech stack, recent signals, pain points, outreach hooks.
5. **Notify**: high-fit leads ping Telegram / webhook / email.
6. **Outreach**: LLM drafts a personalized email referencing concrete details from their post → you approve → SMTP send.
7. **CRM push**: every lead lifecycle event (created, enriched, contacted, replied, won, lost) is POSTed to your CRM webhooks with HMAC signature.
8. **Schedule**: cron-style automation runs all of the above on the cadence you choose.

## Quick start (local)

```bash
git clone https://github.com/havijavi/leadmagnet.git
cd leadmagnet
cp .env.example .env
# At minimum edit: ADMIN_TOKEN, POSTGRES_PASSWORD. Add LLM_API_KEY when ready.
docker compose up -d --build
```

| Service       | URL                                  | Purpose                            |
| ------------- | ------------------------------------ | ---------------------------------- |
| Dashboard     | http://localhost:3000                | Day-to-day pipeline UI             |
| API docs      | http://localhost:8000/docs           | Swagger + try-it-out               |
| NocoDB        | http://localhost:8080                | Spreadsheet view of every table    |

The dashboard prompts for `ADMIN_TOKEN` on first load — paste it from your `.env`. NocoDB needs first-time setup: pick "External database" → Postgres, host `postgres`, port `5432`, db/user/password from `.env`.

## Deploy to a Contabo VPS

DNS: point `leadmagnet.yourdomain.com` (and optionally `data.yourdomain.com` for NocoDB) at the VPS IP. Then on a fresh Ubuntu/Debian box:

```bash
sudo DOMAIN=leadmagnet.yourdomain.com \
     NOCODB_DOMAIN=data.yourdomain.com \
     ACME_EMAIL=you@yourdomain.com \
     bash <(curl -fsSL https://raw.githubusercontent.com/havijavi/leadmagnet/main/deploy/setup-vps.sh)
```

The script installs Docker, clones this repo to `/opt/leadmagnet`, generates strong secrets in `.env`, and brings the stack up under Caddy with auto-HTTPS.

## Configure your LLM (DeepSeek / Qwen / OpenAI / Ollama)

Any OpenAI-compatible API works:

```env
# DeepSeek (recommended — cheapest)
LLM_BASE_URL=https://api.deepseek.com/v1
LLM_MODEL=deepseek-chat
LLM_API_KEY=sk-...

# Qwen via DashScope
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_MODEL=qwen-plus

# Local Ollama
LLM_BASE_URL=http://host.docker.internal:11434/v1
LLM_MODEL=qwen2.5:14b
LLM_API_KEY=ollama
```

Leave `LLM_API_KEY` blank to run **mock mode**: extraction returns canned data so you can verify wiring before paying for tokens.

## Configure enrichment providers

The waterfall runs whichever providers you've configured, in this order:

1. **Website** (always on, free) — Crawl4AI fetches the company home page; we pull title, contact email, LinkedIn URL, and a research excerpt.
2. **Hunter.io** (free 25 searches/month) — set `HUNTER_API_KEY`. Email finder + domain search.
3. **Snov.io** (free 50 credits/month) — set `SNOV_CLIENT_ID` and `SNOV_CLIENT_SECRET`.
4. **LLM research** (always on, ~1 LLM call per lead) — synthesizes the structured dossier.

Add a provider by dropping a module in `backend/app/services/enrichment/` and appending it to `PROVIDERS`.

## Architecture

```
                           ┌───────────────────────┐
                           │ Caddy (auto-HTTPS)    │
                           └──────────┬────────────┘
                                      │
        ┌───────────────────┬─────────┼──────────────┬───────────────────────┐
        ▼                   ▼         ▼              ▼                       ▼
┌──────────────┐    ┌──────────────┐  ┌──────────────────┐         ┌──────────────────┐
│ Next.js UI   │    │ NocoDB       │  │ FastAPI backend  │ ──────► │ DeepSeek / Qwen  │
│ (3000)       │    │ (8080)       │  │   + APScheduler  │         │  (your LLM)      │
└──────────────┘    └──────┬───────┘  │   + workers      │         └──────────────────┘
                           │          └──────┬───────────┘
                           │                 │
                           ▼                 ▼
                       ┌────────────────────────────┐
                       │       PostgreSQL           │  ← single source of truth
                       │  (leads, runs, schedules,  │
                       │   crm_webhooks, …)         │
                       └────────────────────────────┘
                                  ▲
                                  │
                       ┌──────────┴──────────────┐
                       │ Crawl4AI / Playwright   │  ← stealth headless browser
                       │ + httpx fallback        │
                       └─────────────────────────┘

Inputs:  HN · Reddit · ProductHunt · IndieHackers · custom URLs · Google (via SearXNG) · CSV upload
Outputs: SMTP · Telegram · webhooks (Slack, Discord) · CRM webhooks (HubSpot, Pipedrive, generic)
```

## Pages in the dashboard

- `/` — KPIs, system health, enrichment provider status
- `/services` — what you sell
- `/sources` — where to harvest leads
- `/discovery` — manual + scheduled discovery runs
- `/import` — CSV target lists, manual lead entry
- `/leads` — sorted by fit score, drawer for enrichment + research + outreach
- `/enrichment` — bulk enrichment, ad-hoc waterfall test, run history
- `/campaigns` — outreach drafts and sends
- `/schedules` — APScheduler cron jobs (replaces n8n)
- `/crm` — CRM webhook configuration, test fire

## API surface (auth: `Authorization: Bearer <ADMIN_TOKEN>`)

| Endpoint                          | Method | Purpose                          |
| --------------------------------- | ------ | -------------------------------- |
| `/api/services`                   | CRUD   | Service offerings                |
| `/api/sources`                    | CRUD   | Lead sources                     |
| `/api/discovery/run`              | POST   | Trigger a discovery run          |
| `/api/discovery/suggest-queries`  | POST   | LLM-generated search queries     |
| `/api/import/csv`                 | POST   | Upload a CSV target list         |
| `/api/import/lead`                | POST   | Create a single lead manually    |
| `/api/import/lists`               | GET    | List target lists                |
| `/api/leads`                      | CRUD   | Leads (filter by score, status, list) |
| `/api/enrichment/providers`       | GET    | What's configured                |
| `/api/enrichment/run`             | POST   | Single waterfall (lead_id or ad-hoc subject) |
| `/api/enrichment/batch`           | POST   | Bulk enrichment                  |
| `/api/enrichment/runs`            | GET    | Audit trail                      |
| `/api/research/run`               | POST   | Deep AI research on one lead     |
| `/api/campaigns/draft`            | POST   | LLM-draft outreach               |
| `/api/campaigns/{id}/send`        | POST   | Send via SMTP                    |
| `/api/schedules`                  | CRUD   | APScheduler cron jobs            |
| `/api/crm`                        | CRUD   | CRM webhook configs              |
| `/api/crm/{id}/test`              | POST   | Fire a test event                |
| `/health`, `/api/stats`           | GET    | Operational visibility           |

Full Swagger at `/docs` once the backend is up.

## CRM webhook events

Each webhook subscribes to a subset of:

- `lead.created` — new lead lands (discovery or CSV)
- `lead.enriched` — waterfall completed
- `lead.contacted` — outreach email sent
- `lead.replied` — you marked the lead as replied
- `lead.won`, `lead.lost`, `lead.trash`, `lead.reviewed` — status changes

Body is full lead JSON by default. Provide a `body_template` like `{"name": "{{lead.name}}", "score": "{{lead.fit_score}}"}` to reshape per-CRM. If `secret` is set, every request includes an HMAC SHA-256 signature in `X-LeadMagnet-Signature: sha256=<hex>` so the receiver can verify authenticity.

## Project layout

```
leadmagnet/
├── docker-compose.yml          # full stack (no n8n)
├── Caddyfile                   # reverse proxy + TLS
├── .env.example                # configuration template
├── deploy/
│   ├── setup-vps.sh            # one-shot Contabo bootstrap
│   └── update.sh               # git pull + rebuild
├── db/
│   └── init.sql                # full schema, idempotent
├── backend/                    # FastAPI orchestrator
│   └── app/
│       ├── api/                # REST endpoints
│       ├── services/
│       │   ├── crawler.py
│       │   ├── extractor.py
│       │   ├── llm.py
│       │   ├── emailer.py
│       │   ├── notifier.py
│       │   ├── crm_push.py
│       │   ├── scheduler.py
│       │   └── enrichment/     # waterfall provider chain
│       │       ├── waterfall.py
│       │       ├── website.py
│       │       ├── hunter.py
│       │       ├── snov.py
│       │       └── llm_research.py
│       ├── sources/            # one file per harvester
│       └── workers/            # discovery, enrichment, csv-import
└── frontend/                   # Next.js 14 dashboard
    └── app/
        ├── page.tsx            # dashboard
        ├── services/
        ├── sources/
        ├── discovery/
        ├── import/
        ├── leads/
        ├── enrichment/
        ├── campaigns/
        ├── schedules/
        └── crm/
```

## Roadmap (you can fork/extend)

- [ ] Twitter/X harvester (via nitter)
- [ ] Email reply tracking (IMAP polling) → auto-set `lead.replied`
- [ ] Multi-step email sequences with reply detection
- [ ] Vector dedupe across leads (Chroma)
- [ ] More enrichment providers: Apollo free tier, Clearbit free, Dropcontact

## License

MIT.
