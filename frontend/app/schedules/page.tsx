"use client";

import { useState } from "react";
import useSWR from "swr";
import { api, fetcher } from "@/lib/api";

type Job = {
  id: string;
  name: string;
  kind: string;
  cron: string;
  payload: any;
  is_active: boolean;
  last_run_at?: string;
  last_status?: string;
  last_error?: string;
  created_at: string;
};

const KIND_DESCRIPTIONS: Record<string, string> = {
  discovery: "Run all active sources (or a subset via payload.source_ids).",
  enrichment_pending: "Waterfall-enrich any leads with status=pending. payload.limit caps the batch.",
  sheets_sync: "Push leads / outreach / enrichment-runs into Google Sheets. Optional payload.config_id targets a single sync config; otherwise runs all active.",
  crm_sync: "Re-fire lead.created for any leads that haven't been pushed to CRM yet.",
};

const PRESETS = [
  { label: "Every 6 hours", cron: "0 */6 * * *" },
  { label: "Daily 9am UTC", cron: "0 9 * * *" },
  { label: "Hourly", cron: "0 * * * *" },
  { label: "Mon-Fri 10am UTC", cron: "0 10 * * 1-5" },
];

export default function SchedulesPage() {
  const { data, mutate } = useSWR<Job[]>("/api/schedules", fetcher, { refreshInterval: 10000 });
  const [open, setOpen] = useState(false);

  return (
    <div className="space-y-6">
      <header className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold">Schedules</h1>
          <p className="text-muted">Cron-style automation. Replaces n8n for routine jobs.</p>
        </div>
        <button className="btn-primary" onClick={() => setOpen(true)}>+ New schedule</button>
      </header>

      <div className="card">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-muted text-xs uppercase tracking-wider">
              <th className="text-left py-2">Name</th>
              <th className="text-left">Kind</th>
              <th className="text-left">Cron</th>
              <th className="text-left">Active</th>
              <th className="text-left">Last run</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {data?.length === 0 && (
              <tr><td colSpan={6} className="py-6 text-center text-muted">no schedules — discovery + enrichment can run on a cadence here</td></tr>
            )}
            {data?.map((j) => (
              <tr key={j.id} className="border-t border-border">
                <td className="py-2">{j.name}</td>
                <td><span className="pill bg-panel2 text-muted">{j.kind}</span></td>
                <td className="font-mono text-xs">{j.cron}</td>
                <td><span className={`pill ${j.is_active ? "bg-good/15 text-good" : "bg-bad/15 text-bad"}`}>{j.is_active ? "on" : "off"}</span></td>
                <td className="text-xs text-muted">
                  {j.last_run_at ? new Date(j.last_run_at).toLocaleString() : "—"}
                  {j.last_status && <span className="ml-1">({j.last_status})</span>}
                </td>
                <td className="text-right">
                  <button
                    className="btn-ghost text-xs text-bad"
                    onClick={async () => {
                      if (!confirm("Delete schedule?")) return;
                      await api(`/api/schedules/${j.id}`, { method: "DELETE" });
                      mutate();
                    }}
                  >
                    delete
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {open && <Modal onClose={() => setOpen(false)} onCreated={() => { setOpen(false); mutate(); }} />}
    </div>
  );
}

function Modal({ onClose, onCreated }: { onClose: () => void; onCreated: () => void }) {
  const [name, setName] = useState("");
  const [kind, setKind] = useState("discovery");
  const [cron, setCron] = useState("0 */6 * * *");
  const [payload, setPayload] = useState("{}");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center p-4 z-50" onClick={onClose}>
      <div className="card w-full max-w-lg space-y-3" onClick={(e) => e.stopPropagation()}>
        <h2 className="text-xl font-semibold">New schedule</h2>
        <div>
          <label className="label">Name *</label>
          <input className="input" value={name} onChange={(e) => setName(e.target.value)} placeholder="discover every 6h" />
        </div>
        <div>
          <label className="label">Kind</label>
          <select className="input" value={kind} onChange={(e) => setKind(e.target.value)}>
            {Object.keys(KIND_DESCRIPTIONS).map((k) => (
              <option key={k} value={k}>{k}</option>
            ))}
          </select>
          <p className="text-xs text-muted mt-1">{KIND_DESCRIPTIONS[kind]}</p>
        </div>
        <div>
          <label className="label">Cron (UTC, 5-field)</label>
          <input className="input font-mono" value={cron} onChange={(e) => setCron(e.target.value)} />
          <div className="flex flex-wrap gap-1 mt-2">
            {PRESETS.map((p) => (
              <button
                key={p.cron}
                type="button"
                className="text-xs pill bg-panel2 text-muted hover:text-text"
                onClick={() => setCron(p.cron)}
              >
                {p.label}
              </button>
            ))}
          </div>
        </div>
        <div>
          <label className="label">Payload (JSON)</label>
          <textarea className="input font-mono text-xs min-h-[80px]" value={payload} onChange={(e) => setPayload(e.target.value)} placeholder='{"limit": 50}' />
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
                const p = JSON.parse(payload || "{}");
                await api("/api/schedules", {
                  method: "POST",
                  body: JSON.stringify({ name: name.trim(), kind, cron, payload: p, is_active: true }),
                });
                onCreated();
              } catch (e: any) {
                setErr(e.message);
              } finally {
                setBusy(false);
              }
            }}
          >
            Create
          </button>
        </div>
      </div>
    </div>
  );
}
