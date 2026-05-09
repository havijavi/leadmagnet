"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "./AuthGate";

export default function UserMenu() {
  const { user, signOut } = useAuth();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const router = useRouter();

  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [open]);

  if (!user) return null;
  const initials = (user.name || user.email).slice(0, 2).toUpperCase();

  return (
    <div ref={ref} className="relative">
      <button
        className="flex items-center gap-2 px-2 py-1 rounded-lg hover:bg-panel2 w-full text-left"
        onClick={() => setOpen((v) => !v)}
      >
        <div className="w-8 h-8 rounded-full bg-accent/30 text-text flex items-center justify-center text-xs font-semibold">
          {initials}
        </div>
        <div className="flex-1 overflow-hidden">
          <div className="text-sm truncate">{user.name || user.email}</div>
          <div className="text-[10px] uppercase tracking-wider text-muted">{user.role}</div>
        </div>
      </button>
      {open && (
        <div className="absolute bottom-full left-0 mb-2 w-full bg-panel2 border border-border rounded-lg shadow-xl py-1 z-50">
          {user.role === "admin" && (
            <button
              className="w-full text-left px-3 py-2 text-sm hover:bg-panel"
              onClick={() => { setOpen(false); router.push("/admin/users"); }}
            >
              User management
            </button>
          )}
          <button
            className="w-full text-left px-3 py-2 text-sm hover:bg-panel"
            onClick={() => { setOpen(false); router.push("/account"); }}
          >
            Change password
          </button>
          <div className="h-px bg-border my-1" />
          <button
            className="w-full text-left px-3 py-2 text-sm text-bad hover:bg-panel"
            onClick={() => { setOpen(false); signOut(); }}
          >
            Sign out
          </button>
        </div>
      )}
    </div>
  );
}
