"use client";

import { useEffect, useState } from "react";
import useSWR from "swr";
import { useAuth } from "@/components/AuthGate";
import { api, fetcher } from "@/lib/api";

type Preset = {
  id: string;
  label: string;
  provider_kind: "openai_compat" | "anthropic";
  base_url: string;
  model_placeholder: string;
  api_key_help: string;
};

type LLMConfig = {
  id: string;
  name: string;
  provider_kind: "openai_compat" | "anthropic";
  base_url: string;
  model: string;
  api_key_preview: string;
  is_active: boolean;
  extra: Record<string, any>;
  created_at: string;
};

type ActiveStatus = {
  configured: boolean;
  source: "db" | "env" | "none";
  provider_kind?: string;
  base_url?: string;
  model?: string;
  config_id?: string;
  config_name?: string;
};

export default function LLMAdminPage() {
  const { user } = useAuth();
  const { data: configs, mutate } = useSWR<LLMConfig[]>("/api/llm-configs", fetcher);
  const { data: presetsResp } = useSWR<{ presets: Preset[] }>("/api/llm-configs/presets", fetcher);
  const { data: active, mutate: mutateActive } = useSWR<ActiveStatus>(
    "/api/llm-configs/active",
    fetcher,
    { refreshInterval: 10000 },
  );
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<LLMConfig | null>(null);

  if (user?.role !== "admin") {
    return (
      <div className="card text-muted">
        Admin access required. You are signed in as <strong>{user?.role}</strong>.
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <header className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold">LLM providers</h1>
          <p className="text-muted">
            Configure OpenAI, Claude, DeepSeek, Qwen, Gemini, Ollama, or any OpenAI-compatible
            endpoint. One config is active at a time — used for extraction, qualification, AI
            research, and outreach drafting.
          </p>
        </div>
        <button className="btn-primary" onClick={() => { setEditing(null); setOpen(true); }}>
          + New LLM
        </button>
      </header>

      <ActivePanel active={active} />

      <div className="grid gap-3">
        {configs?.length === 0 && (
          <div className="card text-muted text-sm">
            No LLMs configured yet. Click <strong>+ New LLM</strong> above to add one.
            Until you do, extraction runs in mock mode (canned responses).
          </div>
        )}
        {configs?.map((c) => (
          <ConfigRow
            key={c.id}
            cfg={c}
            onActivated={() => { mutate(); mutateActive(); }}
            onEdit={() => { setEditing(c); setOpen(true); }}
            onDeleted={() => { mutate(); mutateActive(); }}
          />
        ))}
      </div>

      {open && (
        <Modal
          presets={presetsResp?.presets ?? []}
          editing={editing}
          onClose={() => setOpen(false)}
          onSaved={() => { setOpen(false); mutate(); mutateActive(); }}
        />
      )}
    </div>
  );
}

function ActivePanel({ active }: { active?: ActiveStatus }) {
  if (!active) return null;
  if (!active.configured) {
    return (
      <div className="card border-l-4 border-warn">
        <div className="flex items-center justify-between">
          <div>
            <div className="font-semibold">No LLM active — running in MOCK mode</div>
            <p className="text-sm text-muted mt-1">
              The pipeline runs end-to-end but extractions return canned data. Add an LLM
              below and click "Activate" to flip to live.
            </p>
          </div>
          <span className="pill bg-warn/15 text-warn">MOCK</span>
        </div>
      </div>
    );
  }
  return (
    <div className="card border-l-4 border-good">
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <div className="font-semibold">
            Active LLM: {active.config_name || "(unnamed)"}
          </div>
          <div className="text-sm text-muted mt-1 font-mono">
            {active.provider_kind} · {active.model} · {active.base_url}
          </div>
          {active.source === "env" && (
            <div className="text-xs text-muted mt-1 italic">
              Loaded from .env. Recommend recreating it as a DB config below so you can
              manage it from this page.
            </div>
          )}
        </div>
        <span className="pill bg-good/15 text-good">LIVE</span>
      </div>
    </div>
  );
}

function ConfigRow({
  cfg, onActivated, onEdit, onDeleted,
}: {
  cfg: LLMConfig;
  onActivated: () => void;
  onEdit: () => void;
  onDeleted: () => void;
}) {
  const [busy, setBusy] = useState<string | null>(null);
  const [testMsg, setTestMsg] = useState<string | null>(null);

  return (
    <div className="card">
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-semibold">{cfg.name}</span>
            <span className="pill bg-panel2 text-muted">
              {cfg.provider_kind === "anthropic" ? "Anthropic" : "OpenAI-compat"}
            </span>
            {cfg.is_active && <span className="pill bg-good/15 text-good">ACTIVE</span>}
          </div>
          <div className="text-sm text-muted mt-1 font-mono break-all">
            {cfg.model} · {cfg.base_url}
          </div>
          <div className="text-xs text-muted mt-1 font-mono">
            key: {cfg.api_key_preview}
          </div>
          {testMsg && <div className="text-xs mt-2">{testMsg}</div>}
        </div>
        <div className="flex flex-col gap-2 shrink-0">
          {!cfg.is_active && (
            <button
              className="btn-primary text-xs"
              disabled={busy !== null}
              onClick={async () => {
                setBusy("activate");
                try {
                  await api(`/api/llm-configs/${cfg.id}/activate`, { method: "POST" });
                  onActivated();
                } catch (e: any) {
                  alert(e.message);
                } finally {
                  setBusy(null);
                }
              }}
            >
              {busy === "activate" ? "Activating…" : "Activate"}
            </button>
          )}
          <button
            className="btn-secondary text-xs"
            disabled={busy !== null}
            onClick={async () => {
              setBusy("test");
              setTestMsg("testing…");
              try {
                const r = await api<any>("/api/llm-configs/test", {
                  method: "POST",
                  body: JSON.stringify({ config_id: cfg.id }),
                });
                setTestMsg(
                  r.ok
                    ? `✓ OK (${r.elapsed_ms} ms) — reply: ${r.sample_output ?? "(empty)"}`
                    : `✗ FAIL: ${r.error}`,
                );
              } catch (e: any) {
                setTestMsg(`✗ FAIL: ${e.message}`);
              } finally {
                setBusy(null);
              }
            }}
          >
            {busy === "test" ? "Testing…" : "Test"}
          </button>
          <button className="btn-secondary text-xs" onClick={onEdit}>Edit</button>
          <button
            className="btn-ghost text-xs text-bad"
            disabled={busy !== null}
            onClick={async () => {
              if (!confirm(`Delete LLM config "${cfg.name}"?`)) return;
              try {
                await api(`/api/llm-configs/${cfg.id}`, { method: "DELETE" });
                onDeleted();
              } catch (e: any) {
                alert(e.message);
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

function Modal({
  presets, editing, onClose, onSaved,
}: {
  presets: Preset[];
  editing: LLMConfig | null;
  onClose: () => void;
  onSaved: () => void;
}) {
  const isEdit = !!editing;
  const [presetId, setPresetId] = useState<string>("custom");
  const [name, setName] = useState(editing?.name ?? "");
  const [providerKind, setProviderKind] = useState<"openai_compat" | "anthropic">(
    editing?.provider_kind ?? "openai_compat",
  );
  const [baseUrl, setBaseUrl] = useState(editing?.base_url ?? "");
  const [model, setModel] = useState(editing?.model ?? "");
  const [apiKey, setApiKey] = useState("");
  const [busy, setBusy] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testMsg, setTestMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  // When editing, infer which preset matches (best-effort) for the label only.
  useEffect(() => {
    if (isEdit) return;
    const p = presets.find((x) => x.id === presetId);
    if (!p) return;
    setProviderKind(p.provider_kind);
    if (!baseUrl) setBaseUrl(p.base_url);
    // Pre-fill name on first selection if user hasn't typed one.
    if (!name && p.id !== "custom") setName(p.label);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [presetId, presets]);

  const activePreset = presets.find((p) => p.id === presetId);

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
            const body: any = {
              name: name.trim() || model.trim(),
              provider_kind: providerKind,
              base_url: baseUrl.trim(),
              model: model.trim(),
            };
            if (apiKey.trim()) body.api_key = apiKey.trim();
            if (isEdit && editing) {
              await api(`/api/llm-configs/${editing.id}`, {
                method: "PATCH",
                body: JSON.stringify(body),
              });
            } else {
              if (!apiKey.trim()) throw new Error("API key is required for a new config.");
              await api("/api/llm-configs", { method: "POST", body: JSON.stringify(body) });
            }
            onSaved();
          } catch (e: any) {
            setErr(e.message);
          } finally {
            setBusy(false);
          }
        }}
      >
        <h2 className="text-xl font-semibold">{isEdit ? "Edit LLM config" : "Add an LLM"}</h2>

        {!isEdit && (
          <div>
            <label className="label">Provider</label>
            <select
              className="input"
              value={presetId}
              onChange={(e) => setPresetId(e.target.value)}
            >
              {presets.map((p) => (
                <option key={p.id} value={p.id}>{p.label}</option>
              ))}
            </select>
            {activePreset?.api_key_help && (
              <p className="text-xs text-muted mt-1">{activePreset.api_key_help}</p>
            )}
          </div>
        )}

        <div className="grid md:grid-cols-2 gap-3">
          <div>
            <label className="label">Name *</label>
            <input
              className="input"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. DeepSeek prod"
            />
          </div>
          <div>
            <label className="label">Provider kind</label>
            <select
              className="input"
              value={providerKind}
              onChange={(e) => setProviderKind(e.target.value as any)}
              disabled={!isEdit && presetId !== "custom"}
            >
              <option value="openai_compat">openai_compat (most providers)</option>
              <option value="anthropic">anthropic (Claude API)</option>
            </select>
          </div>
        </div>

        <div>
          <label className="label">Base URL *</label>
          <input
            className="input font-mono text-xs"
            value={baseUrl}
            onChange={(e) => setBaseUrl(e.target.value)}
            placeholder={activePreset?.base_url || "https://..."}
          />
        </div>

        <div>
          <label className="label">Model * (any model name your provider exposes)</label>
          <input
            className="input font-mono"
            value={model}
            onChange={(e) => setModel(e.target.value)}
            placeholder={activePreset?.model_placeholder || "gpt-4o-mini / claude-3-5-sonnet-20241022 / etc."}
          />
        </div>

        <div>
          <label className="label">
            API key {isEdit ? "(leave blank to keep current)" : "*"}
          </label>
          <input
            className="input font-mono"
            type="password"
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            placeholder={isEdit ? `current: ${editing?.api_key_preview}` : "sk-..."}
          />
        </div>

        {testMsg && <div className="text-sm">{testMsg}</div>}
        {err && <div className="text-bad text-sm">{err}</div>}

        <div className="flex justify-between gap-2 pt-2">
          <button
            type="button"
            className="btn-secondary"
            disabled={!baseUrl.trim() || !model.trim() || (!apiKey.trim() && !isEdit) || testing}
            onClick={async () => {
              setTesting(true);
              setTestMsg("testing…");
              try {
                const r = await api<any>("/api/llm-configs/test", {
                  method: "POST",
                  body: JSON.stringify({
                    provider_kind: providerKind,
                    base_url: baseUrl.trim(),
                    model: model.trim(),
                    api_key: apiKey.trim() || (editing?.api_key_preview ?? ""),
                    // Note: if editing without supplying a new key, this still asks the
                    // backend to test — but with no real key. Better: edit-mode test uses the
                    // saved config endpoint instead.
                    ...(isEdit && !apiKey.trim() ? { config_id: editing!.id } : {}),
                  }),
                });
                setTestMsg(
                  r.ok
                    ? `✓ OK (${r.elapsed_ms} ms) — reply: ${r.sample_output ?? "(empty)"}`
                    : `✗ FAIL: ${r.error}`,
                );
              } catch (e: any) {
                setTestMsg(`✗ FAIL: ${e.message}`);
              } finally {
                setTesting(false);
              }
            }}
          >
            {testing ? "Testing…" : "Test connection"}
          </button>
          <div className="flex gap-2">
            <button type="button" className="btn-secondary" onClick={onClose}>Cancel</button>
            <button
              type="submit"
              className="btn-primary"
              disabled={!baseUrl.trim() || !model.trim() || (!apiKey.trim() && !isEdit) || busy}
            >
              {busy ? "Saving…" : (isEdit ? "Save" : "Create")}
            </button>
          </div>
        </div>
      </form>
    </div>
  );
}
