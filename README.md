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
| Console UI                 | Next.js dashboard + Google Sheets sync        |

### Clay

| Clay feature               | Replacement                                   |
| -------------------------- | --------------------------------------------- |
| Multi-source waterfall enrichment | Pluggable provider chain: Website → Hunter.io → Snov.io → LLM research |
| Web scraping for prospect data    | Crawl4AI (already in stack)            |
| AI research on prospects   | DeepSeek/Qwen prompt → structured dossier (employee est, tech stack, signals, hooks) |
| Workflow automation / cron | APScheduler — discovery / enrichment on cron  |
| Spreadsheet-style UI       | Google Sheets sync (one-way, idempotent)      |
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

The dashboard prompts for `ADMIN_TOKEN` on first load — paste it from your `.env`. Google Sheets sync (the spreadsheet view) is configured under `/sheets` once you've added a service account — see below.

## Deploy to a VPS with HTTPS on your own domain

LeadMagnet is built to run on a single small VPS (Contabo, Hetzner, DigitalOcean — anything with 2 GB+ RAM and Docker support) at a real domain with auto-HTTPS via Let's Encrypt. This is the recommended path; running on a bare IP without HTTPS is fine for poking around but unsuitable for real lead data and outreach.

### 1. Point DNS at the VPS

In your domain registrar, add an `A` record:

| Host                  | Type | Value         |
| --------------------- | ---- | ------------- |
| `leadmagnet`          | A    | <your-vps-ip> |

Wait until `dig +short leadmagnet.yourdomain.com` returns the VPS IP — usually under a minute, can take longer. The deploy script will pre-check this and refuse to proceed if DNS hasn't propagated, so Caddy doesn't burn through Let's Encrypt's rate limits trying to acquire a cert for a domain that doesn't resolve.

### 2. Run the bootstrap on a fresh Ubuntu/Debian VPS

```bash
sudo DOMAIN=leadmagnet.yourdomain.com \
     ACME_EMAIL=you@yourdomain.com \
     bash <(curl -fsSL https://raw.githubusercontent.com/havijavi/leadmagnet/main/deploy/setup-vps.sh)
```

The script:

1. Installs Docker + compose plugin if missing.
2. Opens UFW ports 22, 80, 443.
3. Pre-flights DNS (`dig`-checks that the domain resolves to this VPS).
4. Clones the repo to `/opt/leadmagnet`.
5. Generates strong `ADMIN_TOKEN`, `JWT_SECRET`, and `POSTGRES_PASSWORD` in `.env` on first run.
6. Sets `DOMAIN`, `ACME_EMAIL`, and `NEXT_PUBLIC_API_URL=https://<your-domain>`.
7. Brings up the stack with the `prod` profile so Caddy is included.
8. Waits for the backend `/health` to come up and smoke-tests `https://<domain>/health` before printing the success banner.

Re-run the script any time — it preserves the existing `.env` and just pulls + rebuilds.

### 3. Open the dashboard and create the first admin

```
https://leadmagnet.yourdomain.com
```

You'll be redirected to `/setup` to create the first admin account (email + password). After that, sign in at `/login` and invite teammates from **Users** in the sidebar.

### 4. (Optional) Verify any time

```bash
cd /opt/leadmagnet
./deploy/verify.sh
```

Curls `/health`, `/docs`, `/openapi.json`, and `/api/auth/needs-setup` against the public URL, plus prints `docker compose ps`. Fits cleanly into a monitoring cron.

### 5. Updating

```bash
cd /opt/leadmagnet
./deploy/update.sh   # git pull + rebuild + restart
```

### What gets routed where

Caddy handles everything on ports 80 and 443:

| Path on `https://<domain>` | Routed to                | Public? |
| -------------------------- | ------------------------ | ------- |
| `/api/*`                   | `backend:8000`           | bearer-auth required |
| `/docs`, `/redoc`, `/openapi.json` | `backend:8000`   | yes (read-only Swagger) |
| `/health`                  | `backend:8000`           | yes (for uptime monitors) |
| anything else              | `frontend:3000` (Next.js) | gated by `/setup` + `/login` |

Caddy also adds HSTS, `X-Content-Type-Options`, and `Referrer-Policy` headers, and forwards `X-Forwarded-Proto` / `X-Forwarded-Host` so the backend sees the original scheme and host.

### Subdomain alternative (if you'd rather split UI and API)

If you want `app.example.com` for the dashboard and `api.example.com` for the backend, point both A records at the VPS and replace the single-domain block in `Caddyfile` with two site blocks. The included single-domain layout works for 95% of setups and avoids a separate CORS allowlist.

### Troubleshooting

