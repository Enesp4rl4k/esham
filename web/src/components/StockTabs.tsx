"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";

export interface TabDef {
  id: string;
  label: string;
  content: ReactNode;
}

/**
 * Sekmeli düzen. Tüm paneller sunucuda render edilir (SEO/erişilebilirlik); etkin olmayanlar `hidden`.
 * Etkin sekme URL hash'inde (#finansallar) tutulur → paylaşılabilir, geri/ileri çalışır.
 */
export function StockTabs({ tabs }: { tabs: TabDef[] }) {
  const [active, setActive] = useState(tabs[0]?.id);
  const refs = useRef<Record<string, HTMLButtonElement | null>>({});

  useEffect(() => {
    const fromHash = () => {
      const h = window.location.hash.replace("#", "");
      if (tabs.some((t) => t.id === h)) setActive(h);
    };
    fromHash();
    window.addEventListener("hashchange", fromHash);
    return () => window.removeEventListener("hashchange", fromHash);
  }, [tabs]);

  const select = (id: string, focus = false) => {
    setActive(id);
    window.history.replaceState(null, "", `#${id}`);
    if (focus) refs.current[id]?.focus();
  };

  const onKey = (e: React.KeyboardEvent, i: number) => {
    const dir = e.key === "ArrowRight" ? 1 : e.key === "ArrowLeft" ? -1 : 0;
    if (e.key === "Home" || e.key === "End") {
      e.preventDefault();
      select(tabs[e.key === "Home" ? 0 : tabs.length - 1].id, true);
    } else if (dir) {
      e.preventDefault();
      select(tabs[(i + dir + tabs.length) % tabs.length].id, true);
    }
  };

  return (
    <div>
      <div
        role="tablist"
        aria-label="Hisse bölümleri"
        className="sticky top-14 z-30 -mx-6 px-6 mb-8 flex gap-1 overflow-x-auto border-b border-zinc-800 bg-[#0a0a0a]/95 backdrop-blur [scrollbar-width:none]"
      >
        {tabs.map((t, i) => (
          <button
            key={t.id}
            ref={(el) => {
              refs.current[t.id] = el;
            }}
            role="tab"
            id={`tab-${t.id}`}
            aria-selected={active === t.id}
            aria-controls={`panel-${t.id}`}
            tabIndex={active === t.id ? 0 : -1}
            onClick={() => select(t.id)}
            onKeyDown={(e) => onKey(e, i)}
            className={`whitespace-nowrap px-4 py-3 text-sm font-medium border-b-2 -mb-px transition-colors ${
              active === t.id ? "border-amber-400 text-white" : "border-transparent text-zinc-400 hover:text-white"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tabs.map((t) => (
        <section key={t.id} role="tabpanel" id={`panel-${t.id}`} aria-labelledby={`tab-${t.id}`} hidden={active !== t.id} className="space-y-10 scroll-mt-32">
          {t.content}
        </section>
      ))}
    </div>
  );
}
