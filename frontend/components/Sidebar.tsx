"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const groups: { label: string; items: { href: string; label: string }[] }[] = [
  {
    label: "Pipeline",
    items: [
      { href: "/", label: "Dashboard" },
      { href: "/services", label: "Services" },
      { href: "/sources", label: "Sources" },
      { href: "/discovery", label: "Discovery" },
      { href: "/import", label: "Import / Lists" },
    ],
  },
  {
    label: "Leads",
    items: [
      { href: "/leads", label: "All leads" },
      { href: "/enrichment", label: "Enrichment" },
      { href: "/campaigns", label: "Outreach" },
    ],
  },
  {
    label: "Automation",
    items: [
      { href: "/schedules", label: "Schedules" },
      { href: "/sheets", label: "Google Sheets" },
      { href: "/crm", label: "CRM webhooks" },
    ],
  },
];

export default function Sidebar() {
  const pathname = usePathname();
  return (
    <aside className="w-60 shrink-0 border-r border-border bg-panel min-h-screen p-4">
      <div className="mb-6 px-2">
        <div className="font-bold text-lg">⚡ LeadMagnet</div>
        <div className="text-xs text-muted">v0.3.0</div>
      </div>
      <nav className="flex flex-col gap-4">
        {groups.map((group) => (
          <div key={group.label}>
            <div className="px-3 text-[10px] uppercase tracking-wider text-muted mb-1">
              {group.label}
            </div>
            <div className="flex flex-col gap-0.5">
              {group.items.map((item) => {
                const active =
                  item.href === "/"
                    ? pathname === "/"
                    : pathname?.startsWith(item.href);
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    className={`px-3 py-2 rounded-lg text-sm transition ${
                      active
                        ? "bg-panel2 text-text"
                        : "text-muted hover:text-text hover:bg-panel2/50"
                    }`}
                  >
                    {item.label}
                  </Link>
                );
              })}
            </div>
          </div>
        ))}

        <div className="px-3 mt-4">
          <div className="text-[10px] uppercase tracking-wider text-muted mb-1">External</div>
          <a
            href="http://localhost:8000/docs"
            target="_blank"
            rel="noopener noreferrer"
            className="block px-3 py-2 rounded-lg text-sm text-muted hover:text-text"
          >
            API docs ↗
          </a>
        </div>
      </nav>
    </aside>
  );
}
