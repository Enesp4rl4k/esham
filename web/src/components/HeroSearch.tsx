"use client";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { Search } from "lucide-react";
import { fold } from "@/lib/fold";

export interface StockLite {
  ticker: string;
  name: string;
  sector: string;
}

/** Ana sayfa hero arama kutusu: hisse kodu/adıyla anında öneri, Enter ile ilk sonuca git. */
export function HeroSearch({ stocks }: { stocks: StockLite[] }) {
  const router = useRouter();
  const [q, setQ] = useState("");
  const [i, setI] = useState(0);
  const [focus, setFocus] = useState(false);

  const results = useMemo(() => {
    const f = fold(q.trim());
    if (!f) return [];
    const starts = stocks.filter((s) => fold(s.ticker).startsWith(f));
    const rest = stocks.filter((s) => !fold(s.ticker).startsWith(f) && (fold(s.ticker).includes(f) || fold(s.name).includes(f)));
    return [...starts, ...rest].slice(0, 6);
  }, [q, stocks]);

  const go = (t: string) => router.push(`/hisse/${t}`);
  const open = focus && results.length > 0;

  return (
    <div className="relative w-full max-w-xl">
      <label className="sr-only" htmlFor="hero-search">
        Hisse ara
      </label>
      <Search className="w-5 h-5 absolute left-4 top-1/2 -translate-y-1/2 text-zinc-500 pointer-events-none" />
      <input
        id="hero-search"
        role="combobox"
        aria-expanded={open}
        aria-controls="hero-search-list"
        aria-autocomplete="list"
        autoComplete="off"
        value={q}
        onChange={(e) => {
          setQ(e.target.value);
          setI(0);
        }}
        onFocus={() => setFocus(true)}
        onBlur={() => setTimeout(() => setFocus(false), 120)}
        onKeyDown={(e) => {
          if (e.key === "ArrowDown") {
            e.preventDefault();
            setI((n) => Math.min(n + 1, results.length - 1));
          } else if (e.key === "ArrowUp") {
            e.preventDefault();
            setI((n) => Math.max(n - 1, 0));
          } else if (e.key === "Enter" && results[i]) {
            e.preventDefault();
            go(results[i].ticker);
          } else if (e.key === "Escape") {
            setFocus(false);
          }
        }}
        placeholder="Hisse ara: THYAO, Aselsan, bankacılık…"
        className="w-full pl-12 pr-4 py-4 rounded-xl bg-zinc-900 border border-zinc-800 text-base text-white placeholder:text-zinc-500 focus:outline-none focus:border-amber-500/60 focus:ring-2 focus:ring-amber-500/20"
      />
      {open && (
        <ul
          id="hero-search-list"
          role="listbox"
          className="absolute z-30 left-0 right-0 mt-2 rounded-xl border border-zinc-800 bg-zinc-950 shadow-2xl overflow-hidden"
        >
          {results.map((s, idx) => (
            <li key={s.ticker} role="option" aria-selected={idx === i}>
              <button
                type="button"
                onMouseDown={(e) => e.preventDefault()}
                onClick={() => go(s.ticker)}
                className={`w-full flex items-center justify-between gap-3 px-4 py-3 text-left ${idx === i ? "bg-zinc-900" : "hover:bg-zinc-900/60"}`}
              >
                <span>
                  <span className="font-mono font-bold text-white mr-2">{s.ticker}</span>
                  <span className="text-sm text-zinc-400">{s.name}</span>
                </span>
                <span className="text-[11px] text-zinc-500 shrink-0">{s.sector}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
