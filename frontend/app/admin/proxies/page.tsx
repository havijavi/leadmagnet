"use client";

import { useState } from "react";
import useSWR from "swr";
import { useAuth } from "@/components/AuthGate";
import { api, fetcher } from "@/lib/api";

type Proxy = {
  id: string;
  label: string;
  url_preview: string;
  is_active: boolean;
  success_count: number;
  failure_count: number;
  last_used_at?: string;
  last_failure_at?: string;
  last_error?: string;
  created_at: string;
};

type PoolStatus = {
  total: number;
  active: number;
  in_cooldown: number;
  in_use_recently: number;
};

export default function ProxiesPage() {
  const { user } = useAuth();
  const { data: proxies, mutate } = useSWR<Proxy[]>("/api/proxies", fetcher, {
    refreshInterval: 8000,
  });
  const { data: status, mutate: mutateStatus } = useSWR<PoolStatus>(
    "/api/proxies/status",
    fetcher,
    { refreshInterval: 8000 },
  );
  const [newOpen, setNewOpen] = useState(false);
  const [bulkOpen, setBulkOpen] = useState(false);

  if (user?.role !== "admin") {
    return (
      <div className="card text-muted">
        Admin access required. You are signed in as <strong>{user?.role}</strong>.
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Proxies</h1>
          <p className="text-muted">
            HTTP/HTTPS proxies the crawler rotates through (least-recently-used). When a
            proxy fails, it's put in a 30-min cooldown automatically. If no proxies are
            configured, the crawler runs direct.
          </p>
        </div>
        <div className="flex gap-2">
          <button className="btn-secondary" onClick={() => setBulkOpen(true)}>
            Bulk import
          </button>
          <button className="btn-primary" onClick={() => setNewOpen(true)}>
            + New proxy
          </button>
        </div>
      </header>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard label="Total" value={status?.total} />
        <StatCard label="Active" value={status?.active} accent />
        <StatCard label="In cooldown" value={status?.in_cooldown} tone={status?.in_cooldown ? "warn" : "muted"} />
        <StatCard label="Used last 5 min" value={status?.in_use_recently} />
      </div>

      <div className="grid gap-3">
        {proxies?.length === 0 && (
          <div className="card text-muted text-sm">
            No proxies yet. Without proxies the crawler hits target sites from this VPS's
            IP — fine for low volume, will get rate-limited or blocked at scale. Use{" "}
            <strong>Bulk import</strong> to paste 10 URLs at once.
          </div>
        )}
        {proxies?.map((p) => (
          <ProxyRow
            key={p.id}
            proxy={p}
            onChanged={() => {
              mutate();
              mutateStatus();
            }}
          />
        ))}
      </div>

      <div className="card text-xs text-muted">
        <strong>URL format:</strong>{" "}
        <code className="text-text">http://username:password@host:port</code> for
        authenticated HTTP/HTTPS proxies (the most common kind from paid services like
        Oxylabs, SmartProxy, Webshare). For bare proxies use{" "}
        <code className="text-text">http://host:port</code>. SOCKS5 is supported via{" "}
        <code className="text-text">socks5://...</code> but requires httpx[socks] (already
        installed). Test each proxy after adding — the test endpoint hits api.ipify.org
        through it and shows you the exit IP.
      </div>

      {newOpen && (
        <NewModal
          onClose={() => setNewOpen(false)}
          onCreated={() => {
            setNewOpen(false);
            mutate();
            mutateStatus();
          }}
        />
      )}
      {bulkOpen && (
        <BulkModal
          onClose={() => setBulkOpen(false)}
          onCreated={() => {
            setBulkOpen(false);
            mutate();
            mutateStatus();
          }}
        />
      )}
    </div>
  );
}

function StatCard({
  label,
  value,
  accent = false,
  tone,
}: {
  label: string;
  value?: number;
  accent?: boolean;
  tone?: "good" | "warn" | "bad" | "muted";
}) {
  let toneCls = "";
  if (accent) toneCls = "text-accent2";
  else if (tone === "warn") toneCls = "text-warn";
  else if (tone === "bad") toneCls = "text-bad";
  else if (tone === "good") toneCls = "text-good";
  return (
    <div className="card">
      <div className="text-xs text-muted">{label}</div>
      <div className={`text-3xl font-semibold ${toneCls}`}>{value ?? "—"}</div>
    </div>
  );
}

