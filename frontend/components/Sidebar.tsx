"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "./AuthGate";
import UserMenu from "./UserMenu";
import { Role } from "@/lib/api";

type Item = { href: string; label: string; minRole: Role };
type Group = { label: string; items: Item[] };

const RANK: Record<Role, number> = { viewer: 0, member: 1, admin: 2 };

const GROUPS: Group[] = [
  {
    label: "Pipeline",
    items: [
      { href: "/", label: "Dashboard", minRole: "viewer" },
      { href: "/services", label: "Services", minRole: "viewer" },
      { href: "/sources", label: "Sources", minRole: "viewer" },
      { href: "/discovery", label: "Discovery", minRole: "member" },
      { href: "/import", label: "Import / Lists", minRole: "member" },
    ],
  },
  {
    label: "Leads",
    items: [
      { href: "/leads", label: "All leads", minRole: "viewer" },
      { href: "/enrichment", label: "Enrichment", minRole: "member" },
      { href: "/campaigns", label: "Outreach", minRole: "viewer" },
    ],
  },
  {
    label: "Automation",
    items: [
      { href: "/schedules", label: "Schedules", minRole: "viewer" },
      { href: "/sheets", label: "Google Sheets", minRole: "viewer" },
      { href: "/crm", label: "CRM webhooks", minRole: "admin" },
    ],
  },
  {
    label: "Admin",
    items: [
      { href: "/admin/llm", label: "LLM providers", minRole: "admin" },
      { href: "/admin/users", label: "Users", minRole: "admin" },
    ],
  },
];

export default function Sidebar() {
  const pathname = usePathname();
  const { user } = useAuth();
  const role: Role = (user?.role as Role) || "viewer";

  return (
    <aside className="w-60 shrink-0 border-r border-border bg-panel min-h-screen p-4 flex flex-col">
      <div className="mb-6 px-2">
        <div className="font-bold text-lg">⚡ LeadMagnet</div>
        <div className="text-xs text-muted">v0.5.0</div>
      </div>

      <nav className="flex flex-col gap-4 flex-1">
        {GROUPS.map((group) => {
          const visible = group.items.filter((i) => RANK[role] >= RANK[i.minRole]);
          if (visible.length === 0) return null;
          return (
            <div key={group.label}>
              <div className="px-3 text-[10px] uppercase tracking-wider text-muted mb-1">
                {group.label}
              </div>
              <div className="flex flex-col gap-0.5">
                {visible.map((item) => {
                  const active =
                    item.href === "/"
                      ? pathname === "/"
                      : pathname?.startsWith(item.href);
                  const restricted = item.minRole === "admin" && role !== "admin";
                  return (
                    <Link
                      key={item.href}
                      href={item.href}
                      className={`px-3 py-2 rounded-lg text-sm transition flex items-center justify-between ${
                        active
                          ? "bg-panel2 text-text"
                          : "text-muted hover:text-text hover:bg-panel2/50"
                      }`}
                    >
                      <span>{item.label}</span>
                      {restricted && (
                        <span className="text-[9px] uppercase text-muted">admin</span>
                      )}
                    </Link>
                  );
                })}
              </div>
            </div>
          );
        })}

        <div className="px-3 mt-4">
          <div className="text-[10px] uppercase tracking-wider text-muted mb-1">External</div>
          <a
            href="/docs"
            target="_blank"
            rel="noopener noreferrer"
            className="block px-3 py-2 rounded-lg text-sm text-muted hover:text-text"
          >
            API docs ↗
          </a>
        </div>
      </nav>

      <div className="border-t border-border pt-2 mt-2">
        <UserMenu />
      </div>
    </aside>
  );
}
