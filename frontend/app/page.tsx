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
};

type Health = {
  llm_provider: string;
  llm_model: string;
  llm_mock_mode: boolean;
  smtp_configured: boolean;
  telegram_configured: boolean;
  webhook_configured: boolean;
};

export default function Dashboard() {
  const { data: stats } = useSWR<Stats>("/api/stats", fetcher, { refreshInterval: 5000 });
  const { data: health } = useSWR<Health>("/health", fetcher, { refreshInterval: 10000 });

  return (
    <div className="space-y-8">
      <header>
        <h1 className="text-3xl font-bold">Dashboard</h1>
        <p className="text-muted">Lead generation, at a glance.</p>
      </header>

      <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
        <Stat label="Leads total" value={stats?.leads_total} />
        <Stat label="High-fit leads" value={stats?.high_fit_count} accent />
        <Stat label="New (untouched)" value={stats?.leads_new} />
        <Stat label="Contacted" value={stats?.leads_contacted} />
        <Stat label="Replied" value={stats?.leads_replied} />
        <Stat label="Discovery runs (24h)" value={stats?.discovery_runs_24h} />
      </div>

      <section className="card">
        <h2 className="text-xl font-semibold mb-3">System</h2>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-3 text-sm">
          <Pill label="LLM provider" value={health?.llm_provider ?? "—"} />
          <Pill label="Model" value={health?.llm_model ?? "—"} />
          <Pill
            label="LLM mode"
            value={health?.llm_mock_mode ? "MOCK (no key)" : "LIVE"}
            tone={health?.llm_mock_mode ? "warn" : "good"}
          />
          <Pill label="SMTP" value={health?.smtp_configured ? "ready" : "not configured"} tone={health?.smtp_configured ? "good" : "muted"} />
          <Pill label="Telegram" value={health?.telegram_configured ? "ready" : "not configured"} tone={health?.telegram_configured ? "good" : "muted"} />
          <Pill label="Webhook" value={health?.webhook_configured ? "ready" : "not configured"} tone={health?.webhook_configured ? "good" : "muted"} />
        </div>
      </section>

      <section className="card">
        <h2 className="text-xl font-semibold mb-3">Get started</h2>
        <ol className="space-y-2 text-sm list-decimal list-inside text-muted">
          <li>
            <Link className="text-accent2" href="/services">Add a service offering</Link>
            {" "}— what you sell. Be specific (e.g. "Next.js + Stripe SaaS MVPs in 4 weeks").
          </li>
          <li>
            <Link className="text-accent2" href="/sources">Pick or add lead sources</Link>
            {" "}— HN, Reddit, custom URLs.
          </li>
          <li>
            <Link className="text-accent2" href="/discovery">Trigger a discovery run</Link>
            {" "}— LeadMagnet scrapes, extracts, qualifies, notifies.
          </li>
          <li>
            <Link className="text-accent2" href="/leads">Review leads</Link>, draft outreach, hit send.
          </li>
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