function ProxyRow({ proxy, onChanged }: { proxy: Proxy; onChanged: () => void }) {
  const [busy, setBusy] = useState<string | null>(null);
  const [testMsg, setTestMsg] = useState<string | null>(null);
  const successRate =
    proxy.success_count + proxy.failure_count > 0
      ? Math.round((proxy.success_count / (proxy.success_count + proxy.failure_count)) * 100)
      : null;
  const inCooldown =
    proxy.last_failure_at &&
    new Date(proxy.last_failure_at).getTime() > Date.now() - 30 * 60 * 1000;

  return (
    <div className="card">
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-semibold">{proxy.label}</span>
            {proxy.is_active ? (
              <span className="pill bg-good/15 text-good">active</span>
            ) : (
              <span className="pill bg-bad/15 text-bad">disabled</span>
            )}
            {inCooldown && <span className="pill bg-warn/15 text-warn">in cooldown</span>}
            {successRate !== null && (
              <span className="pill bg-panel2 text-muted">
                {successRate}% ok ({proxy.success_count} / {proxy.success_count + proxy.failure_count})
              </span>
            )}
          </div>
          <div className="text-xs text-muted mt-1 font-mono break-all">{proxy.url_preview}</div>
          {proxy.last_used_at && (
            <div className="text-xs text-muted mt-1">
              last used: {new Date(proxy.last_used_at).toLocaleString()}
            </div>
          )}
          {proxy.last_error && (
            <div className="text-xs text-bad mt-1">last error: {proxy.last_error}</div>
          )}
          {testMsg && <div className="text-xs mt-2">{testMsg}</div>}
        </div>
        <div className="flex flex-col gap-2 shrink-0">
          <button
            className="btn-secondary text-xs"
            disabled={busy !== null}
            onClick={async () => {
              setBusy("test");
              setTestMsg("testing…");
              try {
                const r = await api<any>("/api/proxies/test", {
                  method: "POST",
                  body: JSON.stringify({ proxy_id: proxy.id }),
                });
                setTestMsg(
                  r.ok
                    ? `✓ OK (${r.elapsed_ms} ms) — exit IP: ${r.exit_ip}`
                    : `✗ FAIL (${r.elapsed_ms} ms): ${r.error}`,
                );
                onChanged();
              } catch (e: any) {
                setTestMsg(`✗ FAIL: ${e.message}`);
              } finally {
                setBusy(null);
              }
            }}
          >
            {busy === "test" ? "Testing…" : "Test"}
          </button>
          <button
            className="btn-ghost text-xs"
            disabled={busy !== null}
            onClick={async () => {
              setBusy("toggle");
              try {
                await api(`/api/proxies/${proxy.id}`, {
                  method: "PATCH",
                  body: JSON.stringify({ is_active: !proxy.is_active }),
                });
                onChanged();
              } catch (e: any) {
                alert(e.message);
              } finally {
                setBusy(null);
              }
            }}
          >
            {proxy.is_active ? "disable" : "enable"}
          </button>
          <button
            className="btn-ghost text-xs"
            disabled={busy !== null}
            onClick={async () => {
              setBusy("reset");
              try {
                await api(`/api/proxies/${proxy.id}/reset`, { method: "POST" });
                onChanged();
              } catch (e: any) {
                alert(e.message);
              } finally {
                setBusy(null);
              }
            }}
          >
            reset stats
          </button>
          <button
            className="btn-ghost text-xs text-bad"
            disabled={busy !== null}
            onClick={async () => {
              if (!confirm(`Delete proxy "${proxy.label}"?`)) return;
              setBusy("delete");
              try {
                await api(`/api/proxies/${proxy.id}`, { method: "DELETE" });
                onChanged();
              } catch (e: any) {
                alert(e.message);
              } finally {
                setBusy(null);
              }
            }}
          >
            delete
          </button>
        </div>
      </div>
    </div>
  );
}

