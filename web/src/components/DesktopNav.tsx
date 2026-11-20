"use client";

import { useState, useRef } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { ChevronDown } from "lucide-react";
import { NAV, isGroupActive } from "@/lib/nav.config";

const pill = (active: boolean) =>
  `px-3 py-1.5 rounded-lg transition-colors ${
    active ? "text-white bg-zinc-900 border border-zinc-800" : "text-zinc-400 hover:text-white hover:bg-zinc-900/50"
  }`;

export function DesktopNav() {
  const pathname = usePathname();
  const [open, setOpen] = useState<string | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const enter = (key: string) => {
    if (timer.current) clearTimeout(timer.current);
    setOpen(key);
  };
  const leave = () => {
    timer.current = setTimeout(() => setOpen(null), 150);
  };

  return (
    <nav className="hidden lg:flex items-center gap-1 xl:gap-2 text-sm font-medium whitespace-nowrap" aria-label="Ana menü">
      {NAV.map((g) => {
        const active = isGroupActive(g, pathname);
        if (!g.items) {
          return (
            <Link key={g.key} href={g.href!} className={pill(active)} aria-current={active ? "page" : undefined}>
              {g.label}
            </Link>
          );
        }
        const isOpen = open === g.key;
        return (
          <div
            key={g.key}
            className="relative"
            onMouseEnter={() => enter(g.key)}
            onMouseLeave={leave}
            onKeyDown={(e) => e.key === "Escape" && setOpen(null)}
          >
            <button
              type="button"
              className={`flex items-center gap-1.5 ${pill(active || isOpen)}`}
              aria-expanded={isOpen}
              aria-haspopup="true"
              onClick={() => setOpen(isOpen ? null : g.key)}
            >
              <span>{g.label}</span>
              <ChevronDown className={`w-3.5 h-3.5 transition-transform duration-200 ${isOpen ? "rotate-180 text-amber-400" : "text-zinc-400"}`} />
            </button>
            {isOpen && (
              <div className="absolute top-full left-0 mt-1 w-80 rounded-xl border border-zinc-800 bg-zinc-950/95 p-2 shadow-2xl backdrop-blur-xl z-50">
                {g.items.map((item) => (
                  <Link
                    key={item.href}
                    href={item.href}
                    onClick={() => setOpen(null)}
                    className={`block p-2.5 rounded-lg transition-colors ${
                      pathname === item.href.split("?")[0] ? "bg-zinc-900 text-white" : "hover:bg-zinc-900/80 text-zinc-300 hover:text-white"
                    }`}
                  >
                    <span className="text-sm font-semibold block">{item.label}</span>
                    {item.description && <span className="text-xs text-zinc-400 mt-0.5 block font-normal whitespace-normal">{item.description}</span>}
                  </Link>
                ))}
              </div>
            )}
          </div>
        );
      })}
    </nav>
  );
}
