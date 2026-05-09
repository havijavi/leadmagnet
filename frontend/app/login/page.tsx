"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { api, setToken } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [needsSetup, setNeedsSetup] = useState<boolean | null>(null);

  useEffect(() => {
    api<{ needs_setup: boolean }>("/api/auth/needs-setup")
      .then((r) => setNeedsSetup(r.needs_setup))
      .catch(() => setNeedsSetup(null));
  }, []);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setErr(null);
    try {
      const r = await api<any>("/api/auth/login", {
        method: "POST",
        body: JSON.stringify({ email: email.trim().toLowerCase(), password }),
      });
      setToken(r.token);
      router.push("/");
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  }

  if (needsSetup) {
    // First-run state: redirect to /setup so the dashboard isn't reachable yet.
    if (typeof window !== "undefined") window.location.href = "/setup";
    return null;
  }

  return (
    <div className="min-h-screen flex items-center justify-center p-6 bg-bg">
      <form onSubmit={submit} className="card w-full max-w-md space-y-4">
        <div>
          <div className="text-2xl font-bold">⚡ LeadMagnet</div>
          <p className="text-sm text-muted mt-1">Sign in to your account.</p>
        </div>
        <div>
          <label className="label">Email</label>
          <input
            className="input"
            type="email"
            autoComplete="email"
            autoFocus
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </div>
        <div>
          <label className="label">Password</label>
          <input
            className="input"
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </div>
        {err && <div className="text-bad text-sm">{err}</div>}
        <button
          type="submit"
          className="btn-primary w-full justify-center"
          disabled={!email || !password || busy}
        >
          {busy ? "Signing in…" : "Sign in"}
        </button>
        <p className="text-xs text-muted text-center">
          Locked out? Use the <code className="text-text">ADMIN_TOKEN</code> from{" "}
          <code className="text-text">.env</code> as a bearer token at{" "}
          <Link className="text-accent2" href="/setup">/setup</Link> or via the API.
        </p>
      </form>
    </div>
  );
}
