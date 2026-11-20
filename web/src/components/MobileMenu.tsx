"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Menu, X, ChevronRight } from "lucide-react";
import { NAV } from "@/lib/nav.config";

export function MobileMenu() {
  const [isOpen, setIsOpen] = useState(false);
  const pathname = usePathname();
  const close = () => setIsOpen(false);

  return (
    <div className="lg:hidden">
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className="inline-flex items-center justify-center w-11 h-11 text-zinc-400 hover:text-white transition-colors"
        aria-label="Menüyü aç/kapat"
        aria-expanded={isOpen}
      >
        {isOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
      </button>

      {isOpen && (
        <div className="fixed inset-x-0 top-14 bottom-0 bg-zinc-950/98 shadow-2xl py-5 px-6 z-50 overflow-y-auto backdrop-blur-2xl flex flex-col gap-6">
          {NAV.map((g) => (
            <div key={g.key}>
              {g.href ? (
                <Link
                  href={g.href}
                  onClick={close}
                  className={`block py-2 text-base font-semibold ${pathname.startsWith(g.href) ? "text-amber-400" : "text-white hover:text-amber-400"}`}
                >
                  {g.label}
                </Link>
              ) : (
                <div className="text-xs font-mono uppercase tracking-wider text-zinc-400 mb-2">{g.label}</div>
              )}
              {g.items && (
                <div className="space-y-0.5">
                  {g.items.map((item) => (
                    <Link
                      key={item.href}
                      href={item.href}
                      onClick={close}
                      className="flex items-center justify-between min-h-11 text-base text-zinc-200 hover:text-white"
                    >
                      <span>{item.label}</span>
                      <ChevronRight className="w-4 h-4 text-zinc-400" />
                    </Link>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
