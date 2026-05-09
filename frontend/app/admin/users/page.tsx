"use client";

import { useState } from "react";
import useSWR from "swr";
import { useAuth } from "@/components/AuthGate";
import { api, fetcher, CurrentUser } from "@/lib/api";

const ROLES: { value: "admin" | "member" | "viewer"; label: string; hint: string }[] = [
  { value: "admin", label: "admin", hint: "Everything: services, sources, schedules, sheets, CRM, users." },
  { value: "member", label: "member", hint: "Pipeline ops: discovery, enrichment, leads, outreach, CSV import." },
  { value: "viewer", label: "viewer", hint: "Read-only: leads, outreach, dashboard." },
];

export default function UsersAdminPage() {
  const { user: me } = useAuth();
  const { data, mutate } = useSWR<CurrentUser[]>("/api/users", fetcher);
  const [open, setOpen] = useState(false);
  const [resetting, setResetting] = useState<string | null>(null);

  if (me?.role !== "admin") {
    return (
      <div className="card text-muted">
        Admin access required. You are signed in as <strong>{me?.role}</strong>.
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Users</h1>
          <p className="text-muted">Invite teammates, change roles, reset passwords.</p>
        </div>
        <button className="btn-primary" onClick={() => setOpen(true)}>+ New user</button>
      </header>

      <div className="card">
        <h2 className="font-semibold mb-2">Roles</h2>
        <ul className="text-sm text-muted space-y-1">
          {ROLES.map((r) => (
            <li key={r.value}>
              <span className="pill bg-panel2 text-text mr-2">{r.label}</span>
              {r.hint}
            </li>
          ))}
        </ul>
      </div>

      <div className="card">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-muted text-xs uppercase tracking-wider">
              <th className="text-left py-2">Email</th>
              <th className="text-left">Name</th>
              <th className="text-left">Role</th>
              <th className="text-left">Active</th>
              <th className="text-left">Last login</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {data?.length === 0 && (
              <tr><td colSpan={6} className="py-6 text-center text-muted">no users yet</td></tr>
            )}
            {data?.map((u) => {
              const isMe = u.id === me?.id;
              return (
                <tr key={u.id} className="border-t border-border">
                  <td className="py-2">{u.email}{isMe && <span className="text-xs text-muted ml-2">(you)</span>}</td>
                  <td>{u.name || "—"}</td>
                  <td>
                    <select
                      className="input py-1 text-xs"
                      value={u.role}
                      disabled={isMe}
                      onChange={async (e) => {
                        try {
                          await api(`/api/users/${u.id}`, {
                            method: "PATCH",
                            body: JSON.stringify({ role: e.target.value }),
                          });
                          mutate();
                        } catch (err: any) {
                          alert(err.message);
                          mutate();
                        }
                      }}
                    >
                      {ROLES.map((r) => <option key={r.value} value={r.value}>{r.label}</option>)}
                    </select>
                  </td>
                  <td>
                    <button
                      className={`pill ${u.is_active ? "bg-good/15 text-good" : "bg-bad/15 text-bad"}`}
                      disabled={isMe}
                      onClick={async () => {
                        try {
                          await api(`/api/users/${u.id}`, {
                            method: "PATCH",
                            body: JSON.stringify({ is_active: !u.is_active }),
                          });
                          mutate();
                        } catch (err: any) {
                          alert(err.message);
                        }
                      }}
                    >
                      {u.is_active ? "active" : "disabled"}
                    </button>
                  </td>
                  <td className="text-xs text-muted">{u.last_login_at ? new Date(u.last_login_at).toLocaleString() : "—"}</td>
                  <td className="text-right">
                    <button
                      className="btn-ghost text-xs"
                      onClick={() => setResetting(u.id)}
                    >
                      reset password
                    </button>
                    {!isMe && (
                      <button
                        className="btn-ghost text-xs text-bad ml-2"
                        onClick={async () => {
                          if (!confirm(`Delete ${u.email}?`)) return;
                          try {
                            await api(`/api/users/${u.id}`, { method: "DELETE" });
                            mutate();
                          } catch (err: any) {
                            alert(err.message);
                          }
                        }}
                      >
                        delete
                      </button>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {open && <CreateModal onClose={() => setOpen(false)} onCreated={() => { setOpen(false); mutate(); }} />}
      {resetting && (
        <ResetModal
          userId={resetting}
          onClose={() => setResetting(null)}
          onDone={() => { setResetting(null); mutate(); }}
        />
      )}
    </div>
  );
}

function CreateModal({ onClose, onCreated }: { onClose: () => void; onCreated: () => void }) {
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState<"admin" | "member" | "viewer">("member");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center p-4 z-50" onClick={onClose}>
      <form
        className="card w-full max-w-md space-y-3"
        onClick={(e) => e.stopPropagation()}
        onSubmit={async (e) => {
          e.preventDefault();
          setBusy(true);
          setErr(null);
          try {
            await api("/api/users", {
              method: "POST",
              body: JSON.stringify({
                email: email.trim().toLowerCase(),
                name: name.trim() || null,
                password,
                role,
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
        <h2 className="text-xl font-semibold">New user</h2>
        <div>
          <label className="label">Email *</label>
          <input className="input" type="email" value={email} onChange={(e) => setEmail(e.target.value)} />
        </div>
        <div>
          <label className="label">Name</label>
          <input className="input" value={name} onChange={(e) => setName(e.target.value)} />
        </div>
        <div>
          <label className="label">Initial password * (min 8 chars)</label>
          <input className="input" type="text" value={password} onChange={(e) => setPassword(e.target.value)} />
        </div>
        <div>
          <label className="label">Role</label>
          <select className="input" value={role} onChange={(e) => setRole(e.target.value as any)}>
            {ROLES.map((r) => <option key={r.value} value={r.value}>{r.label}</option>)}
          </select>
          <p className="text-xs text-muted mt-1">{ROLES.find((r) => r.value === role)?.hint}</p>
        </div>
        {err && <div className="text-bad text-sm">{err}</div>}
        <div className="flex justify-end gap-2 pt-2">
          <button type="button" className="btn-secondary" onClick={onClose}>Cancel</button>
          <button type="submit" className="btn-primary" disabled={!email || password.length < 8 || busy}>
            {busy ? "Creating…" : "Create"}
          </button>
        </div>
      </form>
    </div>
  );
}

function ResetModal({ userId, onClose, onDone }: { userId: string; onClose: () => void; onDone: () => void }) {
  const [pwd, setPwd] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center p-4 z-50" onClick={onClose}>
      <form
        className="card w-full max-w-sm space-y-3"
        onClick={(e) => e.stopPropagation()}
        onSubmit={async (e) => {
          e.preventDefault();
          setBusy(true);
          setErr(null);
          try {
            await api(`/api/users/${userId}/reset-password`, {
              method: "POST",
              body: JSON.stringify({ new_password: pwd }),
            });
            onDone();
          } catch (e: any) {
            setErr(e.message);
          } finally {
            setBusy(false);
          }
        }}
      >
        <h2 className="text-xl font-semibold">Reset password</h2>
        <p className="text-sm text-muted">The user will need to sign in with this new password.</p>
        <input className="input" type="text" value={pwd} onChange={(e) => setPwd(e.target.value)} placeholder="new password (min 8)" />
        {err && <div className="text-bad text-sm">{err}</div>}
        <div className="flex justify-end gap-2">
          <button type="button" className="btn-secondary" onClick={onClose}>Cancel</button>
          <button type="submit" className="btn-primary" disabled={pwd.length < 8 || busy}>
            {busy ? "Saving…" : "Reset"}
          </button>
        </div>
      </form>
    </div>
  );
}
