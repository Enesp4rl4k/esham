"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import { ArrowDown, ArrowUp, Search } from "lucide-react";
import type { UniverseStock } from "@/lib/stocks";
import { fold } from "@/lib/fold";

type SortKey = "ticker" | "market_cap" | "pe" | "pb" | "ev_ebitda" | "roe" | "net_margin" | "dividend_yield" | "net_debt_ebitda";

const COLS: { key: SortKey; label: string; unit?: "x" | "%" | "mcap"; title: string }[] = [
  { key: "market_cap", label: "Piyasa Değeri", unit: "mcap", title: "TL" },
  { key: "pe", label: "F/K", unit: "x", title: "Fiyat / Kazanç (son 12 ay)" },
  { key: "pb", label: "PD/DD", unit: "x", title: "Piyasa değeri / özkaynak" },
  { key: "ev_ebitda", label: "FD/FAVÖK", unit: "x", title: "Firma değeri / FAVÖK" },
  { key: "roe", label: "ROE", unit: "%", title: "Özkaynak karlılığı" },
  { key: "net_margin", label: "Net Marj", unit: "%", title: "Net kâr / hasılat" },
  { key: "dividend_yield", label: "Temettü", unit: "%", title: "Son 12 ay brüt temettü verimi" },
  { key: "net_debt_ebitda", label: "Net Borç/FAVÖK", unit: "x", title: "Bankalarda hesaplanmaz" },
];

type Preset = { id: string; label: string; test: (s: UniverseStock) => boolean };
const PRESETS: Preset[] = [
  { id: "ucuz", label: "Düşük F/K (<8)", test: (s) => s.pe !== null && s.pe > 0 && s.pe < 8 },
  { id: "roe", label: "Yüksek ROE (>%25)", test: (s) => s.roe !== null && s.roe > 25 && s.roe < 200 },
  { id: "temettu", label: "Temettü > %3", test: (s) => (s.dividend_yield ?? 0) > 3 },
  { id: "borc", label: "Düşük borç (ND/FAVÖK<1)", test: (s) => s.net_debt_ebitda !== null && s.net_debt_ebitda < 1 },
  { id: "iskonto", label: "PD/DD < 1", test: (s) => s.pb !== null && s.pb > 0 && s.pb < 1 },
];

