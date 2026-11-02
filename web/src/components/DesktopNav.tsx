"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

export function DesktopNav({
  navItems,
}: {
  navItems: { href: string; label: string }[];
}) {
  const pathname = usePathname();

  return (
    <nav className="hidden lg:flex items-center gap-4 xl:gap-5 text-xs xl:text-sm whitespace-nowrap">
      {navItems.map((item) => {
        const isActive =
          item.href === "/"
            ? pathname === "/"
            : pathname.startsWith(item.href);
        return (
          <Link
            key={item.href}
            href={item.href}
            className="transition-colors relative pb-0.5"
            style={{
              color: isActive ? "var(--text-primary)" : "var(--text-secondary)",
              fontWeight: isActive ? 500 : 400,
            }}
          >
            {item.label}
            {isActive && (
              <span
                className="absolute bottom-0 left-0 w-full h-px"
                style={{ background: "var(--accent)" }}
              />
            )}
          </Link>
        );
      })}
    </nav>
  );
}
