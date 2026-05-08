"use client";

import { useState } from "react";
import useSWR from "swr";
import { api, fetcher } from "@/lib/api";

type TargetList = {
  id: string;
  name: string;
  description?: string;
  row_count: number;
  created_at: string;
};

const BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function ImportPage() {
  const { data: lists, mutate } = useSWR<TargetList[]>("/api/import/lists", fetcher);
  const [file, setFile] = useState<File | null>(null);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  async function upload() {
    if (!file || !name.trim()) return;
    setBusy(true);
    setMsg(null);
    try {
      const fd = new FormData();
      fd.append("file", file);
      fd.append("name", name.trim());
      if (description.trim()) fd.append("description", description.trim());
      const token = window.localStorage.getItem("admin_token") || "";
      const r = await fetch(`${BASE}/api/import/csv`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
        body: fd,
      });
      const j = await r.json();
      if (!r.ok) throw new Error(j.detail || "upload failed");
      setMsg(`Added ${j.added}, skipped ${j.skipped}.`);
      setFile(null);
      setName("");
      setDescription("");
      mutate();
    } catch (e: any) {
      setMsg("Error: " + e.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-3xl font-bold">Import / Target lists</h1>
        <p className="text-muted">Upload a CSV of prospects to enrich. Recognized columns: name, company, email, website, domain, linkedin, role, location, tags.</p>
      </header>

      <div className="card space-y-3">
        <h2 className="font-semibold">Upload CSV</h2>
        <div className="grid md:grid-cols-2 gap-3">
          <div>
            <label className="label">List name *</label>
            <input className="input" value={name} onChange={(e) => setName(e.target.value)} placeholder="Q2 outbound test" />
          </div>
          <div>
            <label className="label">Description</label>
            <input className="input" value={description} onChange={(e) => setDescription(e.target.value)} placeholder="optional" />
          </div>
        </div>
        <input type="file" accept=".csv" onChange={(e) => setFile(e.target.files?.[0] ?? null)} className="text-sm" />
        <div className="flex gap-2 items-center">
          <button className="btn-primary" disabled={!file || !name.trim() || busy} onClick={upload}>
            {busy ? "Uploading…" : "Upload"}
          </button>
          {msg && <span className="text-sm text-muted">{msg}</span>}
        </div>
      </div>

      <div className="card">
        <h2 className="font-semibold mb-3">Existing lists</h2>
        <table className="w-full text-sm">
          <thead>
            <tr className="text-muted text-xs uppercase tracking-wider">
              <th className="text-left py-2">Name</th>
              <th className="text-left">Description</th>
              <th className="text-right">Rows</th>
              <th className="text-left">Created</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {lists?.length === 0 && (
              <tr><td colSpan={5} className="py-6 text-center text-muted">no lists yet — upload a CSV above</td></tr>
            )}
            {lists?.map((l) => (
              <tr key={l.id} className="border-t border-border">
                <td className="py-2">{l.name}</td>
                <td className="text-muted text-xs">{l.description || ""}</td>
                <td className="text-right font-mono">{l.row_count}</td>
                <td className="text-xs text-muted">{new Date(l.created_at).toLocaleDateString()}</td>
                <td className="text-right">
                  <button
                    className="btn-secondary text-xs"
                    onClick={async () => {
                      await api("/api/enrichment/batch", {
                        method: "POST",
                        body: JSON.stringify({ target_list_id: l.id }),
                      });
                      alert("Enrichment queued for this list");
                    }}
                  >
                    enrich list
                  </button>
                  <button
                    className="btn-ghost text-xs text-bad ml-2"
                    onClick={async () => {
                      if (!confirm("Delete list (leads will be unlinked, not deleted)?")) return;
                      await api(`/api/import/lists/${l.id}`, { method: "DELETE" });
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

      <div className="card">
        <h2 className="font-semibold mb-2">CSV format reference</h2>
        <pre className="text-xs bg-panel2 p-3 rounded overflow-auto">
{`name,company,email,website,linkedin,role,location,tags
Jane Doe,Acme Inc,jane@acme.com,acme.com,https://linkedin.com/in/jane,CTO,Berlin,saas;hot
,BetaCorp,,beta.com,,,Remote,early-stage`}
        </pre>
      </div>
    </div>
  );
}
