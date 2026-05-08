"use client";

import { useState } from "react";
import useSWR from "swr";
import { api, fetcher } from "@/lib/api";

type Source = {
  id: string;
  kind: string;
  name: string;
  config: Record<string, any>;
  is_active: boolean;
  last_run_at?: string;
  created_at: string;
};

export default function SourcesPage() {
  const { data, mutate } = useSWR<Source[]>("/api/sources", fetcher);
  const { data: kinds } = useSWR<{ kinds: string[] }>("/api/sources/kinds", fetcher);
  const [open, setOpen] = useState(false);

  return (
    <div className="space-y-6">
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Lead sources</h1>
          <p className="text-muted">Where to look. Each source is fetched, then handed to the LLM extractor.</p>
        </div>
        <button className="btn-primary" onClick={() => setOpen(true)}>+ New source</button>
      </header>

      <div className="grid gap-3">
        {data?.map((s) => (
          <div key={s.id} className="card flex items-start justify-between gap-4">
            <div>
              <div className="flex items-center gap-2">
                <span className="font-semibold">{s.name}</span>
                <span className="pill bg-panel2 text-muted">{s.kind}</span>
                {s.is_active ? (
                  <span className="pill bg-good/15 text-good">active</span>
                ) : (
                  <span className="pill bg-bad/15 text-bad">paused</span>
                )}
              </div>
              <pre className="text-xs text-muted mt-2 whitespace-pre-wrap">
                {JSON.stringify(s.config, null, 2)}
              </pre>
              {s.last_run_at && (
                <div className="text-xs text-muted mt-1">
                  last run: {new Date(s.last_run_at).toLocaleString()}
                </div>
              )}
            </div>
            <button
              className="btn-ghost text-bad"
              onClick={async () => {
                if (!confirm("Delete this source?")) return;
                await api(`/api/sources/${s.id}`, { method: "DELETE" });
                mutate();
              }}
            >
              delete
            </button>
          </div>
        ))}
      </div>

      {open && (
        <Modal
          kinds={kinds?.kinds ?? []}
          onClose={() => setOpen(false)}
          onCreated={() => { setOpen(false); mutate(); }}
        />
      )}
    </div>
  );
}

function Modal({ kinds, onClose, onCreated }: { kinds: string[]; onClose: () => void; onCreated: () => void }) {
  const [kind, setKind] = useState(kinds[0] ?? "url");
  const [name, setName] = useState("");
  const [config, setConfig] = useState(defaultConfigFor(kinds[0] ?? "url"));
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center p-4 z-50">
      <div className="card w-full max-w-lg space-y-3">
        <h2 className="text-xl font-semibold">New source</h2>
        <div>
          <label className="label">Kind</label>
          <select
            className="input"
            value={kind}
            onChange={(e) => {
              setKind(e.target.value);
              setConfig(defaultConfigFor(e.target.value));
            }}
          >
            {kinds.map((k) => (
              <option key={k} value={k}>{k}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="label">Name *</label>
          <input className="input" value={name} onChange={(e) => setName(e.target.value)} placeholder="r/SaaS new posts" />
        </div>
        <div>
          <label className="label">Config (JSON)</label>
          <textarea className="input font-mono text-xs min-h-[120px]" value={config} onChange={(e) => setConfig(e.target.value)} />
        </div>
        {err && <div className="text-bad text-sm">{err}</div>}
        <div className="flex justify-end gap-2 pt-2">
          <button className="btn-secondary" onClick={onClose}>Cancel</button>
          <button
            className="btn-primary"
            disabled={!name.trim() || busy}
            onClick={async () => {
              setBusy(true);
              setErr(null);
              try {
                const cfg = JSON.parse(config || "{}");
                await api("/api/sources", {
                  method: "POST",
                  body: JSON.stringify({ kind, name: name.trim(), config: cfg, is_active: true }),
                });
                onCreated();
              } catch (e: any) {
                setErr(e.message);
              } finally {
                setBusy(false);
              }
            }}
          >
            {busy ? "Saving…" : "Create"}
          </button>
        </div>
      </div>
    </div>
  );
}

function defaultConfigFor(kind: string): string {
  const examples: Record<string, any> = {
    hackernews: { thread: "who_is_hiring", limit: 30 },
    reddit: { subreddit: "SaaS", limit: 50, sort: "new" },
    google: { queries: ["looking for next.js developer"], max_results_per_query: 5 },
    url: { urls: ["https://example.com/jobs"] },
  };
  return JSON.stringify(examples[kind] ?? {}, null, 2);
}
