"use client";

import { useState } from "react";
import useSWR from "swr";
import { api, fetcher } from "@/lib/api";

type Lead = {
  id: string;
  name?: string;
  company?: string;
  email?: string;
  website?: string;
  domain?: string;
  linkedin_url?: string;
  role?: string;
  project_summary?: string;
  source_url?: string;
  fit_score: number;
  urgency: string;
  status: string;
  qualification_notes?: string;
  raw_excerpt?: string;
  enrichment_status: string;
  enrichment_data?: any;
  research_summary?: string;
  research_data?: any;
  tags: string[];
  created_at: string;
};

export default function LeadsPage() {
  const [status, setStatus] = useState<string>("");
  const [minScore, setMinScore] = useState(0);
  const url = `/api/leads?min_score=${minScore}${status ? `&status=${status}` : ""}`;
  const { data, mutate } = useSWR<Lead[]>(url, fetcher, { refreshInterval: 8000 });
  const [active, setActive] = useState<Lead | null>(null);

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-3xl font-bold">Leads</h1>
        <p className="text-muted">Sorted by fit score. Click for detail and outreach.</p>
      </header>

      <div className="card flex items-center gap-3 flex-wrap">
        <div>
          <label className="label">Status</label>
          <select className="input" value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="">all</option>
            {["new", "reviewed", "contacted", "replied", "won", "lost", "trash"].map((s) => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="label">Min fit score</label>
          <input type="number" min={0} max={100} className="input w-24" value={minScore} onChange={(e) => setMinScore(Number(e.target.value) || 0)} />
        </div>
      </div>

      <div className="card">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-muted text-xs uppercase tracking-wider">
              <th className="text-left py-2">Name</th>
              <th className="text-left">Project</th>
              <th className="text-right">Fit</th>
              <th className="text-left">Urgency</th>
              <th className="text-left">Status</th>
              <th className="text-left">Found</th>
            </tr>
          </thead>
          <tbody>
            {data?.length === 0 && (
              <tr><td colSpan={6} className="py-6 text-muted text-center">no leads yet — run discovery</td></tr>
            )}
            {data?.map((l) => (
              <tr key={l.id} className="border-t border-border hover:bg-panel2 cursor-pointer" onClick={() => setActive(l)}>
                <td className="py-2">
                  <div className="font-medium">{l.name || l.company || "—"}</div>
                  <div className="text-xs text-muted">{l.email || l.website || ""}</div>
                </td>
                <td className="max-w-xs">
                  <div className="truncate">{l.project_summary}</div>
                </td>
                <td className="text-right font-mono">
                  <span className={l.fit_score >= 70 ? "text-good" : l.fit_score >= 40 ? "text-warn" : "text-muted"}>
                    {l.fit_score}
                  </span>
                </td>
                <td><span className="pill bg-panel2 text-muted">{l.urgency}</span></td>
                <td><span className="pill bg-panel2 text-muted">{l.status}</span></td>
                <td className="text-xs text-muted">{new Date(l.created_at).toLocaleDateString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {active && <LeadDrawer lead={active} onClose={() => setActive(null)} onChanged={() => mutate()} />}
    </div>
  );
}

function LeadDrawer({ lead, onClose, onChanged }: { lead: Lead; onClose: () => void; onChanged: () => void }) {
  const [drafting, setDrafting] = useState(false);
  const [msg, setMsg] = useState<{ id?: string; subject?: string; body?: string; status?: string } | null>(null);
  const [emailVal, setEmailVal] = useState(lead.email || "");
  const [savingEmail, setSavingEmail] = useState(false);
  const [sendErr, setSendErr] = useState<string | null>(null);
  const [busyOp, setBusyOp] = useState<string | null>(null);
  const [opMsg, setOpMsg] = useState<string | null>(null);

  return (
    <div className="fixed inset-0 bg-black/60 flex justify-end z-50" onClick={onClose}>
      <div
        className="bg-panel border-l border-border w-full max-w-2xl h-full overflow-auto p-6 space-y-5"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 className="text-2xl font-bold">{lead.name || lead.company || "Lead"}</h2>
            <div className="text-muted text-sm">{lead.role} {lead.company ? `@ ${lead.company}` : ""}</div>
          </div>
          <button className="btn-ghost" onClick={onClose}>close</button>
        </div>

        <div className="grid grid-cols-2 gap-2 text-sm">
          <Field label="Fit score" value={String(lead.fit_score)} />
          <Field label="Urgency" value={lead.urgency} />
          <Field label="Status" value={lead.status} />
          <Field label="Enrichment" value={lead.enrichment_status} />
          <Field label="Website" value={lead.website || "—"} link={lead.website} />
          <Field label="LinkedIn" value={lead.linkedin_url || "—"} link={lead.linkedin_url} />
        </div>

        <div className="card flex flex-wrap gap-2 items-center">
          <button
            className="btn-secondary text-xs"
            disabled={busyOp === "enrich"}
            onClick={async () => {
              setBusyOp("enrich");
              setOpMsg(null);
              try {
                const r = await api<any>("/api/enrichment/run", { method: "POST", body: JSON.stringify({ lead_id: lead.id }) });
                setOpMsg(`Enrichment: ${r.status}, providers hit: ${(r.providers_hit || []).join(", ") || "none"}`);
                onChanged();
              } catch (e: any) {
                setOpMsg("Error: " + e.message);
              } finally {
                setBusyOp(null);
              }
            }}
          >
            {busyOp === "enrich" ? "enriching…" : "Run waterfall enrichment"}
          </button>
          <button
            className="btn-secondary text-xs"
            disabled={busyOp === "research"}
            onClick={async () => {
              setBusyOp("research");
              setOpMsg(null);
              try {
                await api("/api/research/run", { method: "POST", body: JSON.stringify({ lead_id: lead.id, deep: true }) });
                setOpMsg("Research complete — see panel below.");
                onChanged();
              } catch (e: any) {
                setOpMsg("Error: " + e.message);
              } finally {
                setBusyOp(null);
              }
            }}
          >
            {busyOp === "research" ? "researching…" : "AI research (deep)"}
          </button>
          {opMsg && <span className="text-xs text-muted">{opMsg}</span>}
        </div>

        <div className="card">
          <div className="text-xs text-muted uppercase">Project</div>
          <p className="mt-1">{lead.project_summary}</p>
          {lead.qualification_notes && (
            <p className="text-xs text-muted mt-2 italic">{lead.qualification_notes}</p>
          )}
          {lead.source_url && (
            <a className="text-accent2 text-xs mt-2 inline-block" href={lead.source_url} target="_blank" rel="noopener noreferrer">
              source ↗
            </a>
          )}
        </div>

        {lead.research_summary && (
          <div className="card">
            <div className="text-xs text-muted uppercase">AI research</div>
            <p className="mt-1 text-sm">{lead.research_summary}</p>
            {lead.research_data && (
              <details className="mt-2">
                <summary className="text-xs text-muted cursor-pointer">full dossier</summary>
                <pre className="text-xs mt-2 whitespace-pre-wrap text-muted overflow-auto max-h-60">
                  {JSON.stringify(lead.research_data, null, 2)}
                </pre>
              </details>
            )}
          </div>
        )}

        <div className="card">
          <div className="text-xs text-muted uppercase">Raw excerpt</div>
          <pre className="mt-2 text-xs whitespace-pre-wrap text-muted max-h-48 overflow-auto">{lead.raw_excerpt}</pre>
        </div>

        <div className="card space-y-3">
          <div className="text-xs text-muted uppercase">Outreach</div>
          <div className="flex gap-2 items-end">
            <div className="flex-1">
              <label className="label">Recipient email</label>
              <input className="input" value={emailVal} onChange={(e) => setEmailVal(e.target.value)} />
            </div>
            <button
              className="btn-secondary"
              disabled={savingEmail || emailVal === (lead.email || "")}
              onClick={async () => {
                setSavingEmail(true);
                await api(`/api/leads/${lead.id}`, { method: "PATCH", body: JSON.stringify({ email: emailVal }) });
                setSavingEmail(false);
                onChanged();
              }}
            >
              save
            </button>
          </div>
          <button
            className="btn-primary"
            disabled={drafting}
            onClick={async () => {
              setDrafting(true);
              setSendErr(null);
              try {
                const draft = await api<any>("/api/campaigns/draft", {
                  method: "POST",
                  body: JSON.stringify({ lead_id: lead.id, tone: "friendly" }),
                });
                setMsg(draft);
              } catch (e: any) {
                setSendErr(e.message);
              } finally {
                setDrafting(false);
              }
            }}
          >
            {drafting ? "Drafting…" : "Draft outreach with LLM"}
          </button>

          {msg && (
            <div className="space-y-2">
              <div>
                <label className="label">Subject</label>
                <input className="input" value={msg.subject || ""} onChange={(e) => setMsg({ ...msg, subject: e.target.value })} />
              </div>
              <div>
                <label className="label">Body</label>
                <textarea className="input min-h-[200px]" value={msg.body || ""} onChange={(e) => setMsg({ ...msg, body: e.target.value })} />
              </div>
              <div className="flex gap-2 justify-end">
                <button
                  className="btn-secondary"
                  onClick={async () => {
                    if (!msg.id) return;
                    await api(`/api/campaigns/${msg.id}`, {
                      method: "PATCH",
                      body: JSON.stringify({ subject: msg.subject, body: msg.body }),
                    });
                  }}
                >
                  save draft
                </button>
                <button
                  className="btn-primary"
                  onClick={async () => {
                    if (!msg.id) return;
                    setSendErr(null);
                    try {
                      await api(`/api/campaigns/${msg.id}`, {
                        method: "PATCH",
                        body: JSON.stringify({ subject: msg.subject, body: msg.body }),
                      });
                      await api(`/api/campaigns/${msg.id}/send`, { method: "POST" });
                      setMsg({ ...msg, status: "sent" });
                      onChanged();
                    } catch (e: any) {
                      setSendErr(e.message);
                    }
                  }}
                >
                  send via SMTP
                </button>
              </div>
              {msg.status === "sent" && <div className="text-good text-sm">sent ✓</div>}
              {sendErr && <div className="text-bad text-sm">{sendErr}</div>}
            </div>
          )}
        </div>

        <div className="flex gap-2 justify-between pt-2 border-t border-border">
          {["reviewed", "contacted", "won", "lost", "trash"].map((s) => (
            <button
              key={s}
              className="btn-ghost text-xs"
              onClick={async () => {
                await api(`/api/leads/${lead.id}`, { method: "PATCH", body: JSON.stringify({ status: s }) });
                onChanged();
                onClose();
              }}
            >
              mark {s}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

function Field({ label, value, link }: { label: string; value: string; link?: string }) {
  return (
    <div>
      <div className="text-xs text-muted">{label}</div>
      {link ? (
        <a href={link} target="_blank" rel="noopener noreferrer" className="text-accent2 break-all">{value}</a>
      ) : (
        <div className="break-all">{value}</div>
      )}
    </div>
  );
}
