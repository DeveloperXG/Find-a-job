"use client";

import {
  Briefcase,
  Building2,
  FileText,
  Inbox,
  Settings,
  Workflow,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { cn } from "@/lib/utils";

const NAV = [
  { href: "/feed", label: "Feed", icon: Inbox },
  { href: "/pipeline", label: "Pipeline", icon: Workflow },
  { href: "/resumes", label: "Resumes", icon: FileText },
  { href: "/companies", label: "Companies", icon: Building2 },
  { href: "/runs", label: "Runs", icon: Briefcase },
  { href: "/settings", label: "Settings", icon: Settings },
] as const;

export function Sidebar() {
  const pathname = usePathname();
  return (
    <aside
      className="flex w-(--sidebar-width) shrink-0 flex-col gap-(--space-gap) border-r border-sidebar-border bg-sidebar p-4 text-sidebar-foreground"
    >
      <div className="px-2 text-lg font-semibold">Job Tracker</div>
      <nav aria-label="Main">
        <ul className="flex flex-col gap-1">
          {NAV.map(({ href, label, icon: Icon }) => {
            const active = pathname === href || pathname.startsWith(`${href}/`);
            return (
              <li key={href}>
                <Link
                  href={href}
                  aria-current={active ? "page" : undefined}
                  className={cn(
                    "flex items-center gap-2 rounded-lg px-2 py-2 text-sm font-medium hover:bg-sidebar-accent hover:text-sidebar-accent-foreground",
                    active && "bg-sidebar-accent text-sidebar-accent-foreground",
                  )}
                >
                  <Icon className="size-4" aria-hidden />
                  {label}
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>
    </aside>
  );
}
