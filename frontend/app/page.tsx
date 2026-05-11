"use client";

import useSWR from "swr";
import Link from "next/link";
import { fetcher } from "@/lib/api";

type Stats = {
  leads_total: number;
  leads_new: number;
  leads_contacted: number;
  leads_replied: number;
  high_fit_count: number;
  discovery_runs_24h: number;
  leads_enriched: number;
  leads_pending_enrichment: number;
};

type Provider = { name: string; configured: boolean; fields: string[] };

type Health = {
  llm_configured: boolean;
  llm_source: "db" | "env" | "none";
  llm_provider_kind?: string;
  llm_base_url?: string;
  llm_model?: string;
  llm_config_name?: string;
  llm_mock_mode: boolean;
  smtp_configured: boolean;
  telegram_configured: boolean;
  webhook_configured: boolean;
  enrichment_providers: Provider[];
  scheduler_enabled: boolean;
  google_sheets_configured: boolean;
  google_sheets_service_account?: string;
};

export default function Dashboard() {
  const { data: stats } = useSWR<Stats>("/api/stats", fetcher, { refreshInterval: 5000 });
  const { data: health } = useSWR<Health>("/health", fetcher, { refreshInterval: 10000 });

  return (
    <div className="space-y-8">
      <header>
        <h1 className="text-3xl font-bold">Dashboard</h1>
        <p className="text-muted">Apify replacement plus a Clay-style lead engine. All in one box.</p>
      </header>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Stat label="Leads total" value={stats?.leads_total} />
        <Stat label="High-fit (≥70)" value={stats?.high_fit_count} accent />
        <Stat label="New" value={stats?.leads_new} />
        <Stat label="Contacted" value={stats?.leads_contacted} />
        <Stat label="Replied" value={stats?.leads_replied} />
        <Stat label="Enriched" value={stats?.leads_enriched} />
        <Stat label="Pending enrichment" value={stats?.leads_pending_enrichment} />
        <Stat label="Discovery runs (24h)" value={stats?.discovery_runs_24h} />
      </div>

      <section className="card">
        <h2 className="text-xl font-semibold mb-3">System</h2>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-3 text-sm">
          <Pill
            label="LLM"
            value={health?.llm_mock_mode ? "MOCK (no key)" : (health?.llm_config_name ?? "LIVE")}
            tone={health?.llm_mock_mode ? "warn" : "good"}
          />
          <Pill label="Model" value={health?.llm_model ?? "—"} />
          <Pill label="LLM kind" value={health?.llm_provider_kind ?? "—"} />
          <Pill label="Scheduler" value={health?.scheduler_enabled ? "running" : "off"} tone={health?.scheduler_enabled ? "good" : "muted"} />
          <Pill label="SMTP" value={health?.smtp_configured ? "ready" : "off"} tone={health?.smtp_configured ? "good" : "muted"} />
          <Pill label="Telegram" value={health?.telegram_configured ? "ready" : "off"} tone={health?.telegram_configured ? "good" : "muted"} />
          <Pill label="Google Sheets" value={health?.google_sheets_configured ? "ready" : "off"} tone={health?.google_sheets_configured ? "good" : "muted"} />
        </div>
        {health?.llm_mock_mode && (
          <p className="text-xs text-muted mt-3">
            No LLM configured — go to <Link href="/admin/llm" className="text-accent2">LLM providers</Link> to add OpenAI / Claude / DeepSeek / Qwen / Gemini / Ollama / etc.
          </p>
        )}
      </section>

      <section className="card">
        <h2 className="text-xl font-semibold mb-3">Enrichment providers</h2>
        <div className="grid md:grid-cols-2 gap-2 text-sm">
          {health?.enrichment_providers?.map((p) => (
            <div key={p.name} className="flex items-center justify-between bg-panel2 rounded-lg px-3 py-2">
              <div>
                <div className="font-medium">{p.name}</div>
                <div className="text-xs text-muted">fills: {p.fields.join(", ")}</div>
              </div>
              <span className={`pill ${p.configured ? "bg-good/15 text-good" : "bg-warn/15 text-warn"}`}>
                {p.configured ? "ready" : "not configured"}
              </span>
            </div>
          ))}
        </div>
      </section>

      <section className="card">
        <h2 className="text-xl font-semibold mb-3">Get started</h2>
        <ol className="space-y-2 text-sm list-decimal list-inside text-muted">
          <li><Link className="text-accent2" href="/services">Add a service offering</Link> — what you sell.</li>
          <li><Link className="text-accent2" href="/sources">Pick lead sources</Link> or <Link className="text-accent2" href="/import">import a CSV target list</Link>.</li>
          <li><Link className="text-accent2" href="/discovery">Run discovery</Link> to harvest fresh leads, or <Link className="text-accent2" href="/enrichment">enrich existing leads</Link>.</li>
          <li><Link className="text-accent2" href="/leads">Review leads</Link> — open one for AI research and outreach drafting.</li>
          <li><Link className="text-accent2" href="/schedules">Schedule</Link> the pipeline so it runs hands-off, push events to <Link className="text-accent2" href="/crm">CRM webhooks</Link>, and mirror everything into <Link className="text-accent2" href="/sheets">Google Sheets</Link>.</li>
        </ol>
      </section>
    </div>
  );
}

function Stat({ label, value, accent = false }: { label: string; value?: number; accent?: boolean }) {
  return (
    <div className="card">
      <div className="text-xs text-muted">{label}</div>
      <div className={`text-3xl font-semibold ${accent ? "text-accent2" : ""}`}>
        {value ?? "—"}
      </div>
    </div>
  );
}

function Pill({ label, value, tone = "muted" }: { label: string; value: string; tone?: "good" | "warn" | "bad" | "muted" }) {
  const cls = {
    good: "bg-good/15 text-good",
    warn: "bg-warn/15 text-warn",
    bad: "bg-bad/15 text-bad",
    muted: "bg-panel2 text-muted",
  }[tone];
  return (
    <div className="flex items-center justify-between">
      <span className="text-muted">{label}</span>
      <span className={`pill ${cls}`}>{value}</span>
    </div>
  );
}
