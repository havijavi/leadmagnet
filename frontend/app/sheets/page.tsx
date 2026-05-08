"use client";

import { useState } from "react";
import useSWR from "swr";
import { api, fetcher } from "@/lib/api";

type Status = {
  configured: boolean;
  service_account_email?: string;
  setup_hint: string;
};

type Config = {
  id: string;
  name: string;
  spreadsheet_id: string;
  spreadsheet_url?: string;
  worksheet_name: string;
  sync_kind: string;
  filters: Record<string, any>;
  is_active: boolean;
  last_synced_at?: string;
  last_status?: string;
  last_error?: string;
  last_row_count?: number;
  created_at: string;
};

const KIND_LABELS: Record<string, string> = {
  leads: "Leads",
  outreach: "Outreach messages",
  enrichment_runs: "Enrichment runs (audit log)",
};

export default function SheetsPage() {
  const { data: status } = useSWR<Status>("/api/sheets/status", fetcher, { refreshInterval: 15000 });
  const { data: configs, mutate } = useSWR<Config[]>("/api/sheets", fetcher, { refreshInterval: 8000 });
  const [open, setOpen] = useState(false);

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-3xl font-bold">Google Sheets sync</h1>
        <p className="text-muted">Push leads, outreach, and enrichment audit data to your sheets on a schedule or on demand.</p>
      </header>

      <div className="card">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="font-semibold">Service account</h2>
            <p className="text-sm text-muted">{status?.setup_hint}</p>
          </div>
          <span className={`pill ${status?.configured ? "bg-good/15 text-good" : "bg-warn/15 text-warn"}`}>
            {status?.configured ? "ready" : "not configured"}
          </span>
        </div>
        {status?.service_account_email && (
          <div className="mt-3 bg-panel2 rounded-lg px-3 py-2 font-mono text-xs">
            {status.service_account_email}
          </div>
        )}
        <div className="mt-3 text-xs text-muted space-y-1">
          <p>1. Google Cloud Console → enable <code className="text-text">Google Sheets API</code></p>
          <p>2. IAM → Service Accounts → create one → download JSON key</p>
          <p>3. Either inline the JSON in <code className="text-text">GOOGLE_SHEETS_CREDENTIALS_JSON</code>, or drop the file at <code className="text-text">./secrets/google.json</code> and set <code className="text-text">GOOGLE_SHEETS_CREDENTIALS_FILE=/app/secrets/google.json</code></p>
          <p>4. Open each target sheet → Share → add the service account email above as <strong>Editor</strong></p>
          <p>5. Add a sync configuration below</p>
        </div>
      </div>

      <div className="flex justify-between items-center">
        <h2 className="text-xl font-semibold">Sync configurations</h2>
        <div className="flex gap-2">
          <button
            className="btn-secondary"
            disabled={!status?.configured || !configs?.length}
            onClick={async () => {
              try {
                await api("/api/sheets/sync-all", { method: "POST" });
                alert("Sync queued for all active configurations.");
                mutate();
              } catch (e: any) {
                alert(e.message);
              }
            }}
          >
            Sync all now
          </button>
          <button className="btn-primary" onClick={() => setOpen(true)} disabled={!status?.configured}>
            + New config
          </button>
        </div>
      </div>

      <div className="grid gap-3">
        {configs?.length === 0 && (
          <div className="card text-muted text-sm">no sheets configured yet</div>
        )}
        {configs?.map((c) => (
          <div key={c.id} className="card">
            <div className="flex items-start justify-between gap-4">
              <div className="flex-1">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="font-semibold">{c.name}</span>
                  <span className="pill bg-panel2 text-muted">{KIND_LABELS[c.sync_kind] ?? c.sync_kind}</span>
                  <span className="pill bg-panel2 text-muted">tab: {c.worksheet_name}</span>
                  {c.is_active ? (
                    <span className="pill bg-good/15 text-good">active</span>
                  ) : (
                    <span className="pill bg-bad/15 text-bad">paused</span>
                  )}
                </div>
                <div className="text-xs mt-2">
                  {c.spreadsheet_url ? (
                    <a className="text-accent2" href={c.spreadsheet_url} target="_blank" rel="noopener noreferrer">
                      open sheet ↗
                    </a>
                  ) : (
                    <span className="text-muted font-mono">{c.spreadsheet_id}</span>
                  )}
                </div>
                {Object.keys(c.filters || {}).length > 0 && (
                  <div className="text-xs mt-2 text-muted">
                    filters: {JSON.stringify(c.filters)}
                  </div>
                )}
                <div className="text-xs mt-2 text-muted">
                  {c.last_synced_at ? (
                    <>
                      last synced {new Date(c.last_synced_at).toLocaleString()} —
                      <span className={c.last_status === "completed" ? "text-good" : "text-bad"}>
                        {" "}{c.last_status} ({c.last_row_count ?? 0} rows)
                      </span>
                      {c.last_error && <div className="text-bad">{c.last_error}</div>}
                    </>
                  ) : (
                    "never synced"
                  )}
                </div>
              </div>
              <div className="flex flex-col gap-2">
                <button
                  className="btn-primary text-xs"
                  onClick={async () => {
                    try {
                      await api(`/api/sheets/${c.id}/sync`, { method: "POST" });
                      alert("Sync queued — refresh in a few seconds.");
                      mutate();
                    } catch (e: any) {
                      alert(e.message);
                    }
                  }}
                >
                  sync now
                </button>
                <button
                  className="btn-ghost text-xs text-bad"
                  onClick={async () => {
                    if (!confirm("Delete this sync configuration?")) return;
                    await api(`/api/sheets/${c.id}`, { method: "DELETE" });
                    mutate();
                  }}
                >
                  delete
                </button>
              </div>
            </div>
          </div>
        ))}
      </div>

      {open && (
        <Modal onClose={() => setOpen(false)} onCreated={() => { setOpen(false); mutate(); }} />
      )}
    </div>
  );
}

