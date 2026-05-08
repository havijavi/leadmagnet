"use client";

import { useState } from "react";
import useSWR from "swr";
import { api, fetcher } from "@/lib/api";

type Run = {
  id: string;
  source_id?: string;
  status: string;
  pages_crawled: number;
  leads_found: number;
  error_message?: string;
  started_at?: string;
  finished_at?: string;
  created_at: string;
};

type Source = { id: string; name: string; kind: string; is_active: boolean };

export default function DiscoveryPage() {
  const { data: sources } = useSWR<Source[]>("/api/sources", fetcher);
  const { data: runs, mutate: reloadRuns } = useSWR<Run[]>("/api/discovery/runs", fetcher, { refreshInterval: 4000 });
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [extra, setExtra] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [suggested, setSuggested] = useState<string[]>([]);

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-3xl font-bold">Discovery</h1>
        <p className="text-muted">Pick sources, hit run. Optionally drop in URLs ad-hoc.</p>
      </header>

      <div className="card space-y-4">
        <div>
          <h2 className="font-semibold mb-2">Sources</h2>
          <div className="grid md:grid-cols-2 gap-2">
            {sources?.filter((s) => s.is_active).map((s) => (
              <label key={s.id} className="flex items-center gap-2 px-3 py-2 bg-panel2 rounded-lg cursor-pointer">
                <input
                  type="checkbox"
                  checked={selected.has(s.id)}
                  onChange={() => {
                    const next = new Set(selected);
                    next.has(s.id) ? next.delete(s.id) : next.add(s.id);
                    setSelected(next);
                  }}
                />
                <span className="text-sm">{s.name}</span>
                <span className="pill bg-panel text-muted ml-auto">{s.kind}</span>
              </label>
            ))}
          </div>
        </div>

        <div>
          <label className="label">Ad-hoc URLs (one per line, optional)</label>
          <textarea
            className="input font-mono text-xs min-h-[80px]"
            value={extra}
            onChange={(e) => setExtra(e.target.value)}
            placeholder={"https://news.ycombinator.com/item?id=...\nhttps://reddit.com/r/SaaS/comments/..."}
          />
        </div>

        <div className="flex flex-wrap gap-2 items-center">
          <button
            className="btn-primary"
            disabled={busy || (selected.size === 0 && !extra.trim())}
            onClick={async () => {
              setBusy(true);
              setMsg(null);
              try {
                await api("/api/discovery/run", {
                  method: "POST",
                  body: JSON.stringify({
                    source_ids: Array.from(selected),
                    extra_urls: extra.split("\n").map((s) => s.trim()).filter(Boolean),
                  }),
                });
                setMsg("Discovery queued. Watch the runs table below.");
                reloadRuns();
              } catch (e: any) {
                setMsg("Error: " + e.message);
              } finally {
                setBusy(false);
              }
            }}
          >
            {busy ? "Queuing…" : "Run discovery"}
          </button>

          <button
            className="btn-secondary"
            onClick={async () => {
              const r = await api<{ queries: string[] }>("/api/discovery/suggest-queries", { method: "POST" });
              setSuggested(r.queries);
            }}
          >
            Suggest search queries
          </button>

          {msg && <span className="text-sm text-muted">{msg}</span>}
        </div>

        {suggested.length > 0 && (
          <div className="border-t border-border pt-3 text-sm">
            <div className="text-muted text-xs uppercase tracking-wider mb-2">LLM-suggested queries</div>
            <ul className="list-disc list-inside text-muted space-y-1">
              {suggested.map((q) => <li key={q} className="text-text">{q}</li>)}
            </ul>
            <p className="text-muted text-xs mt-2">
              Add these as a <code className="text-text">google</code> source (requires SEARXNG_URL) or paste matching URLs above.
            </p>
          </div>
        )}
      </div>

      <section className="card">
        <h2 className="font-semibold mb-3">Recent runs</h2>
        <div className="overflow-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-muted text-xs uppercase tracking-wider">
                <th className="text-left py-2">Started</th>
                <th className="text-left">Status</th>
                <th className="text-right">Pages</th>
                <th className="text-right">Leads</th>
                <th className="text-left">Error</th>
              </tr>
            </thead>
            <tbody>
              {runs?.map((r) => (
                <tr key={r.id} className="border-t border-border">
                  <td className="py-2">{r.started_at ? new Date(r.started_at).toLocaleString() : new Date(r.created_at).toLocaleString()}</td>
                  <td><StatusPill status={r.status} /></td>
                  <td className="text-right">{r.pages_crawled}</td>
                  <td className="text-right">{r.leads_found}</td>
                  <td className="text-bad text-xs">{r.error_message || ""}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}

function StatusPill({ status }: { status: string }) {
  const tone =
    status === "completed" ? "bg-good/15 text-good" :
    status === "running" ? "bg-warn/15 text-warn" :
    status === "failed" ? "bg-bad/15 text-bad" :
    "bg-panel2 text-muted";
  return <span className={`pill ${tone}`}>{status}</span>;
}
