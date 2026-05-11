"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import useSWR from "swr";
import { api, fetcher } from "@/lib/api";

type Project = {
  id: string;
  name: string;
  description?: string;
  system_prompt?: string;
  memory?: string;
  is_pinned: boolean;
  message_count: number;
  last_message_at?: string;
  created_at: string;
  updated_at: string;
};

type Message = {
  id: string;
  project_id: string;
  role: "user" | "assistant" | "tool";
  content?: string;
  tool_calls?: { id: string; name: string; arguments: Record<string, any> }[];
  tool_call_id?: string;
  tool_name?: string;
  error?: string;
  created_at: string;
};

export default function ChatPage() {
  const { data: projects, mutate: mutateProjects } = useSWR<Project[]>(
    "/api/chat/projects",
    fetcher,
    { refreshInterval: 15000 },
  );
  const [activeId, setActiveId] = useState<string | null>(null);
  const [newOpen, setNewOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);

  // Auto-select the first project on load.
  useEffect(() => {
    if (!activeId && projects && projects.length > 0) {
      setActiveId(projects[0].id);
    }
  }, [projects, activeId]);

  const activeProject = useMemo(
    () => projects?.find((p) => p.id === activeId) ?? null,
    [projects, activeId],
  );

  return (
    <div className="flex h-[calc(100vh-4rem)] -m-8">
      {/* Project list */}
      <aside className="w-72 shrink-0 border-r border-border bg-panel2/40 flex flex-col">
        <div className="p-4 border-b border-border">
          <div className="flex items-center justify-between mb-2">
            <h2 className="font-semibold">Projects</h2>
            <button className="btn-primary text-xs" onClick={() => setNewOpen(true)}>
              + New
            </button>
          </div>
          <p className="text-xs text-muted">
            One thread per business. Each project has its own memory, system prompt, and message history.
          </p>
        </div>
        <div className="flex-1 overflow-auto p-2">
          {projects?.length === 0 && (
            <div className="text-sm text-muted p-3">
              No projects yet. Click <strong>+ New</strong> to start.
            </div>
          )}
          {projects?.map((p) => (
            <button
              key={p.id}
              className={`w-full text-left px-3 py-2 rounded-lg mb-1 transition ${
                p.id === activeId
                  ? "bg-panel border border-border"
                  : "hover:bg-panel"
              }`}
              onClick={() => setActiveId(p.id)}
            >
              <div className="flex items-center gap-2">
                {p.is_pinned && <span className="text-warn text-xs">★</span>}
                <span className="font-medium truncate flex-1">{p.name}</span>
                <span className="text-xs text-muted">{p.message_count}</span>
              </div>
              {p.description && (
                <div className="text-xs text-muted truncate mt-0.5">{p.description}</div>
              )}
            </button>
          ))}
        </div>
      </aside>

      {/* Chat panel */}
      <div className="flex-1 flex flex-col min-w-0">
        {activeProject ? (
          <ChatPanel
            project={activeProject}
            onOpenSettings={() => setSettingsOpen(true)}
            onChanged={() => mutateProjects()}
          />
        ) : (
          <div className="flex-1 flex items-center justify-center text-muted">
            {projects?.length === 0 ? "Create a project to start chatting." : "Pick a project on the left."}
          </div>
        )}
      </div>

      {newOpen && (
        <NewProjectModal
          onClose={() => setNewOpen(false)}
          onCreated={(p) => {
            setNewOpen(false);
            mutateProjects();
            setActiveId(p.id);
          }}
        />
      )}
      {settingsOpen && activeProject && (
        <ProjectSettingsModal
          project={activeProject}
          onClose={() => setSettingsOpen(false)}
          onSaved={() => {
            setSettingsOpen(false);
            mutateProjects();
          }}
          onDeleted={() => {
            setSettingsOpen(false);
            setActiveId(null);
            mutateProjects();
          }}
        />
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------

function ChatPanel({
  project,
  onOpenSettings,
  onChanged,
}: {
  project: Project;
  onOpenSettings: () => void;
  onChanged: () => void;
}) {
  const { data: messages, mutate: mutateMessages } = useSWR<Message[]>(
    `/api/chat/projects/${project.id}/messages`,
    fetcher,
  );
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const [sendErr, setSendErr] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  // Reset when switching projects.
  useEffect(() => {
    setDraft("");
    setSendErr(null);
  }, [project.id]);

  // Auto-scroll to bottom when messages change.
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, sending]);

  async function send() {
    const content = draft.trim();
    if (!content || sending) return;
    setSending(true);
    setSendErr(null);
    // Optimistic: drop our message into the visible list immediately.
    setDraft("");
    try {
      await api(`/api/chat/projects/${project.id}/messages`, {
        method: "POST",
        body: JSON.stringify({ content }),
      });
      await mutateMessages();
      onChanged();
    } catch (e: any) {
      setSendErr(e.message);
      setDraft(content); // restore so the user doesn't lose it
    } finally {
      setSending(false);
    }
  }

  return (
    <>
      {/* Header */}
      <div className="border-b border-border px-6 py-3 flex items-center justify-between bg-panel">
        <div className="min-w-0">
          <div className="font-semibold truncate">{project.name}</div>
          {project.description && (
            <div className="text-xs text-muted truncate">{project.description}</div>
          )}
        </div>
        <button className="btn-secondary text-xs" onClick={onOpenSettings}>
          ⚙ Settings
        </button>
      </div>

      {/* Messages */}
      <div ref={scrollRef} className="flex-1 overflow-auto px-6 py-6 space-y-4">
        {(!messages || messages.length === 0) && (
          <EmptyHelp project={project} onUseExample={setDraft} />
        )}
        {messages?.map((m) => (
          <MessageBubble key={m.id} message={m} />
        ))}
        {sending && (
          <div className="text-sm text-muted italic">
            Thinking… (the LLM may be calling tools — discovery, crawls, etc.)
          </div>
        )}
      </div>

      {/* Composer */}
      <div className="border-t border-border bg-panel p-4">
        {sendErr && <div className="text-bad text-sm mb-2">{sendErr}</div>}
        <div className="flex gap-2">
          <textarea
            className="input flex-1 min-h-[60px] max-h-[200px] resize-y"
            placeholder="Tell the agent what to do. E.g. 'Crawl bold.org/scholarships and save the top 20 active scholarships as leads.'"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
                e.preventDefault();
                send();
              }
            }}
            disabled={sending}
          />
          <button
            className="btn-primary self-end"
            onClick={send}
            disabled={!draft.trim() || sending}
          >
            {sending ? "Sending…" : "Send"}
          </button>
        </div>
        <div className="text-[10px] text-muted mt-1">⌘+Enter to send</div>
      </div>
    </>
  );
}

