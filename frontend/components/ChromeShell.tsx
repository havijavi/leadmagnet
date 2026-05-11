"use client";

import { usePathname } from "next/navigation";
import Sidebar from "./Sidebar";
import { useAuth } from "./AuthGate";

const PUBLIC_PATHS = new Set(["/login", "/setup"]);

// Routes that fill the whole viewport (no max-width, no padding).
// Used by the chat UI which has its own internal panels.
const FULL_BLEED_PATHS = new Set(["/chat"]);

/** Renders the sidebar+content shell for authenticated pages and bare children for /login + /setup. */
export default function ChromeShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname() || "/";
  const { user } = useAuth();
  const isPublic = PUBLIC_PATHS.has(pathname);
  const isFullBleed = FULL_BLEED_PATHS.has(pathname);

  if (isPublic || !user) {
    return <>{children}</>;
  }

  return (
    <div className="flex">
      <Sidebar />
      <main
        className={
          isFullBleed
            ? "flex-1 min-h-screen"
            : "flex-1 min-h-screen p-8 max-w-6xl"
        }
      >
        {children}
      </main>
    </div>
  );
}
