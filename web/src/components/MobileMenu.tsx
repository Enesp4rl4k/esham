"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Menu, X } from "lucide-react";

export function MobileMenu({
  navItems,
}: {
  navItems: { href: string; label: string }[];
}) {
  const [isOpen, setIsOpen] = useState(false);
  const pathname = usePathname();

  return (
    <div className="lg:hidden">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="p-2 text-zinc-400 hover:text-white transition-colors"
        aria-label="Menüyü aç/kapat"
      >
        {isOpen ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
      </button>

      {isOpen && (
        <div className="absolute top-14 left-0 w-full bg-zinc-950 border-b border-zinc-900 shadow-2xl py-4 flex flex-col px-6 gap-3 z-50 max-h-[80vh] overflow-y-auto">
          {navItems.map((item) => {
            const isActive =
              item.href === "/"
                ? pathname === "/"
                : pathname.startsWith(item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                onClick={() => setIsOpen(false)}
                className={`text-base font-medium transition-colors py-2 border-b border-zinc-900/50 ${
                  isActive
                    ? "text-amber-400"
                    : "text-zinc-300 hover:text-amber-400"
                }`}
              >
                {item.label}
              </Link>
            );
          })}
        </div>
      )}
    </div>
  );
}
