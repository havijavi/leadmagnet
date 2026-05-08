"use client";

import { useEffect, useState } from "react";
import { setToken } from "@/lib/api";

export default function TokenGate({ children }: { children: React.ReactNode }) {
  const [ready, setReady] = useState(false);
  const [value, setValue] = useState("");

  useEffect(() => {
    if (typeof window !== "undefined" && window.localStorage.getItem("admin_token")) {
      setReady(true);
    } else {
      setReady(false);
    }
  }, []);

  if (ready) return <>{children}</>;

  return (
    <div className="min-h-screen flex items-center justify-center bg-bg p-6">
      <div className="card w-full max-w-md">
        <h1 className="text-xl font-semibold mb-1">Sign in</h1>
        <p className="text-sm text-muted mb-4">
          Paste the <code className="text-text">ADMIN_TOKEN</code> from your{" "}
          <code className="text-text">.env</code> to access the dashboard.
        </p>
        <input
          autoFocus
          type="password"
          className="input mb-3"
          placeholder="bearer token"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && value.trim()) {
              setToken(value.trim());
              setReady(true);
            }
          }}
        />
        <button
          className="btn-primary w-full justify-center"
          disabled={!value.trim()}
          onClick={() => {
            setToken(value.trim());
            setReady(true);
          }}
        >
          Continue
        </button>
      </div>
    </div>
  );
}
