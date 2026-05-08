# n8n workflow templates

These are *optional* — the LeadMagnet backend has its own scheduler-friendly endpoints, so you can run everything without n8n. n8n becomes useful when you want a visual editor, custom branching, or to glue LeadMagnet to other tools (Slack, Notion, Google Sheets, your CRM).

## Importing

1. Bring up n8n: `docker compose --profile n8n up -d n8n`
2. Open `http://<host>:5678` and log in (creds in `.env`).
3. Settings → Import workflow → select a `.json` file from this folder.
4. Create an HTTP Header credential named **LeadMagnet Admin Token**:
   - Header name: `Authorization`
   - Header value: `Bearer <your ADMIN_TOKEN>`
5. Activate the workflow.

## Templates

- `lead-discovery.json` — runs `/api/discovery/run` every 6 hours over all active sources.

## Building your own

The backend exposes everything you need:

| Endpoint                          | Method | Purpose                          |
| --------------------------------- | ------ | -------------------------------- |
| `/api/discovery/run`              | POST   | Trigger a discovery run          |
| `/api/discovery/runs`             | GET    | List recent runs                 |
| `/api/discovery/suggest-queries`  | POST   | LLM-generated search queries     |
| `/api/leads`                      | GET    | List leads (filter by score etc) |
| `/api/campaigns/draft`            | POST   | Draft outreach with LLM          |
| `/api/campaigns/{id}/send`        | POST   | Send via SMTP                    |

All endpoints require `Authorization: Bearer <ADMIN_TOKEN>`.
