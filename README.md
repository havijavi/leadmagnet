# LeadMagnet

> Self-hosted, open-source alternative to Apify + a built-in lead generation, qualification, and outreach machine. Drop in your DeepSeek or Qwen API key and let it find work for you.

LeadMagnet stitches together best-in-class open-source tools so you can replace Apify, Clay, Apollo, and a chunk of your outbound stack on a single VPS:

| Layer            | Tool used                          | Replaces                          |
| ---------------- | ---------------------------------- | --------------------------------- |
| Scraping         | [Crawl4AI](https://github.com/unclecode/crawl4ai) (LLM-friendly) | Apify Actors, Firecrawl |
| Orchestration    | FastAPI workers + optional n8n     | Apify Cloud, Zapier               |
| AI extraction    | DeepSeek / Qwen / any OpenAI-compat | Clay AI, Apollo enrichment       |
| Storage          | PostgreSQL                         | Apify datasets                    |
| Email outreach   | SMTP (Postmark/SES/Mailgun/etc.)   | Lemlist, Instantly                |
| Notifications    | Email, Telegram, generic webhook   | —                                 |
| Reverse proxy    | Caddy (auto-HTTPS)                 | —                                 |
| UI               | Next.js dashboard                  | Apify Console                     |

## What it does

You tell LeadMagnet what services you sell ("Next.js development, AI integrations, branding"). It then:

1. Generates targeted search queries using your LLM
2. Scrapes Hacker News *Who's Hiring*, Reddit r/forhire, ProductHunt, IndieHackers, generic URLs you add, and any custom source
3. Sends raw page content to DeepSeek/Qwen, which extracts structured leads (name, email, project, urgency, fit score)
4. Stores qualified leads in Postgres
5. Pings you (email / Telegram / webhook) when a high-score lead lands
6. Drafts a personalized outreach email per lead — you approve, it sends via SMTP
7. Tracks campaign state so you don't double-message anyone

## Quick start (local)

```bash
git clone https://github.com/havijavi/leadmagnet.git
cd leadmagnet
cp .env.example .env
# edit .env — at minimum set LLM_API_KEY, POSTGRES_PASSWORD, ADMIN_TOKEN
docker compose up -d --build
open http://localhost:3000
```

The dashboard is at `http://localhost:3000`, the API at `http://localhost:8000/docs`, and (if enabled) n8n at `http://localhost:5678`.

## Deploy to a Contabo VPS

```bash
# on a fresh Ubuntu 22.04+ Contabo box, as root
curl -fsSL https://raw.githubusercontent.com/havijavi/leadmagnet/main/deploy/setup-vps.sh -o setup.sh
chmod +x setup.sh
sudo DOMAIN=leadmagnet.yourdomain.com EMAIL=you@yourdomain.com ./setup.sh
```

The script installs Docker, clones this repo into `/opt/leadmagnet`, generates secrets, brings the stack up, and points Caddy at your domain so you get HTTPS automatically. Make sure your domain's A record points at the VPS IP first.

## Configure your LLM

LeadMagnet talks to **any OpenAI-compatible API**. In `.env`:

```
LLM_PROVIDER=deepseek
LLM_BASE_URL=https://api.deepseek.com/v1
LLM_MODEL=deepseek-chat
LLM_API_KEY=sk-...
```

For Qwen via DashScope:
```
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_MODEL=qwen-plus
```

For local Ollama:
```
LLM_BASE_URL=http://host.docker.internal:11434/v1
LLM_MODEL=qwen2.5:14b
LLM_API_KEY=ollama
```

If you leave `LLM_API_KEY` blank LeadMagnet runs in **mock mode** — extraction returns canned data so you can verify wiring before paying for tokens.

## Architecture

```
                     ┌─────────────────────┐
                     │   Caddy (HTTPS)     │
                     └──────────┬──────────┘
                                │
              ┌─────────────────┴─────────────────┐
              ▼                                   ▼
     ┌─────────────────┐                ┌─────────────────┐
     │ Next.js (3000)  │ ───────────►   │ FastAPI (8000)  │
     │  Dashboard      │                │  + workers      │
     └─────────────────┘                └────────┬────────┘
                                                 │
                ┌────────────────────────────────┼────────────────────────────┐
                ▼                                ▼                            ▼
       ┌─────────────────┐              ┌─────────────────┐         ┌──────────────────┐
       │   Crawl4AI      │              │   DeepSeek /    │         │    Postgres      │
       │  (Playwright)   │              │   Qwen / etc.   │         │    Redis         │
       └─────────────────┘              └─────────────────┘         └──────────────────┘
                ▲
                │  (optional)
       ┌────────┴────────┐
       │   n8n (5678)    │  ← visual workflow editor for advanced pipelines
       └─────────────────┘
```

## Built-in lead sources

Out of the box LeadMagnet knows how to harvest from:

- **Hacker News** — *Who Is Hiring* and *Who Wants To Be Hired* threads
- **Reddit** — any subreddit's `.json` feed (defaults: r/forhire, r/slavelabour, r/SaaS, r/startups)
- **Generic URL** — point at a job board, marketplace, or directory
- **Google search** — uses your search query through Crawl4AI on a SearXNG instance (config in `.env`)

Add more in `backend/app/sources/` — they're tiny Python modules with one async `fetch()` function.

## Roadmap (you can fork/extend)

- [ ] Twitter/X harvester (via nitter)
- [ ] LinkedIn harvester (via headless login + cookie reuse — your account, your risk)
- [ ] Slack/Discord webhook ingest
- [ ] Vector DB (Chroma) for de-dup and semantic search across leads
- [ ] Scheduled discovery cron via APScheduler (skeleton already in `discovery_worker.py`)
- [ ] Multi-step email sequences with reply detection (IMAP polling)

## Project layout

```
leadmagnet/
├── docker-compose.yml          # full stack
├── Caddyfile                   # reverse proxy / TLS
├── .env.example                # config template
├── deploy/
│   └── setup-vps.sh            # one-shot Contabo bootstrap
├── db/
│   └── init.sql                # schema
├── backend/                    # FastAPI orchestrator
│   └── app/
│       ├── api/                # REST endpoints
│       ├── services/           # crawler, llm, emailer, notifier
│       ├── sources/            # one file per harvester
│       └── workers/            # background jobs
├── frontend/                   # Next.js dashboard
│   └── app/                    # pages
└── n8n-workflows/              # importable workflow templates
```

## License

MIT. Do whatever you want with it.
