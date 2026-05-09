"use client";

const BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const TOKEN_KEY = "lm_auth_token";

export function getToken(): string {
  if (typeof window === "undefined") return "";
  return window.localStorage.getItem(TOKEN_KEY) || "";
}

export function setToken(t: string) {
  if (t) window.localStorage.setItem(TOKEN_KEY, t);
  else window.localStorage.removeItem(TOKEN_KEY);
  // Tell SWR to revalidate everywhere — listeners in AuthGate pick this up.
  window.dispatchEvent(new Event("lm:auth-changed"));
}

export function clearToken() {
  setToken("");
}

export async function api<T = any>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const token = getToken();
  const r = await fetch(`${BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(init.headers || {}),
    },
    cache: "no-store",
  });
  if (r.status === 401) {
    // Token rejected → bounce to login.
    clearToken();
    if (typeof window !== "undefined" && !window.location.pathname.startsWith("/login")) {
      window.location.href = "/login";
    }
  }
  if (!r.ok) {
    let detail: any = "";
    try {
      detail = await r.json();
    } catch {
      detail = await r.text();
    }
    const msg = detail?.detail || detail || r.statusText;
    throw new Error(typeof msg === "string" ? msg : JSON.stringify(msg));
  }
  if (r.status === 204) return undefined as unknown as T;
  return (await r.json()) as T;
}

export const fetcher = (path: string) => api(path);

export type Role = "admin" | "member" | "viewer";

export type CurrentUser = {
  id: string;
  email: string;
  name?: string;
  role: Role;
  is_active: boolean;
  last_login_at?: string;
  created_at: string;
};

// Role helpers used by the sidebar and pages to gate UI.
const RANK: Record<Role, number> = { viewer: 0, member: 1, admin: 2 };

export function hasRole(user: CurrentUser | null | undefined, minimum: Role): boolean {
  if (!user) return false;
  return RANK[user.role] >= RANK[minimum];
}
