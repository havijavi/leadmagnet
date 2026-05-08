"use client";

import { useState } from "react";
import useSWR from "swr";
import { api, fetcher } from "@/lib/api";

type Webhook = {
  id: string;
  name: string;
  url: string;
  events: string[];
  headers: Record<string, string>;
  body_template?: string;
  is_active: boolean;
  last_fired_at?: string;
  last_status_code?: number;
  last_error?: string;
  created_at: string;
};

const ALL_EVENTS = [
  "lead.created",
  "lead.enriched",
  "lead.contacted",
  "lead.replied",
  "lead.won",
  "lead.lost",
  "lead.trash",
  "lead.reviewed",
];

export default function CrmPage() {
  const { data, mutate } = useSWR<Webhook[]>("/api/crm", fetcher, { refreshInterval: 8000 });
  const [open, setOpen] = useState(false);

  return (
    <div className="space-y-6">
      <header className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold">CRM webhooks</h1>
          <p className="text-muted">POST lead events to HubSpot, Pipedrive, Slack, or any URL that accepts JSON.</p>
        </div>
        <button className="btn-primary" onClick={() => setOpen(true)}>+ New webhook</button>
      </header>

      <div className="card">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-muted text-xs uppercase tracking-wider">
              <th className="text-left py-2">Name</th>
              <th className="text-left">URL</th>
              <th className="text-left">Events</th>
              <th className="text-left">Last fired</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {data?.length === 0 && (
              <tr><td colSpan={5} className="py-6 text-center text-muted">no webhooks — set one up to push leads to your CRM</td></tr>
            )}
            {data?.map((w) => (
              <tr key={w.id} className="border-t border-border">
                <td className="py-2">{w.name}</td>
                <td className="text-xs text-muted truncate max-w-xs">{w.url}</td>
                <td className="text-xs">
                  {w.events.map((e) => <span key={e} className="pill bg-panel2 text-muted mr-1">{e}</span>)}
                </td>
                <td className="text-xs">
                  {w.last_fired_at ? (
                    <span>
                      {new Date(w.last_fired_at).toLocaleString()}
                      <span className={w.last_status_code && w.last_status_code < 400 ? "text-good ml-1" : "text-bad ml-1"}>
                        ({w.last_status_code ?? "?"})
                      </span>
                    </span>
                  ) : "—"}
                  {w.last_error && <div className="text-bad">{w.last_error}</div>}
                </td>
                <td className="text-right">
                  <button
                    className="btn-secondary text-xs"
                    onClick={async () => {
                      try {
                        await api(`/api/crm/${w.id}/test`, { method: "POST" });
                        alert("Test fired — check 'Last fired' column.");
                        mutate();
                      } catch (e: any) {
                        alert(e.message);
                      }
                    }}
                  >
                    test
                  </button>
                  <button
                    className="btn-ghost text-xs text-bad ml-2"
                    onClick={async () => {
                      if (!confirm("Delete webhook?")) return;
                      await api(`/api/crm/${w.id}`, { method: "DELETE" });
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
  const [url, setUrl] = useState("");
  const [events, setEvents] = useState<Set<string>>(new Set(["lead.created", "lead.contacted", "lead.replied", "lead.won"]));
  const [secret, setSecret] = useState("");
  const [headers, setHeaders] = useState("{}");
  const [bodyTpl, setBodyTpl] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center p-4 z-50" onClick={onClose}>
      <div className="card w-full max-w-xl space-y-3" onClick={(e) => e.stopPropagation()}>
        <h2 className="text-xl font-semibold">New CRM webhook</h2>
        <div>
          <label className="label">Name *</label>
          <input className="input" value={name} onChange={(e) => setName(e.target.value)} placeholder="HubSpot deals" />
        </div>
        <div>
          <label className="label">URL *</label>
          <input className="input" value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://hooks.zapier.com/..." />
        </div>
        <div>
          <label className="label">Events</label>
          <div className="flex flex-wrap gap-1">
            {ALL_EVENTS.map((e) => (
              <button
                key={e}
                type="button"
                className={`pill ${events.has(e) ? "bg-accent text-white" : "bg-panel2 text-muted"}`}
                onClick={() => {
                  const next = new Set(events);
                  next.has(e) ? next.delete(e) : next.add(e);
                  setEvents(next);
                }}
              >
                {e}
              </button>
            ))}
          </div>
        </div>
        <div>
          <label className="label">Secret (optional, used for HMAC SHA256 signature header)</label>
          <input className="input" value={secret} onChange={(e) => setSecret(e.target.value)} type="password" />
        </div>
        <div>
          <label className="label">Custom headers (JSON, optional)</label>
          <textarea className="input font-mono text-xs min-h-[60px]" value={headers} onChange={(e) => setHeaders(e.target.value)} />
        </div>
        <div>
          <label className="label">Body template (optional). Use {`{{lead.field}}`} substitutions.</label>
          <textarea
            className="input font-mono text-xs min-h-[100px]"
            value={bodyTpl}
            onChange={(e) => setBodyTpl(e.target.value)}
            placeholder={`{\n  "name": "{{lead.name}}",\n  "email": "{{lead.email}}",\n  "score": "{{lead.fit_score}}"\n}`}
          />
        </div>
        {err && <div className="text-bad text-sm">{err}</div>}
        <div className="flex justify-end gap-2 pt-2">
          <button className="btn-secondary" onClick={onClose}>Cancel</button>
          <button
            className="btn-primary"
            disabled={!name.trim() || !url.trim() || busy}
            onClick={async () => {
              setBusy(true);
              setErr(null);
              try {
                const h = JSON.parse(headers || "{}");
                await api("/api/crm", {
                  method: "POST",
                  body: JSON.stringify({
                    name: name.trim(),
                    url: url.trim(),
                    events: Array.from(events),
                    secret: secret || null,
                    headers: h,
                    body_template: bodyTpl || null,
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
