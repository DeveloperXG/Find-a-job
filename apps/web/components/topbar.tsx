import { Bell, Search } from "lucide-react";

import { ThemeToggle } from "@/components/theme-toggle";
import { Button } from "@/components/ui/button";

export function Topbar() {
  return (
    <header className="flex h-(--topbar-height) shrink-0 items-center gap-(--space-gap) border-b border-border px-(--space-page)">
      <form role="search" className="relative max-w-md flex-1">
        <Search
          className="absolute left-2 top-1/2 size-4 -translate-y-1/2 text-muted-foreground"
          aria-hidden
        />
        <input
          type="search"
          name="q"
          aria-label="Search jobs"
          placeholder="Search jobs"
          className="h-9 w-full rounded-lg border border-input bg-background pl-8 pr-3 text-sm outline-none focus-visible:ring-3 focus-visible:ring-ring/50"
        />
      </form>
      <div className="ml-auto flex items-center gap-1">
        <Button variant="ghost" size="icon" aria-label="Notifications">
          <Bell aria-hidden />
        </Button>
        <ThemeToggle />
      </div>
    </header>
  );
}
