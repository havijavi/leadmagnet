"use client";

import { useState } from "react";
import useSWR from "swr";
import { api, fetcher } from "@/lib/api";

type Service = {
  id: string;
  name: string;
  description?: string;
  keywords: string[];
  target_industries: string[];
  min_budget_usd?: number;
  is_active: boolean;
  created_at: string;
};

export default function ServicesPage() {
  const { data, mutate } = useSWR<Service[]>("/api/services", fetcher);
  const [open, setOpen] = useState(false);

  return (
    <div className="space-y-6">
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Service offerings</h1>
          <p className="text-muted">What you sell. The LLM uses these to extract & qualify leads.</p>
        </div>
        <button className="btn-primary" onClick={() => setOpen(true)}>+ New service</button>
      </header>

      <div className="grid gap-3">
        {data?.length === 0 && (
          <div className="card text-muted">
            No services yet. Add one — e.g. <code className="text-text">Next.js + Stripe SaaS MVPs in 4 weeks</code>.
          </div>
        )}
        {data?.map((s) => (
          <div key={s.id} className="card">
            <div className="flex items-start justify-between gap-4">
              <div>
                <div className="font-semibold text-lg">{s.name}</div>
                {s.description && <p className="text-sm text-muted mt-1">{s.description}</p>}
                <div className="flex flex-wrap gap-1 mt-2">
                  {s.keywords?.map((k) => (
                    <span key={k} className="pill bg-panel2 text-muted">{k}</span>
                  ))}
                </div>
              </div>
              <div className="flex gap-2">
                <button
                  className="btn-ghost text-bad"
                  onClick={async () => {
                    if (!confirm("Delete this service?")) return;
                    await api(`/api/services/${s.id}`, { method: "DELETE" });
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
  const [description, setDescription] = useState("");
  const [keywords, setKeywords] = useState("");
  const [budget, setBudget] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center p-4 z-50">
      <div className="card w-full max-w-lg space-y-3">
        <h2 className="text-xl font-semibold">New service</h2>
        <div>
          <label className="label">Name *</label>
          <input className="input" value={name} onChange={(e) => setName(e.target.value)} placeholder="Next.js + AI MVP development" />
        </div>
        <div>
          <label className="label">Description</label>
          <textarea className="input min-h-[80px]" value={description} onChange={(e) => setDescription(e.target.value)} placeholder="What problem you solve, who you solve it for." />
        </div>
        <div>
          <label className="label">Keywords (comma separated)</label>
          <input className="input" value={keywords} onChange={(e) => setKeywords(e.target.value)} placeholder="next.js, react, openai, langchain" />
        </div>
        <div>
          <label className="label">Min budget USD</label>
          <input className="input" type="number" value={budget} onChange={(e) => setBudget(e.target.value)} placeholder="optional" />
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
                await api("/api/services", {
                  method: "POST",
                  body: JSON.stringify({
                    name: name.trim(),
                    description: description.trim() || null,
                    keywords: keywords.split(",").map((k) => k.trim()).filter(Boolean),
                    target_industries: [],
                    min_budget_usd: budget ? Number(budget) : null,
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
            {busy ? "Saving…" : "Create"}
          </button>
        </div>
      </div>
    </div>
  );
}
