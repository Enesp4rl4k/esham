import Link from "next/link";
import type { UniverseStock } from "@/lib/stocks";

const nf = new Intl.NumberFormat("tr-TR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const x = (v: number | null) => (typeof v === "number" ? `${nf.format(v)}x` : "—");
const p = (v: number | null) => (typeof v === "number" ? `%${nf.format(v)}` : "—");
const mcap = (v: number | null) => (typeof v !== "number" ? "—" : v >= 1e9 ? `${nf.format(v / 1e9)} Mr` : `${nf.format(v / 1e6)} Mn`);

/** Sunucuda çizilen, indekslenebilir hisse tablosu (sektör ve tarama sayfaları). */
export function StockTable({ rows, caption }: { rows: UniverseStock[]; caption: string }) {
  return (
    <div className="overflow-x-auto rounded-xl border border-zinc-800">
      <table className="w-full text-sm">
        <caption className="sr-only">{caption}</caption>
        <thead className="bg-zinc-900 text-zinc-400 text-xs">
          <tr>
            <th scope="col" className="text-left font-medium px-3 py-2.5">Hisse</th>
            {["Piyasa değ.", "F/K", "PD/DD", "ROE", "Temettü", "ND/FAVÖK"].map((h) => (
              <th key={h} scope="col" className="text-right font-medium px-3 py-2.5 whitespace-nowrap">{h}</th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-zinc-800/60 tabular-nums">
          {rows.map((s) => (
            <tr key={s.ticker} className="hover:bg-zinc-900/40">
              <th scope="row" className="text-left px-3 py-2.5 font-normal">
                <Link href={`/hisse/${s.ticker}`} className="font-bold text-white hover:underline">{s.ticker}</Link>
                <span className="block text-xs text-zinc-400 max-w-[16rem] truncate">{s.name}</span>
              </th>
              <td className="px-3 py-2.5 text-right">{mcap(s.market_cap)}</td>
              <td className="px-3 py-2.5 text-right">{x(s.pe)}</td>
              <td className="px-3 py-2.5 text-right">{x(s.pb)}</td>
              <td className="px-3 py-2.5 text-right">{p(s.roe)}</td>
              <td className="px-3 py-2.5 text-right">{p(s.dividend_yield)}</td>
              <td className="px-3 py-2.5 text-right">{s.financial ? "—" : x(s.net_debt_ebitda)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
