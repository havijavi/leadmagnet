"use client";

import useSWR from "swr";
import { fetcher } from "@/lib/api";

type Msg = {
  id: string;
  lead_id: string;
  subject?: string;
  body: string;
  status: string;
  sent_at?: string;
  error_message?: string;
  created_at: string;
};

export default function CampaignsPage() {
  const { data } = useSWR<Msg[]>("/api/campaigns", fetcher, { refreshInterval: 8000 });

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-3xl font-bold">Outreach messages</h1>
        <p className="text-muted">Drafts, sends, failures.</p>
      </header>

      <div className="card">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-muted text-xs uppercase tracking-wider">
              <th className="text-left py-2">Subject</th>
              <th className="text-left">Status</th>
              <th className="text-left">Sent</th>
              <th className="text-left">Error</th>
            </tr>
          </thead>
          <tbody>
            {data?.length === 0 && (
              <tr><td colSpan={4} className="py-6 text-muted text-center">no messages yet</td></tr>
            )}
            {data?.map((m) => (
              <tr key={m.id} className="border-t border-border">
                <td className="py-2">{m.subject || "(no subject)"}</td>
                <td><span className={`pill ${pill(m.status)}`}>{m.status}</span></td>
                <td className="text-xs text-muted">{m.sent_at ? new Date(m.sent_at).toLocaleString() : ""}</td>
                <td className="text-xs text-bad">{m.error_message || ""}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function pill(status: string) {
  if (status === "sent") return "bg-good/15 text-good";
  if (status === "failed") return "bg-bad/15 text-bad";
  if (status === "draft") return "bg-warn/15 text-warn";
  return "bg-panel2 text-muted";
}
