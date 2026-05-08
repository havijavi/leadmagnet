"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const items = [
  { href: "/", label: "Dashboard" },
  { href: "/services", label: "Services" },
  { href: "/sources", label: "Sources" },
  { href: "/discovery", label: "Discovery" },
  { href: "/leads", label: "Leads" },
  { href: "/campaigns", label: "Campaigns" },
];

export default function Sidebar() {
  const pathname = usePathname();
  return (
    <aside className="w-56 shrink-0 border-r border-border bg-panel min-h-screen p-4">
      <div className="mb-8 px-2">
        <div className="font-bold text-lg">⚡ LeadMagnet</div>
        <div className="text-xs text-muted">v0.1.0</div>
      </div>
      <nav className="flex flex-col gap-1">
        {items.map((item) => {
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
      </nav>
    </aside>
  );
}
