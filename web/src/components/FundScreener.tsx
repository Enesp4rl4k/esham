"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import { ArrowDown, ArrowUp, Search } from "lucide-react";
import { fmtMoney, fmtPct, sortBy, type FundRow } from "@/lib/funds";
import { fold } from "@/lib/fold";

type SortKey = "code" | "aum" | "r1m" | "r3m" | "ytd" | "r1y" | "real_1y" | "vol" | "mdd" | "fee";

const COLS: { key: Exclude<SortKey, "code">; label: string; title: string; kind: "money" | "ret" | "plain" }[] = [
  { key: "aum", label: "Büyüklük", title: "Portföy büyüklüğü (TL)", kind: "money" },
  { key: "r1m", label: "1 Ay", title: "1 aylık getiri", kind: "ret" },
  { key: "r3m", label: "3 Ay", title: "3 aylık getiri", kind: "ret" },
  { key: "ytd", label: "YBİ", title: "Yılbaşından beri getiri", kind: "ret" },
  { key: "r1y", label: "1 Yıl", title: "1 yıllık nominal getiri", kind: "ret" },
  { key: "real_1y", label: "Reel 1Y", title: "TÜFE'den arındırılmış 1 yıllık getiri", kind: "ret" },
  { key: "vol", label: "Oynaklık", title: "Son 1 yıl yıllıklandırılmış oynaklık", kind: "plain" },
  { key: "mdd", label: "Maks. düşüş", title: "Son 1 yılda zirveden en büyük düşüş", kind: "plain" },
  { key: "fee", label: "Yön. ücreti", title: "Uygulanan yıllık yönetim ücreti", kind: "plain" },
];

const ariaSort = (active: boolean, dir: 1 | -1) => (active ? (dir === 1 ? "ascending" : "descending") : "none");

export function FundScreener({ funds, categories }: { funds: FundRow[]; categories: string[] }) {
  const params = useSearchParams();
  const initialCat = params.get("kategori");
  const [q, setQ] = useState(params.get("q") ?? "");
  const [cat, setCat] = useState(initialCat && categories.includes(initialCat) ? initialCat : "");
  const [sort, setSort] = useState<{ key: SortKey; dir: 1 | -1 }>({ key: "aum", dir: -1 });

  // Filtre durumu URL'de: paylaşılabilir (history.replaceState, yeniden render yok)
  useEffect(() => {
    const u = new URL(window.location.href);
    const set = (k: string, v: string) => (v ? u.searchParams.set(k, v) : u.searchParams.delete(k));
    set("q", q.trim());
    set("kategori", cat);
    window.history.replaceState(null, "", u.pathname + u.search);
  }, [q, cat]);

  const rows = useMemo(() => {
    const fq = fold(q.trim());
    const f = funds.filter((x) => (!cat || x.category === cat) && (!fq || fold(x.code).includes(fq) || fold(x.name).includes(fq)));
    return sortBy(f, sort.key, sort.dir);
  }, [funds, q, cat, sort]);

  const toggle = (key: SortKey) =>
    setSort((s) => (s.key === key ? { key, dir: (s.dir * -1) as 1 | -1 } : { key, dir: key === "code" ? 1 : -1 }));
  const arrow = (key: SortKey) => sort.key === key && (sort.dir === 1 ? <ArrowUp className="w-3 h-3" /> : <ArrowDown className="w-3 h-3" />);

  return (
    <div>
      <div className="flex flex-col md:flex-row gap-3 mb-4">
        <label className="relative flex-1">
          <span className="sr-only">Fon ara</span>
          <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-zinc-400" />
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Fon kodu veya adı…"
            type="search"
            name="q"
            spellCheck={false}
            autoComplete="off"
            className="w-full pl-9 pr-3 py-2.5 rounded-lg bg-zinc-900 border border-zinc-800 text-sm text-white placeholder:text-zinc-400 focus:outline-none focus:border-amber-500/60"
          />
        </label>
        <select
          value={cat}
          onChange={(e) => setCat(e.target.value)}
          aria-label="Kategori"
          className="px-3 py-2.5 rounded-lg bg-zinc-900 border border-zinc-800 text-sm text-zinc-200 focus:outline-none focus:border-amber-500/60"
        >
          <option value="" className="bg-zinc-900 text-zinc-200">
            Tüm kategoriler
          </option>
          {categories.map((c) => (
            <option key={c} value={c} className="bg-zinc-900 text-zinc-200">
              {c}
            </option>
          ))}
        </select>
      </div>

      <p className="text-xs text-zinc-400 mb-2" aria-live="polite">
        {rows.length} fon
      </p>
      <div className="overflow-x-auto rounded-2xl border border-zinc-800">
        <table className="w-full text-sm">
          <thead className="bg-zinc-900/80 text-zinc-400">
            <tr>
              <th scope="col" className="text-left px-3 font-medium" aria-sort={ariaSort(sort.key === "code", sort.dir)}>
                <button type="button" onClick={() => toggle("code")} className="inline-flex items-center gap-1 hover:text-white min-h-[44px]">
                  Fon {arrow("code")}
                </button>
              </th>
              {COLS.map((c) => (
                <th key={c.key} scope="col" title={c.title} className="text-right px-3 font-medium whitespace-nowrap" aria-sort={ariaSort(sort.key === c.key, sort.dir)}>
                  <button type="button" onClick={() => toggle(c.key)} className="inline-flex items-center gap-1 hover:text-white min-h-[44px]">
                    {c.label} {arrow(c.key)}
                  </button>
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-800/70">
            {rows.map((f) => (
              <tr key={f.code} className="hover:bg-zinc-900/50">
                <td className="px-3 py-2 min-w-[14rem]">
                  <Link href={`/fon/${f.code}`} className="font-mono font-bold text-white hover:text-amber-300">
                    {f.code}
                  </Link>
                  <span className="block text-xs text-zinc-400 line-clamp-1">{f.name}</span>
                </td>
                {COLS.map((c) => {
                  const v = f[c.key] as number | null;
                  if (c.kind === "money") return <td key={c.key} className="px-3 py-2 text-right font-mono tabular-nums whitespace-nowrap text-zinc-200">{fmtMoney(v)}</td>;
                  if (c.kind === "plain" || v === null)
                    return <td key={c.key} className="px-3 py-2 text-right font-mono tabular-nums whitespace-nowrap text-zinc-200">{fmtPct(v)}</td>;
                  const up = v >= 0; // renk tek başına anlam taşımaz: ▲/▼ + metin
                  return (
                    <td key={c.key} className={`px-3 py-2 text-right font-mono tabular-nums whitespace-nowrap ${up ? "text-emerald-400" : "text-red-400"}`}>
                      {up ? "▲" : "▼"} {fmtPct(Math.abs(v))}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