// ---------------------------------------------------------------------------

function MessageBubble({ message }: { message: Message }) {
  if (message.role === "user") {
    return (
      <div className="flex justify-end">
        <div className="max-w-2xl bg-accent text-white rounded-2xl rounded-br-sm px-4 py-2 whitespace-pre-wrap">
          {message.content}
        </div>
      </div>
    );
  }

  if (message.role === "tool") {
    return <ToolResultBlock message={message} />;
  }

  // assistant
  return (
    <div className="flex justify-start">
      <div className="max-w-2xl space-y-2">
        {message.content && (
          <div className="bg-panel border border-border rounded-2xl rounded-bl-sm px-4 py-2 whitespace-pre-wrap">
            {message.content}
          </div>
        )}
        {message.tool_calls?.map((tc) => (
          <ToolCallChip key={tc.id} call={tc} />
        ))}
      </div>
    </div>
  );
}

function ToolCallChip({ call }: { call: { name: string; arguments: Record<string, any> } }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="bg-panel2 border border-border rounded-lg text-xs">
      <button
        className="w-full text-left px-3 py-2 flex items-center justify-between"
        onClick={() => setOpen((v) => !v)}
      >
        <span>
          <span className="text-muted">tool call:</span>{" "}
          <span className="font-mono text-accent2">{call.name}</span>
          <span className="text-muted">(</span>
          <span className="font-mono">
            {Object.keys(call.arguments || {}).slice(0, 2).join(", ")}
            {Object.keys(call.arguments || {}).length > 2 ? ", …" : ""}
          </span>
          <span className="text-muted">)</span>
        </span>
        <span className="text-muted">{open ? "▾" : "▸"}</span>
      </button>
      {open && (
        <pre className="text-xs px-3 pb-2 overflow-auto max-h-48 text-muted">
          {JSON.stringify(call.arguments, null, 2)}
        </pre>
      )}
    </div>
  );
}