function Modal({ onClose, onCreated }: { onClose: () => void; onCreated: () => void }) {
  const [name, setName] = useState("");
  const [spreadsheetId, setSpreadsheetId] = useState("");
  const [worksheet, setWorksheet] = useState("Leads");
  const [kind, setKind] = useState("leads");
  const [filters, setFilters] = useState("{}");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center p-4 z-50" onClick={onClose}>
      <div className="card w-full max-w-lg space-y-3" onClick={(e) => e.stopPropagation()}>
        <h2 className="text-xl font-semibold">New sync config</h2>
        <div>
          <label className="label">Name *</label>
          <input className="input" value={name} onChange={(e) => setName(e.target.value)} placeholder="Hot leads → operations sheet" />
        </div>
        <div>
          <label className="label">Spreadsheet ID or URL *</label>
          <input
            className="input font-mono text-xs"
            value={spreadsheetId}
            onChange={(e) => setSpreadsheetId(e.target.value)}
            placeholder="1AbCdEfGhIj... or paste full https://docs.google.com/spreadsheets/d/.../edit"
          />
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="label">Sync kind</label>
            <select className="input" value={kind} onChange={(e) => {
              setKind(e.target.value);
              setWorksheet(e.target.value === "leads" ? "Leads" : e.target.value === "outreach" ? "Outreach" : "Enrichment");
            }}>
              {Object.entries(KIND_LABELS).map(([k, l]) => (
                <option key={k} value={k}>{l}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="label">Tab name</label>
            <input className="input" value={worksheet} onChange={(e) => setWorksheet(e.target.value)} />
          </div>
        </div>
        <div>
          <label className="label">Filters (JSON, optional)</label>
          <textarea
            className="input font-mono text-xs min-h-[60px]"
            value={filters}
            onChange={(e) => setFilters(e.target.value)}
            placeholder={kind === "leads" ? '{"min_fit_score": 60, "status": "new"}' : "{}"}
          />
        </div>
        {err && <div className="text-bad text-sm">{err}</div>}
        <div className="flex justify-end gap-2 pt-2">
          <button className="btn-secondary" onClick={onClose}>Cancel</button>
          <button
            className="btn-primary"
            disabled={!name.trim() || !spreadsheetId.trim() || busy}
            onClick={async () => {
              setBusy(true);
              setErr(null);
              try {
                const f = JSON.parse(filters || "{}");
                await api("/api/sheets", {
                  method: "POST",
                  body: JSON.stringify({
                    name: name.trim(),
                    spreadsheet_id: spreadsheetId.trim(),
                    worksheet_name: worksheet.trim(),
                    sync_kind: kind,
                    filters: f,
                    is_active: true,
                  }),
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
