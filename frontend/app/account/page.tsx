"use client";

import { useState } from "react";
import { useAuth } from "@/components/AuthGate";
import { api } from "@/lib/api";

export default function AccountPage() {
  const { user } = useAuth();
  const [oldPwd, setOldPwd] = useState("");
  const [newPwd, setNewPwd] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ ok?: boolean; text: string } | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (newPwd !== confirm) return setMsg({ ok: false, text: "Passwords don't match." });
    if (newPwd.length < 8) return setMsg({ ok: false, text: "New password must be at least 8 characters." });
    setBusy(true);
    setMsg(null);
    try {
      await api("/api/auth/change-password", {
        method: "POST",
        body: JSON.stringify({ old_password: oldPwd, new_password: newPwd }),
      });
      setOldPwd("");
      setNewPwd("");
      setConfirm("");
      setMsg({ ok: true, text: "Password updated." });
    } catch (e: any) {
      setMsg({ ok: false, text: e.message });
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6 max-w-xl">
      <header>
        <h1 className="text-3xl font-bold">Your account</h1>
        <p className="text-muted">{user?.email} ({user?.role})</p>
      </header>

      <form onSubmit={submit} className="card space-y-3">
        <h2 className="font-semibold">Change password</h2>
        <div>
          <label className="label">Current password</label>
          <input className="input" type="password" value={oldPwd} onChange={(e) => setOldPwd(e.target.value)} />
        </div>
        <div>
          <label className="label">New password</label>
          <input className="input" type="password" value={newPwd} onChange={(e) => setNewPwd(e.target.value)} />
        </div>
        <div>
          <label className="label">Confirm new password</label>
          <input className="input" type="password" value={confirm} onChange={(e) => setConfirm(e.target.value)} />
        </div>
        {msg && (
          <div className={`text-sm ${msg.ok ? "text-good" : "text-bad"}`}>{msg.text}</div>
        )}
        <button
          type="submit"
          className="btn-primary"
          disabled={!oldPwd || !newPwd || !confirm || busy}
        >
          {busy ? "Saving…" : "Update password"}
        </button>
      </form>
    </div>
  );
}