function ToolResultBlock({ message }: { message: Message }) {
  const [open, setOpen] = useState(false);
  const isError = !!message.error;
  let summary = "";
  try {
    const parsed = JSON.parse(message.content || "{}");
    if (parsed.count !== undefined) summary = `${parsed.count} item(s)`;
    else if (parsed.lead_id) summary = `saved lead ${String(parsed.lead_id).slice(0, 8)}`;
    else if (parsed.queued) summary = "queued in background";
    else if (parsed.markdown) summary = `${(parsed.markdown.length / 1000).toFixed(1)} KB markdown`;
    else if (parsed.ok === false) summary = parsed.error || "failed";
    else if (parsed.ok) summary = "ok";
    else summary = `${(message.content || "").length} chars`;
  } catch {
    summary = `${(message.content || "").length} chars`;
  }
  return (
    <div className="flex justify-start">
      <div className="max-w-2xl w-full">
        <button
          className={`w-full text-left text-xs px-3 py-2 rounded-lg border ${
            isError ? "border-bad/40 bg-bad/5 text-bad" : "border-border bg-panel2"
          }`}
          onClick={() => setOpen((v) => !v)}
        >
          <span className="text-muted">tool result:</span>{" "}
          <span className="font-mono">{message.tool_name}</span> → {summary}
          {message.error && <span className="ml-2 text-bad">⚠ {message.error}</span>}
          <span className="text-muted ml-2">{open ? "▾" : "▸"}</span>
        </button>
        {open && (
          <pre className="text-xs mt-1 px-3 py-2 bg-panel2 border border-border rounded-lg overflow-auto max-h-64 whitespace-pre-wrap">
            {prettyTry(message.content || "")}
          </pre>
        )}
      </div>
    </div>
  );
}

function prettyTry(s: string): string {
  try {
    return JSON.stringify(JSON.parse(s), null, 2);
  } catch {
    return s;
  }
}

// ---------------------------------------------------------------------------

function EmptyHelp({ project, onUseExample }: { project: Project; onUseExample: (s: string) => void }) {
  const examples = [
    "Crawl bold.org and find the 10 most relevant active scholarships. Save each one as a lead with the application URL as the website and the deadline in the project_summary.",
    "Search existing leads with fit_score >= 70 and tell me what they have in common.",
    "List my configured lead sources, then trigger a discovery run over the Reddit ones.",
    "Crawl https://example.com/team — extract every email address you see and save the most senior person as a lead.",
  ];
  return (
    <div className="max-w-2xl mx-auto text-sm space-y-4 py-8">
      <h3 className="text-lg font-semibold">{project.name}</h3>
      <p className="text-muted">
        This chat has access to your active LLM, all your existing leads, and these tools:
      </p>
      <ul className="text-muted list-disc list-inside text-xs space-y-1">
        <li><code className="text-text">crawl_url</code> — fetch any public webpage as Markdown</li>
        <li><code className="text-text">save_lead</code> / <code className="text-text">search_leads</code> — work with your leads DB</li>
        <li><code className="text-text">list_lead_sources</code> / <code className="text-text">trigger_discovery_run</code> — kick off background discovery</li>
        <li><code className="text-text">list_services</code> — knows what you sell</li>
        <li><code className="text-text">remember</code> — write durable notes to THIS project's memory</li>
      </ul>
      <div className="space-y-2 pt-2">
        <div className="text-muted text-xs uppercase tracking-wider">Try one of these:</div>
        {examples.map((ex) => (
          <button
            key={ex}
            className="w-full text-left px-3 py-2 bg-panel2 hover:bg-panel border border-border rounded-lg text-xs"
            onClick={() => onUseExample(ex)}
          >
            {ex}
          </button>
        ))}
      </div>
      <div className="text-xs text-muted pt-4 border-t border-border">
        <strong>About LinkedIn:</strong> LinkedIn actively blocks scrapers. A single public profile URL
        might work; anything at scale (e.g. "get me 500 LinkedIn leads") will fail. For real
        LinkedIn volume, use Sales Navigator API, Apollo/Wiza/RocketReach (paid), or export from
        LinkedIn and use Import / Lists.
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------

function NewProjectModal({
  onClose,
  onCreated,
}: {
  onClose: () => void;
  onCreated: (p: Project) => void;
}) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [systemPrompt, setSystemPrompt] = useState("");
  const [busy, setBusy] = useState(false);
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
            const p = await api<Project>("/api/chat/projects", {
              method: "POST",
              body: JSON.stringify({
                name: name.trim(),
                description: description.trim() || null,
                system_prompt: systemPrompt.trim() || null,
              }),
            });
            onCreated(p);
          } catch (e: any) {
            setErr(e.message);
          } finally {
            setBusy(false);
          }
        }}
      >
        <h2 className="text-xl font-semibold">New chat project</h2>
        <div>
          <label className="label">Name *</label>
          <input
            className="input"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g. Shapla AI · AIOptimize.me"
            autoFocus
          />
        </div>
        <div>
          <label className="label">Description (optional)</label>
          <input
            className="input"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="One line on what this project is for"
          />
        </div>
        <div>
          <label className="label">
            Project-specific instructions (optional, appended to system prompt)
          </label>
          <textarea
            className="input font-mono text-xs min-h-[100px]"
            value={systemPrompt}
            onChange={(e) => setSystemPrompt(e.target.value)}
            placeholder="e.g. 'You're helping me run Shapla AI, a scholarship matching service for Bangladeshi students. Focus on US/UK/Australia full-ride scholarships.'"
          />
        </div>
        {err && <div className="text-bad text-sm">{err}</div>}
        <div className="flex justify-end gap-2 pt-2">
          <button type="button" className="btn-secondary" onClick={onClose}>Cancel</button>
          <button type="submit" className="btn-primary" disabled={!name.trim() || busy}>
            {busy ? "Creating…" : "Create"}
          </button>
        </div>
      </form>
    </div>
  );
}