const nf = new Intl.NumberFormat("tr-TR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
function fmt(v: number | null, unit?: "x" | "%" | "mcap"): string {
  if (v === null || v === undefined) return "—";
  if (unit === "mcap") return v >= 1e9 ? `${nf.format(v / 1e9)} Mr` : `${nf.format(v / 1e6)} Mn`;
  return unit === "%" ? `%${nf.format(v)}` : `${nf.format(v)}x`;
}

export function StockScreener({ stocks, sectors }: { stocks: UniverseStock[]; sectors: string[] }) {
  const params = useSearchParams();
  const initialSector = params.get("sector");
  const [q, setQ] = useState(params.get("q") ?? "");
  const [sector, setSector] = useState(initialSector && sectors.includes(initialSector) ? initialSector : "");
  const [active, setActive] = useState<string[]>(() => (params.get("f") ?? "").split(",").filter((id) => PRESETS.some((p) => p.id === id)));
  const [sort, setSort] = useState<{ key: SortKey; dir: 1 | -1 }>({ key: "market_cap", dir: -1 });

  // Filtre durumu URL'de: paylaşılabilir/geri-ileri uyumlu (history.replaceState, yeniden render yok)
  useEffect(() => {
    const u = new URL(window.location.href);
    const set = (k: string, v: string) => (v ? u.searchParams.set(k, v) : u.searchParams.delete(k));
    set("q", q.trim());
    set("sector", sector);
    set("f", active.join(","));
    window.history.replaceState(null, "", u.pathname + u.search);
  }, [q, sector, active]);

  const rows = useMemo(() => {
    const fq = fold(q.trim());
    const tests = PRESETS.filter((p) => active.includes(p.id)).map((p) => p.test);
    const out = stocks.filter(
      (s) =>
        (!sector || s.sector === sector) &&
        (!fq || fold(s.ticker).includes(fq) || fold(s.name).includes(fq)) &&
        tests.every((t) => t(s)),
    );
    return out.sort((a, b) => {
      if (sort.key === "ticker") return sort.dir * a.ticker.localeCompare(b.ticker);
      const av = a[sort.key], bv = b[sort.key];
      if (av === null) return 1; // boşlar hep sonda
      if (bv === null) return -1;
      return sort.dir * ((av as number) - (bv as number));
    });
  }, [stocks, q, sector, active, sort]);

  const toggleSort = (key: SortKey) =>
    setSort((s) => (s.key === key ? { key, dir: (s.dir * -1) as 1 | -1 } : { key, dir: key === "ticker" ? 1 : -1 }));

  return (
    <div>
      <div className="flex flex-col md:flex-row gap-3 mb-4">
        <label className="relative flex-1">
          <span className="sr-only">Hisse ara</span>
          <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-zinc-400" />
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Hisse kodu veya şirket adı…" type="search" name="q" spellCheck={false} autoComplete="off"
            className="w-full pl-9 pr-3 py-2.5 rounded-lg bg-zinc-900 border border-zinc-800 text-sm text-white placeholder:text-zinc-500 focus:outline-none focus:border-amber-500/60"
          />
        </label>
        <select
          value={sector}
          onChange={(e) => setSector(e.target.value)}
          aria-label="Sektör"
          className="px-3 py-2.5 rounded-lg bg-zinc-900 border border-zinc-800 text-sm text-zinc-200 focus:outline-none focus:border-amber-500/60"
        >
          <option value="" className="bg-zinc-900 text-zinc-200">Tüm sektörler</option>
          {sectors.map((s) => (
            <option key={s} value={s} className="bg-zinc-900 text-zinc-200">
              {s}
            </option>
          ))}
        </select>
      </div>

      <div className="flex flex-wrap gap-2 mb-4" role="group" aria-label="Hazır filtreler">
        {PRESETS.map((p) => {
          const on = active.includes(p.id);
          return (
            <button
              key={p.id}
              type="button"
              aria-pressed={on}
              onClick={() => setActive((a) => (on ? a.filter((x) => x !== p.id) : [...a, p.id]))}
              className={`px-3 py-1.5 rounded-full text-xs border transition-colors ${
                on
                  ? "bg-amber-500/15 border-amber-500/50 text-amber-300"
                  : "bg-zinc-900 border-zinc-800 text-zinc-400 hover:text-white hover:border-zinc-700"
              }`}
            >
              {p.label}
            </button>
          );
        })}
        {(active.length > 0 || sector || q) && (
          <button
            type="button"
            onClick={() => {
              setActive([]);
              setSector("");
              setQ("");
            }}
            className="px-3 py-1.5 text-xs text-zinc-400 hover:text-white"
          >
            Temizle
          </button>
        )}
      </div>

      <p className="text-xs text-zinc-400 mb-2" aria-live="polite">
        {rows.length} hisse
      </p>

      <div className="overflow-x-auto rounded-xl border border-zinc-800">
        <table className="w-full text-xs min-w-[860px]">
          <thead className="bg-zinc-900/80 text-zinc-400">
            <tr>
              <th aria-sort={sort.key === "ticker" ? (sort.dir === 1 ? "ascending" : "descending") : "none"} className="text-left font-medium px-3 py-2.5 sticky left-0 bg-zinc-900 z-10">
                <button type="button" onClick={() => toggleSort("ticker")} className="inline-flex items-center gap-1 hover:text-white">
                  Hisse {sort.key === "ticker" && (sort.dir === 1 ? <ArrowUp className="w-3 h-3" /> : <ArrowDown className="w-3 h-3" />)}
                </button>
              </th>
              <th className="text-left font-medium px-3 py-2.5 hidden lg:table-cell">Sektör</th>
              <th className="text-right font-medium px-3 py-2.5">Fiyat</th>
              {COLS.map((c) => (
                <th key={c.key} aria-sort={sort.key === c.key ? (sort.dir === 1 ? "ascending" : "descending") : "none"} className="text-right font-medium px-3 py-2.5" title={c.title}>
                  <button type="button" onClick={() => toggleSort(c.key)} className="inline-flex items-center gap-1 hover:text-white">
                    {c.label}
                    {sort.key === c.key && (sort.dir === 1 ? <ArrowUp className="w-3 h-3" /> : <ArrowDown className="w-3 h-3" />)}
                  </button>
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-900">
            {rows.map((s) => (
              <tr key={s.ticker} className="hover:bg-zinc-900/50">
                <td className="px-3 py-2.5 sticky left-0 bg-[#0a0a0a] z-10">
                  <Link href={`/hisse/${s.ticker}`} className="block">
                    <span className="font-mono font-bold text-white">{s.ticker}</span>
                    <span className="block text-xs text-zinc-400 truncate max-w-[150px]">{s.name}</span>
                  </Link>
                </td>
                <td className="px-3 py-2.5 text-zinc-400 hidden lg:table-cell">{s.sector}</td>
                <td className="px-3 py-2.5 text-right font-mono tabular-nums text-zinc-200">
                  {s.price !== null ? `${nf.format(s.price)} ₺` : "—"}
                </td>
                {COLS.map((c) => (
                  <td key={c.key} className="px-3 py-2.5 text-right font-mono tabular-nums text-zinc-300">
                    {fmt(s[c.key as keyof UniverseStock] as number | null, c.unit)}
                  </td>
                ))}
              </tr>
            ))}
            {rows.length === 0 && (
              <tr>
                <td colSpan={COLS.length + 3} className="px-3 py-10 text-center text-zinc-400">
                  Filtrelere uyan hisse yok.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