function NewModal({ onClose, onCreated }: { onClose: () => void; onCreated: () => void }) {
  const [label, setLabel] = useState("");
  const [url, setUrl] = useState("");
  const [busy, setBusy] = useState(false);
  const [testMsg, setTestMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center p-4 z-50" onClick={onClose}>
      <form
        className="card w-full max-w-lg space-y-3"
        onClick={(e) => e.stopPropagation()}
        onSubmit={async (e) => {
          e.preventDefault();
          setBusy(true);
          setErr(null);
          try {
            await api("/api/proxies", {
              method: "POST",
              body: JSON.stringify({ label: label.trim(), url: url.trim(), is_active: true }),
            });
            onCreated();
          } catch (e: any) {
            setErr(e.message);
          } finally {
            setBusy(false);
          }
        }}
      >
        <h2 className="text-xl font-semibold">New proxy</h2>
        <div>
          <label className="label">Label *</label>
          <input
            className="input"
            value={label}
            onChange={(e) => setLabel(e.target.value)}
            placeholder="e.g. Oxylabs US #1"
            autoFocus
          />
        </div>
        <div>
          <label className="label">URL *</label>
          <input
            className="input font-mono text-xs"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="http://user:pass@host:port"
          />
        </div>
        {testMsg && <div className="text-sm">{testMsg}</div>}
        {err && <div className="text-bad text-sm">{err}</div>}
        <div className="flex justify-between gap-2 pt-2">
          <button
            type="button"
            className="btn-secondary"
            disabled={!url.trim() || busy}
            onClick={async () => {
              setTestMsg("testing…");
              try {
                const r = await api<any>("/api/proxies/test", {
                  method: "POST",
                  body: JSON.stringify({ url: url.trim() }),
                });
                setTestMsg(
                  r.ok
                    ? `✓ OK (${r.elapsed_ms} ms) — exit IP: ${r.exit_ip}`
                    : `✗ FAIL (${r.elapsed_ms} ms): ${r.error}`,
                );
              } catch (e: any) {
                setTestMsg(`✗ FAIL: ${e.message}`);
              }
            }}
          >
            Test before saving
          </button>
          <div className="flex gap-2">
            <button type="button" className="btn-secondary" onClick={onClose}>
              Cancel
            </button>
            <button type="submit" className="btn-primary" disabled={!label.trim() || !url.trim() || busy}>
              {busy ? "Saving…" : "Create"}
            </button>
          </div>
        </div>
      </form>
    </div>
  );
}

function BulkModal({ onClose, onCreated }: { onClose: () => void; onCreated: () => void }) {
  const [text, setText] = useState("");
  const [prefix, setPrefix] = useState("proxy");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const lines = text
    .split(/\r?\n/)
    .map((s) => s.trim())
    .filter(Boolean);

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center p-4 z-50" onClick={onClose}>
      <form
        className="card w-full max-w-xl space-y-3"
        onClick={(e) => e.stopPropagation()}
        onSubmit={async (e) => {
          e.preventDefault();
          setBusy(true);
          setErr(null);
          try {
            const created = await api<any[]>("/api/proxies/bulk", {
              method: "POST",
              body: JSON.stringify({ urls: lines, label_prefix: prefix.trim() || "proxy" }),
            });
            alert(`Imported ${created.length} proxies.`);
            onCreated();
          } catch (e: any) {
            setErr(e.message);
          } finally {
            setBusy(false);
          }
        }}
      >
        <h2 className="text-xl font-semibold">Bulk import proxies</h2>
        <p className="text-sm text-muted">
          One proxy URL per line. Labels are auto-generated like{" "}
          <code className="text-text">{prefix.trim() || "proxy"}-1</code>,{" "}
          <code className="text-text">{prefix.trim() || "proxy"}-2</code>, etc.
        </p>
        <div>
          <label className="label">Label prefix</label>
          <input className="input" value={prefix} onChange={(e) => setPrefix(e.target.value)} placeholder="proxy" />
        </div>
        <div>
          <label className="label">Proxy URLs ({lines.length} detected)</label>
          <textarea
            className="input font-mono text-xs min-h-[200px]"
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder={`http://user:pass@us-pr.example.com:10001\nhttp://user:pass@us-pr.example.com:10002\n...`}
          />
        </div>
        {err && <div className="text-bad text-sm">{err}</div>}
        <div className="flex justify-end gap-2 pt-2">
          <button type="button" className="btn-secondary" onClick={onClose}>
            Cancel
          </button>
          <button type="submit" className="btn-primary" disabled={lines.length === 0 || busy}>
            {busy ? "Importing…" : `Import ${lines.length}`}
          </button>
        </div>
      </form>
    </div>
  );
}
