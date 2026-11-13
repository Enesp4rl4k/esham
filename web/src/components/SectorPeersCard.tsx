import Link from "next/link";
import { Scale } from "lucide-react";
import type { UniverseStock } from "@/lib/stocks";

const nf = new Intl.NumberFormat("tr-TR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const x = (v: number | null) => (v === null ? "—" : `${nf.format(v)}x`);
const p = (v: number | null) => (v === null ? "—" : `%${nf.format(v)}`);

/** Aynı sektördeki hisseler — tek veri kaynağı: universe.json (RatiosCard ile aynı rakamlar). */
export function SectorPeersCard({
  ticker,
  sector,
  stocks,
  median,
}: {
  ticker: string;
  sector: string;
  stocks: UniverseStock[];
  median?: Record<string, number>;
}) {
  const peers = stocks
    .filter((s) => s.sector === sector)
    .sort((a, b) => (b.market_cap ?? 0) - (a.market_cap ?? 0))
    .slice(0, 8);
  if (peers.length < 3 || !peers.some((s) => s.ticker === ticker)) return null;

  return (
    <div className="rounded-2xl border border-zinc-800 bg-zinc-950/80 p-6 shadow-xl">
      <div className="flex items-center justify-between gap-2 pb-4 border-b border-zinc-800/80 mb-4">
        <div className="flex items-center gap-2">
          <span className="p-1.5 rounded-lg bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
            <Scale className="w-4 h-4" />
          </span>
          <h3 className="text-sm font-bold text-white tracking-tight">Sektör Karşılaştırması · {sector}</h3>
        </div>
        <Link href={`/hisseler?sector=${encodeURIComponent(sector)}`} className="text-xs text-zinc-400 hover:text-white">
          Tüm {sector} hisseleri
        </Link>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-xs min-w-[520px]">
          <thead className="text-zinc-500">
            <tr>
              <th className="text-left font-medium py-2">Hisse</th>
              <th className="text-right font-medium py-2">F/K</th>
              <th className="text-right font-medium py-2">PD/DD</th>
              <th className="text-right font-medium py-2">FD/FAVÖK</th>
              <th className="text-right font-medium py-2">ROE</th>
              <th className="text-right font-medium py-2">Net Marj</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-900 font-mono tabular-nums">
            {peers.map((s) => {
              const me = s.ticker === ticker;
              return (
                <tr key={s.ticker} className={me ? "bg-amber-500/5" : "hover:bg-zinc-900/50"} aria-current={me ? "true" : undefined}>
                  <td className="py-2.5">
                    <Link href={`/hisse/${s.ticker}`} className={`font-bold ${me ? "text-amber-300" : "text-white"}`}>
                      {s.ticker}
                    </Link>
                    <span className="ml-2 font-sans text-[11px] text-zinc-500">{s.name}</span>
                  </td>
                  <td className="py-2.5 text-right text-zinc-300">{x(s.pe)}</td>
                  <td className="py-2.5 text-right text-zinc-300">{x(s.pb)}</td>
                  <td className="py-2.5 text-right text-zinc-300">{x(s.ev_ebitda)}</td>
                  <td className="py-2.5 text-right text-zinc-300">{p(s.roe)}</td>
                  <td className="py-2.5 text-right text-zinc-300">{p(s.net_margin)}</td>
                </tr>
              );
            })}
            {median && (
              <tr className="text-zinc-500">
                <td className="py-2.5 font-sans">Sektör medyanı</td>
                <td className="py-2.5 text-right">{x(median.pe ?? null)}</td>
                <td className="py-2.5 text-right">{x(median.pb ?? null)}</td>
                <td className="py-2.5 text-right">—</td>
                <td className="py-2.5 text-right">{p(median.roe ?? null)}</td>
                <td className="py-2.5 text-right">{p(median.net_margin ?? null)}</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
