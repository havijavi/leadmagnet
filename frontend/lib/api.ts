"use client";

const BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

function getToken(): string {
  if (typeof window === "undefined") return "";
  return window.localStorage.getItem("admin_token") || "";
}

export function setToken(t: string) {
  window.localStorage.setItem("admin_token", t);
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
