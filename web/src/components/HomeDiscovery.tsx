import Link from "next/link";
import { ArrowRight, ArrowUpRight } from "lucide-react";
import { HeroSearch } from "./HeroSearch";
import { buildLeaderboards, type Universe, type UniverseStock } from "@/lib/stocks";

const POPULAR = ["THYAO", "ASELS", "BIMAS", "GARAN", "EREGL", "KCHOL", "TUPRS", "FROTO"];
const nf = new Intl.NumberFormat("tr-TR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

const val = (v: unknown, unit: "x" | "%") => (typeof v === "number" ? (unit === "%" ? `%${nf.format(v)}` : `${nf.format(v)}x`) : "—");

function BoardRow({ s, metric, unit, rank }: { s: UniverseStock; metric: keyof UniverseStock; unit: "x" | "%"; rank: number }) {
  return (
    <li>
      <Link href={`/hisse/${s.ticker}`} className="flex items-center gap-3 py-2.5 hover:bg-zinc-900/50 -mx-2 px-2 rounded-lg transition-colors">
        <span className="w-4 text-xs font-mono text-zinc-400">{rank}</span>
        <span className="flex-1 min-w-0">
          <span className="block font-mono font-bold text-sm text-white">{s.ticker}</span>
          <span className="block text-xs text-zinc-400 truncate">{s.name}</span>
        </span>
        <span className="font-mono text-sm font-semibold tabular-nums" style={{ color: "var(--accent)" }}>
          {val(s[metric], unit)}
        </span>
      </Link>
    </li>
  );
}

/** İlk ekran şeridi: kompakt hisse arama + popüler kısayollar. (H1 görünmez; arama motorları ve ekran okuyucu için.) */
export function HomeStrip({ u }: { u: Universe | null }) {
  return (
    <section className="border-b" style={{ borderColor: "var(--border)" }}>
      <div className="container mx-auto px-6 py-3.5">
        <h1 className="sr-only">Esham: Borsa İstanbul’u rakamlarla okuyun</h1>
        <div className="flex flex-col lg:flex-row lg:items-center gap-3 lg:gap-5">
          {u && (
            <div className="lg:flex-1 lg:max-w-lg">
              <HeroSearch compact stocks={u.stocks.map((s) => ({ ticker: s.ticker, name: s.name, sector: s.sector }))} />
            </div>
          )}
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-xs" style={{ color: "var(--text-muted)" }}>Popüler:</span>
            {POPULAR.slice(0, 6).map((t) => (
              <Link
                key={t}
                href={`/hisse/${t}`}
                className="px-2.5 py-1 rounded-md text-xs font-mono font-semibold bg-zinc-900 border border-zinc-800 text-zinc-300 hover:text-white hover:border-zinc-600 transition-colors"
              >
                {t}
              </Link>
            ))}
            <Link href="/hisseler" className="ml-1 inline-flex items-center gap-1 text-sm font-semibold hover:opacity-80" style={{ color: "var(--accent)" }}>
              Hisse tarayıcı <ArrowRight className="w-3.5 h-3.5" />
            </Link>
          </div>
        </div>
      </div>
    </section>
  );
}

/** Hisse liderlik tabloları (kompakt: varsayılan 4 satır). */
export function StockLeaderboards({ u, rows = 4 }: { u: Universe; rows?: number }) {
  const boards = buildLeaderboards(u, rows).filter((b) => b.rows.length > 0);
  if (boards.length === 0) return null;
  return (
    <section className="py-8 border-b" style={{ borderColor: "var(--border)" }}>
      <div className="container mx-auto px-6">
        <div className="flex items-baseline justify-between mb-5">
          <h2 className="text-xs font-bold tracking-[0.15em] uppercase" style={{ color: "var(--text-muted)" }}>
            Hisse Liderlik Tabloları
          </h2>
          <Link href="/hisseler" className="text-xs flex items-center gap-1 hover:opacity-70" style={{ color: "var(--text-secondary)" }}>
            Tüm hisseler <ArrowUpRight className="w-3 h-3" />
          </Link>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {boards.map((b) => (
            <div key={b.title} className="rounded-2xl border p-4" style={{ borderColor: "var(--border)", background: "var(--surface)" }}>
              <h3 className="text-sm font-bold font-display">{b.title}</h3>
              <p className="text-xs mb-2" style={{ color: "var(--text-muted)" }}>
                {b.hint}
              </p>
              <ol className="divide-y divide-zinc-900">
                {b.rows.map((s, i) => (
                  <BoardRow key={s.ticker} s={s} metric={b.metric} unit={b.unit} rank={i + 1} />
                ))}
              </ol>
            </div>
          ))}
        </div>
        <p className="text-xs mt-3" style={{ color: "var(--text-muted)" }}>
          Piyasa değeri 5 milyar TL altı şirketler ve veri tutarsızlığı bayrağı taşıyanlar yer almaz. Veriler Yahoo Finance bilançolarına dayanır, KAP ile teyit edilmemiştir; yatırım tavsiyesi değildir.
        </p>
      </div>
    </section>
  );
}

/** Sektör kartları: hisse sayısı + medyan F/K ve ROE (en kalabalık 8 sektör). */
export function SectorCards({ u }: { u: Universe }) {
  const counts = new Map<string, number>();
  u.stocks.forEach((s) => counts.set(s.sector, (counts.get(s.sector) ?? 0) + 1));
  const sectorRows = [...counts.entries()]
    .sort((a, b) => b[1] - a[1])
    .slice(0, 8)
    .map(([name, n]) => ({ name, n, med: u.sector_median[name] ?? {} }));
  return (
    <section className="py-8 border-b" style={{ borderColor: "var(--border)" }}>
      <div className="container mx-auto px-6">
        <h2 className="text-xs font-bold tracking-[0.15em] uppercase mb-4" style={{ color: "var(--text-muted)" }}>
          Sektörlere Göre
        </h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {sectorRows.map((s) => (
            <Link
              key={s.name}
              href={`/hisseler?sector=${encodeURIComponent(s.name)}`}
              className="rounded-xl border p-4 hover:border-zinc-600 transition-colors"
              style={{ borderColor: "var(--border)", background: "var(--surface)" }}
            >
              <span className="block text-sm font-semibold">{s.name}</span>
              <span className="block text-xs mb-2" style={{ color: "var(--text-muted)" }}>
                {s.n} hisse
              </span>
              <span className="block text-xs font-mono text-zinc-400">
                F/K {val(s.med.pe, "x")} · ROE {val(s.med.roe, "%")}
              </span>
            </Link>
          ))}
        </div>
        <p className="text-xs mt-3" style={{ color: "var(--text-muted)" }}>
          Sektör değerleri medyandır; en az 3 hisseli sektörlerde gösterilir.
        </p>
      </div>
    </section>
  );
}
