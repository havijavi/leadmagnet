"use client";

import { useState } from "react";
import useSWR from "swr";
import { api, fetcher } from "@/lib/api";

type Provider = { name: string; configured: boolean; fields: string[] };
type Run = {
  id: string;
  lead_id?: string;
  providers_tried: string[];
  providers_hit: string[];
  fields_filled: string[];
  status: string;
  error_message?: string;
  created_at: string;
};

export default function EnrichmentPage() {
  const { data: providers } = useSWR<{ providers: Provider[] }>("/api/enrichment/providers", fetcher);
  const { data: runs, mutate } = useSWR<Run[]>("/api/enrichment/runs", fetcher, { refreshInterval: 5000 });
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  // Ad-hoc enrichment form
  const [form, setForm] = useState({ name: "", company: "", email: "", domain: "", linkedin_url: "" });
  const [adhoc, setAdhoc] = useState<any>(null);

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-3xl font-bold">Enrichment</h1>
        <p className="text-muted">Waterfall: website → Hunter.io → Snov.io → DeepSeek/Qwen research.</p>
      </header>

      <div className="card">
        <h2 className="font-semibold mb-2">Configured providers</h2>
        <div className="grid md:grid-cols-2 gap-2">
          {providers?.providers?.map((p) => (
            <div key={p.name} className="flex items-center justify-between bg-panel2 px-3 py-2 rounded-lg">
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
      </div>

      <div className="card space-y-3">
        <h2 className="font-semibold">Bulk enrichment</h2>
        <p className="text-sm text-muted">Run the waterfall over every lead with <code className="text-text">enrichment_status = pending</code>. Limited to 50 per click; schedule it for full automation.</p>
        <button
          className="btn-primary"
          disabled={busy}
          onClick={async () => {
            setBusy(true);
            setMsg(null);
            try {
              const r = await api<any>("/api/enrichment/batch", { method: "POST", body: JSON.stringify({ only_pending: true }) });
              setMsg(`Queued ${r.count}`);
              mutate();
            } catch (e: any) {
              setMsg("Error: " + e.message);
            } finally {
              setBusy(false);
            }
          }}
        >
          {busy ? "Queuing…" : "Enrich pending leads"}
        </button>
        {msg && <span className="text-sm text-muted ml-2">{msg}</span>}
      </div>

      <div className="card space-y-3">
        <h2 className="font-semibold">Ad-hoc enrichment</h2>
        <p className="text-sm text-muted">Test the waterfall against a single prospect without saving.</p>
        <div className="grid md:grid-cols-2 gap-3">
          {(["name", "company", "email", "domain", "linkedin_url"] as const).map((f) => (
            <div key={f}>
              <label className="label">{f}</label>
              <input
                className="input"
                value={(form as any)[f]}
                onChange={(e) => setForm({ ...form, [f]: e.target.value })}
              />
            </div>
          ))}
        </div>
        <button
          className="btn-primary"
          onClick={async () => {
            setAdhoc(null);
            const r = await api<any>("/api/enrichment/run", { method: "POST", body: JSON.stringify(form) });
            setAdhoc(r);
          }}
        >
          Run waterfall
        </button>
        {adhoc && (
          <pre className="text-xs bg-panel2 p-3 rounded overflow-auto max-h-80">
            {JSON.stringify(adhoc, null, 2)}
          </pre>
        )}
      </div>

      <div className="card">
        <h2 className="font-semibold mb-3">Recent enrichment runs</h2>
        <table className="w-full text-sm">
          <thead>
            <tr className="text-muted text-xs uppercase tracking-wider">
              <th className="text-left py-2">When</th>
              <th className="text-left">Status</th>
              <th className="text-left">Providers hit</th>
              <th className="text-left">Fields filled</th>
              <th className="text-left">Error</th>
            </tr>
          </thead>
          <tbody>
            {runs?.length === 0 && (
              <tr><td colSpan={5} className="py-6 text-center text-muted">no runs yet</td></tr>
            )}
            {runs?.map((r) => (
              <tr key={r.id} className="border-t border-border">
                <td className="py-2 text-xs text-muted">{new Date(r.created_at).toLocaleString()}</td>
                <td><span className={`pill ${pillForStatus(r.status)}`}>{r.status}</span></td>
                <td className="text-xs">{r.providers_hit.join(", ") || "—"}</td>
                <td className="text-xs text-muted">{r.fields_filled.join(", ") || "—"}</td>
                <td className="text-xs text-bad">{r.error_message || ""}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function pillForStatus(s: string) {
  if (s === "completed") return "bg-good/15 text-good";
  if (s === "partial") return "bg-warn/15 text-warn";
  if (s === "failed") return "bg-bad/15 text-bad";
  return "bg-panel2 text-muted";
}