- **Cert acquisition fails**: most common cause is DNS not pointing at the VPS, or port 80 being blocked by your provider's firewall (separate from UFW). Tail `docker compose logs -f caddy`.
- **Dashboard loads but `/api/*` 404s**: this used to happen on early versions due to a Caddy `handle_path` prefix-strip bug — fixed in v0.4.1. Pull and rebuild.
- **Locked out of the dashboard**: use the `ADMIN_TOKEN` from `/opt/leadmagnet/.env` as a Bearer token against `/api/users` to reset another admin's password, or via the Swagger UI at `https://<domain>/docs`.
- **Backups**: the only volume that holds irreplaceable data is `postgres_data`. Snapshot it via `docker compose exec postgres pg_dump -U leadmagnet leadmagnet > leadmagnet-$(date +%F).sql` on a cron.

## Authentication & roles

LeadMagnet has per-user accounts with three roles:

| Role     | Can                                                                |
| -------- | ------------------------------------------------------------------ |
| `admin`  | Everything — system config (services, sources, schedules, sheets, CRM), user management, all data ops |
| `member` | Daily pipeline ops — run discovery, enrichment, research; create/update leads; draft & send outreach; CSV import; trigger sheet syncs |
| `viewer` | Read-only — browse leads, outreach, schedules, dashboards         |

**First-run setup**: visit the dashboard. If no users exist you'll be sent to `/setup` to create the first admin. After that, `/login` is the entry point.

**`ADMIN_TOKEN` is a break-glass superuser**. Anyone presenting it as a bearer token is treated as admin without a user account. Use it for `setup-vps.sh`, CI scripts, or to recover from a locked-out dashboard. Rotate it in `.env` periodically.

**JWTs are signed with `JWT_SECRET`** (auto-derived from `ADMIN_TOKEN` if blank). Tokens last 24h by default — change with `JWT_TTL_SECONDS`. Sessions live in browser localStorage; sign-out clears them.

**Inviting teammates**: as admin go to **Users** in the sidebar → **+ New user** → choose role + initial password. Send them the URL + credentials. They change their password on `/account`.

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

## Google Sheets sync (replaces NocoDB / Notion)

LeadMagnet writes leads, outreach messages, and enrichment audit data to your own Google Sheets — one-way, idempotent (every sync rewrites the tab from current DB state). Use it as your spreadsheet UI, share it with your team, or pipe it into Apps Script for downstream automation.

### Setup (one-time)

1. **Google Cloud Console** → create or pick a project.
2. **APIs & Services → Library** → enable **Google Sheets API**.
3. **APIs & Services → Credentials → Create credentials → Service account**. Skip the optional steps; you don't need to grant it any roles in the project.
4. Click the new service account → **Keys → Add key → JSON**. Download the file.
5. Configure LeadMagnet, two options:
   - **Inline (recommended for production)**: paste the entire JSON into `GOOGLE_SHEETS_CREDENTIALS_JSON` in `.env` (use single-quotes around the value to preserve newlines).
   - **File mount (recommended for local dev)**: drop the JSON at `./secrets/google.json` and set `GOOGLE_SHEETS_CREDENTIALS_FILE=/app/secrets/google.json`. The `./secrets` folder is bind-mounted read-only into the backend container.
6. Open each target Google Sheet → **Share** → paste the service account's `client_email` (shown on the dashboard `/sheets` page) and grant **Editor**.
7. In the dashboard go to `/sheets`, click **+ New config**, and paste either the spreadsheet ID or the full URL — LeadMagnet extracts the ID for you.

### Sync kinds

| Kind              | What gets written                                                |
| ----------------- | ---------------------------------------------------------------- |
| `leads`           | Every lead with status, fit score, enrichment fields, research summary, tags. Filter by `min_fit_score`, `status`, `enrichment_status`. |
| `outreach`        | Every outreach message with subject, body, status, timestamps.   |
| `enrichment_runs` | Audit log of every waterfall run (providers tried, fields filled, errors). |

### Triggering syncs

- Manual: `/sheets` page → **Sync now** on a config, or **Sync all now**.
- Scheduled: `/schedules` → new job of kind `sheets_sync`. Optional `payload.config_id` targets a single config; otherwise all active configs run.
- API: `POST /api/sheets/{id}/sync` or `POST /api/sheets/sync-all`.

## Architecture

