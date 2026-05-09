"use client";

import { usePathname, useRouter } from "next/navigation";
import { createContext, useContext, useEffect, useState } from "react";
import { CurrentUser, api, getToken } from "@/lib/api";

type AuthState = {
  user: CurrentUser | null;
  refresh: () => Promise<void>;
  signOut: () => void;
  loading: boolean;
};

const AuthCtx = createContext<AuthState>({
  user: null,
  refresh: async () => {},
  signOut: () => {},
  loading: true,
});

export const useAuth = () => useContext(AuthCtx);

const PUBLIC_PATHS = new Set(["/login", "/setup"]);

export default function AuthGate({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname() || "/";
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [loading, setLoading] = useState(true);

  async function refresh() {
    const token = getToken();
    if (!token) {
      setUser(null);
      setLoading(false);
      return;
    }
    try {
      const me = await api<CurrentUser>("/api/auth/me");
      setUser(me);
    } catch {
      setUser(null);
    } finally {
      setLoading(false);
    }
  }

  function signOut() {
    if (typeof window !== "undefined") {
      window.localStorage.removeItem("lm_auth_token");
    }
    setUser(null);
    router.push("/login");
  }

  // Initial load + react to login/logout from other tabs/components.
  useEffect(() => {
    refresh();
    const onChange = () => refresh();
    window.addEventListener("lm:auth-changed", onChange);
    window.addEventListener("storage", onChange);
    return () => {
      window.removeEventListener("lm:auth-changed", onChange);
      window.removeEventListener("storage", onChange);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Routing based on auth state.
  useEffect(() => {
    if (loading) return;

    const isPublic = PUBLIC_PATHS.has(pathname);

    // Decide between /setup and /login when not authenticated.
    if (!user && !isPublic) {
      (async () => {
        try {
          const r = await api<{ needs_setup: boolean }>("/api/auth/needs-setup");
          router.replace(r.needs_setup ? "/setup" : "/login");
        } catch {
          router.replace("/login");
        }
      })();
      return;
    }

    // Logged in but on a public page → kick them to dashboard.
    if (user && isPublic) {
      router.replace("/");
    }
  }, [user, loading, pathname, router]);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center text-muted">
        Loading…
      </div>
    );
  }

  // For public paths render the page itself (login/setup).
  if (PUBLIC_PATHS.has(pathname)) {
    return (
      <AuthCtx.Provider value={{ user, refresh, signOut, loading }}>
        {children}
      </AuthCtx.Provider>
    );
  }

  // For authenticated paths only render once we have a user (the effect
  // above will have redirected if not).
  if (!user) {
    return (
      <div className="min-h-screen flex items-center justify-center text-muted">
        Redirecting…
      </div>
    );
  }

  return (
    <AuthCtx.Provider value={{ user, refresh, signOut, loading }}>
      {children}
    </AuthCtx.Provider>
  );
}
