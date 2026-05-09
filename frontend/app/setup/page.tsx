"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, setToken } from "@/lib/api";

export default function SetupPage() {
  const router = useRouter();
  const [needsSetup, setNeedsSetup] = useState<boolean | null>(null);
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [password2, setPassword2] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    api<{ needs_setup: boolean }>("/api/auth/needs-setup")
      .then((r) => setNeedsSetup(r.needs_setup))
      .catch(() => setNeedsSetup(null));
  }, []);

  // If setup is already complete bounce the visitor to /login.
  useEffect(() => {
    if (needsSetup === false) router.replace("/login");
  }, [needsSetup, router]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (password !== password2) {
      setErr("Passwords don't match.");
      return;
    }
    if (password.length < 8) {
      setErr("Password must be at least 8 characters.");
      return;
    }
    setBusy(true);
    setErr(null);
    try {
      const r = await api<any>("/api/auth/setup", {
        method: "POST",
        body: JSON.stringify({
          email: email.trim().toLowerCase(),
          password,
          name: name.trim() || null,
        }),
      });
      setToken(r.token);
      router.push("/");
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  }

  if (needsSetup === null) {
    return <div className="min-h-screen flex items-center justify-center text-muted">Loading…</div>;
  }
  if (needsSetup === false) return null;

  return (
    <div className="min-h-screen flex items-center justify-center p-6 bg-bg">
      <form onSubmit={submit} className="card w-full max-w-md space-y-4">
        <div>
          <div className="text-2xl font-bold">⚡ Welcome to LeadMagnet</div>
          <p className="text-sm text-muted mt-1">
            Create the first <strong>admin</strong> account. You can invite teammates
            (member / viewer) afterwards.
          </p>
        </div>
        <div>
          <label className="label">Your name</label>
          <input className="input" value={name} onChange={(e) => setName(e.target.value)} placeholder="optional" />
        </div>
        <div>
          <label className="label">Email *</label>
          <input className="input" type="email" autoComplete="email" autoFocus value={email} onChange={(e) => setEmail(e.target.value)} />
        </div>
        <div>
          <label className="label">Password *</label>
          <input className="input" type="password" autoComplete="new-password" value={password} onChange={(e) => setPassword(e.target.value)} />
        </div>
        <div>
          <label className="label">Confirm password *</label>
          <input className="input" type="password" autoComplete="new-password" value={password2} onChange={(e) => setPassword2(e.target.value)} />
        </div>
        {err && <div className="text-bad text-sm">{err}</div>}
        <button
          type="submit"
          className="btn-primary w-full justify-center"
          disabled={!email || !password || !password2 || busy}
        >
          {busy ? "Creating…" : "Create admin account"}
        </button>
      </form>
    </div>
  );
}