function ProjectSettingsModal({
  project,
  onClose,
  onSaved,
  onDeleted,
}: {
  project: Project;
  onClose: () => void;
  onSaved: () => void;
  onDeleted: () => void;
}) {
  const [name, setName] = useState(project.name);
  const [description, setDescription] = useState(project.description ?? "");
  const [systemPrompt, setSystemPrompt] = useState(project.system_prompt ?? "");
  const [memory, setMemory] = useState(project.memory ?? "");
  const [isPinned, setIsPinned] = useState(project.is_pinned);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center p-4 z-50" onClick={onClose}>
      <form
        className="card w-full max-w-xl space-y-3 max-h-[90vh] overflow-auto"
        onClick={(e) => e.stopPropagation()}
        onSubmit={async (e) => {
          e.preventDefault();
          setBusy(true);
          setErr(null);
          try {
            await api(`/api/chat/projects/${project.id}`, {
              method: "PATCH",
              body: JSON.stringify({
                name: name.trim(),
                description: description.trim() || null,
                system_prompt: systemPrompt.trim() || null,
                memory: memory.trim() || null,
                is_pinned: isPinned,
              }),
            });
            onSaved();
          } catch (e: any) {
            setErr(e.message);
          } finally {
            setBusy(false);
          }
        }}
      >
        <h2 className="text-xl font-semibold">Project settings</h2>
        <div>
          <label className="label">Name *</label>
          <input className="input" value={name} onChange={(e) => setName(e.target.value)} />
        </div>
        <div>
          <label className="label">Description</label>
          <input className="input" value={description} onChange={(e) => setDescription(e.target.value)} />
        </div>
        <div>
          <label className="label">System prompt addition (project-specific instructions)</label>
          <textarea
            className="input font-mono text-xs min-h-[100px]"
            value={systemPrompt}
            onChange={(e) => setSystemPrompt(e.target.value)}
          />
        </div>
        <div>
          <label className="label">
            Memory (notes the LLM sees every turn — both the agent and you can edit)
          </label>
          <textarea
            className="input text-xs min-h-[120px]"
            value={memory}
            onChange={(e) => setMemory(e.target.value)}
            placeholder="Auto-written by the `remember` tool, but feel free to edit by hand."
          />
        </div>
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={isPinned}
            onChange={(e) => setIsPinned(e.target.checked)}
          />
          Pin to top of project list
        </label>
        {err && <div className="text-bad text-sm">{err}</div>}
        <div className="flex justify-between gap-2 pt-2">
          <button
            type="button"
            className="btn-ghost text-bad"
            onClick={async () => {
              if (!confirm(`Delete project "${project.name}"? This deletes all its messages too.`)) return;
              try {
                await api(`/api/chat/projects/${project.id}`, { method: "DELETE" });
                onDeleted();
              } catch (e: any) {
                alert(e.message);
              }
            }}
          >
            Delete project
          </button>
          <div className="flex gap-2">
            <button type="button" className="btn-secondary" onClick={onClose}>Cancel</button>
            <button type="submit" className="btn-primary" disabled={!name.trim() || busy}>
              {busy ? "Saving…" : "Save"}
            </button>
          </div>
        </div>
      </form>
    </div>
  );
}