```
                          ┌───────────────────────┐
                          │ Caddy (auto-HTTPS)    │
                          └──────────┬────────────┘
                                     │
                ┌────────────────────┴─────────────────────┐
                ▼                                          ▼
       ┌──────────────────┐                       ┌──────────────────────┐
       │ Next.js UI       │ ────────────────────► │ FastAPI backend      │
       │ (3000)           │                       │  + APScheduler       │
       └──────────────────┘                       │  + waterfall workers │
                                                  └────────┬─────────────┘
                                                           │
       ┌────────────────────┬────────────────────┬─────────┼───────────────┬───────────────────────┐
       ▼                    ▼                    ▼         ▼               ▼                       ▼
┌──────────────┐   ┌──────────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  ┌──────────────────┐
│ Crawl4AI /   │   │ Hunter / Snov    │  │ DeepSeek /   │  │ PostgreSQL   │  │ Google Sheets    │  │ SMTP · Telegram  │
│ Playwright   │   │ (waterfall)      │  │ Qwen (LLM)   │  │ (truth)      │  │ (sync read-only) │  │ webhooks · CRM   │
└──────────────┘   └──────────────────┘  └──────────────┘  └──────────────┘  └──────────────────┘  └──────────────────┘

Inputs:  HN · Reddit · ProductHunt · IndieHackers · custom URLs · Google (SearXNG) · CSV upload
Outputs: SMTP · Telegram · generic webhooks · CRM webhooks (HubSpot, Pipedrive) · Google Sheets
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
- `/schedules` — APScheduler cron jobs (discovery, enrichment, sheets sync, CRM)
- `/sheets` — Google Sheets sync configurations
- `/crm` — CRM webhook configuration, test fire (admin only)
- `/admin/users` — invite teammates, change roles, reset passwords (admin only)
- `/account` — change your own password

## API surface

Auth: `Authorization: Bearer <token>` where `<token>` is either a user's JWT (from `POST /api/auth/login`) **or** the `ADMIN_TOKEN` superuser bypass.

| Endpoint                          | Method | Min role | Purpose                          |
| --------------------------------- | ------ | -------- | -------------------------------- |
| `/api/auth/needs-setup`           | GET    | public   | Whether the first-admin setup is needed |
| `/api/auth/setup`                 | POST   | public†  | Create first admin (only when no users exist) |
| `/api/auth/login`                 | POST   | public   | Email + password → JWT           |
| `/api/auth/me`                    | GET    | any      | Current user details             |
| `/api/auth/change-password`       | POST   | any      | Change own password              |
| `/api/users`                      | CRUD   | admin    | User management                  |
| `/api/services`                   | GET    | viewer+  | List service offerings           |
| `/api/services`                   | POST/PUT/DELETE | admin | Modify service offerings   |
| `/api/sources`                    | GET    | viewer+  | List sources                     |
| `/api/sources`                    | POST/PUT/DELETE | admin | Modify sources             |
| `/api/discovery/run`              | POST   | member+  | Trigger a discovery run          |
| `/api/discovery/suggest-queries`  | POST   | member+  | LLM-generated search queries     |
| `/api/import/csv`                 | POST   | member+  | Upload a CSV target list         |
| `/api/import/lead`                | POST   | member+  | Create a single lead manually    |
| `/api/import/lists`               | GET    | viewer+  | List target lists                |
| `/api/import/lists/{id}`          | DELETE | admin    | Delete a target list             |
| `/api/leads`                      | GET    | viewer+  | List leads                       |
| `/api/leads/{id}`                 | PATCH  | member+  | Update a lead                    |
| `/api/leads/{id}`                 | DELETE | admin    | Delete a lead                    |
| `/api/enrichment/*`               | *      | member+  | Waterfall enrichment             |
| `/api/research/run`               | POST   | member+  | Deep AI research on one lead     |
| `/api/campaigns`                  | GET    | viewer+  | List outreach messages           |
| `/api/campaigns/draft`, `/{id}/send` | POST | member+ | Draft / send outreach            |
| `/api/schedules`                  | GET    | viewer+  | View scheduled jobs              |
| `/api/schedules`                  | POST/PUT/DELETE | admin | Manage scheduled jobs       |
| `/api/sheets`                     | GET    | viewer+  | View sync configs                |
| `/api/sheets`                     | POST/PUT/DELETE | admin | Manage sync configs         |
| `/api/sheets/{id}/sync`, `/sync-all` | POST | member+ | Trigger a sync                  |
| `/api/crm`                        | CRUD   | admin    | CRM webhook configs              |
| `/api/crm/{id}/test`              | POST   | admin    | Fire a test event                |
| `/api/stats`                      | GET    | viewer+  | KPIs                             |
| `/health`                         | GET    | public   | Operational status               |

† `/api/auth/setup` only works when zero users exist; otherwise it returns 400.

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
│       │   ├── google_sheets.py    # service-account-based sheet writes
│       │   └── enrichment/         # waterfall provider chain
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
        ├── sheets/
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
