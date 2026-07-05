"use client";

import { useState } from "react";
import Link from "next/link";
import { Menu, X } from "lucide-react";

export function MobileMenu({
  navItems,
}: {
  navItems: { href: string; label: string }[];
}) {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <div className="md:hidden">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="p-2 text-zinc-400 hover:text-white transition-colors"
        aria-label="Menüyü aç/kapat"
      >
        {isOpen ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
      </button>

      {isOpen && (
        <div className="absolute top-16 left-0 w-full bg-zinc-950 border-b border-zinc-900 shadow-xl py-4 flex flex-col px-6 gap-4">
          {navItems.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              onClick={() => setIsOpen(false)}
              className="text-lg font-medium text-zinc-300 hover:text-cyan-400 transition-colors py-2 border-b border-zinc-900/50"
            >
              {item.label}
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
