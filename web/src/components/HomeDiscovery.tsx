import Link from "next/link";
import { ArrowRight, ArrowUpRight } from "lucide-react";
import { HeroSearch } from "./HeroSearch";
import { buildLeaderboards, type Universe, type UniverseStock } from "@/lib/stocks";

const POPULAR = ["THYAO", "ASELS", "BIMAS", "GARAN", "EREGL", "KCHOL", "TUPRS", "FROTO"];
const nf = new Intl.NumberFormat("tr-TR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

const val = (v: unknown, unit: "x" | "%") => (typeof v === "number" ? (unit === "%" ? `%${nf.format(v)}` : `${nf.format(v)}x`) : "—");

/** Ana sayfanın ilk ekranı: değer önerisi + arama + veriden türetilen keşif bölümleri. */
export function HomeHero({ u }: { u: Universe | null }) {
  const sectors = u ? new Set(u.stocks.map((s) => s.sector)).size : 0;
  const asOf = u ? new Date(u.updated_at).toLocaleDateString("tr-TR", { day: "numeric", month: "long", year: "numeric" }) : null;

  return (
    <section className="py-12 md:py-20 border-b" style={{ borderColor: "var(--border)" }}>
      <div className="container mx-auto px-6">
        <h1 className="text-4xl md:text-6xl font-display font-bold leading-[1.05] max-w-3xl mb-5 [text-wrap:balance]">
          Borsa İstanbul’u <span style={{ color: "var(--accent)" }}>rakamlarla</span> okuyun.
        </h1>
        <p className="text-base md:text-lg max-w-2xl mb-8" style={{ color: "var(--text-secondary)" }}>
          {u ? `${u.count} hissenin` : "Hisselerin"} F/K, PD/DD, FAVÖK, ROE gibi oranlarını bilançolardan kendimiz hesaplıyor, her gün
          güncel raporlarla birlikte tek yerde sunuyoruz.
        </p>

        {u && <HeroSearch stocks={u.stocks.map((s) => ({ ticker: s.ticker, name: s.name, sector: s.sector }))} />}

        <div className="flex flex-wrap items-center gap-2 mt-5">
          <span className="text-xs" style={{ color: "var(--text-muted)" }}>
            Popüler:
          </span>
          {POPULAR.map((t) => (
            <Link
              key={t}
              href={`/hisse/${t}`}
              className="px-2.5 py-1 rounded-md text-xs font-mono font-semibold bg-zinc-900 border border-zinc-800 text-zinc-300 hover:text-white hover:border-zinc-600 transition-colors"
            >
              {t}
            </Link>
          ))}
        </div>

        <div className="flex flex-wrap items-center gap-3 mt-8">
          <Link
            href="/hisseler"
            className="inline-flex items-center gap-2 px-5 py-2.5 rounded-lg text-sm font-semibold text-black hover:opacity-90 transition-opacity"
            style={{ background: "var(--accent)" }}
          >
            Hisse Tarayıcıyı Aç <ArrowRight className="w-4 h-4" />
          </Link>
          <Link
            href="/arsiv"
            className="inline-flex items-center gap-2 px-5 py-2.5 rounded-lg text-sm font-semibold border border-zinc-700 text-zinc-200 hover:border-zinc-500 transition-colors"
          >
            Günlük Raporlar
          </Link>
          {u && (
            <span className="text-xs ml-1" style={{ color: "var(--text-muted)" }}>
              {u.count} hisse · {sectors} sektör · veri: {asOf}
            </span>
          )}
        </div>
      </div>
    </section>
  );
}

function BoardRow({ s, metric, unit, rank }: { s: UniverseStock; metric: keyof UniverseStock; unit: "x" | "%"; rank: number }) {
  return (
    <li>
      <Link href={`/hisse/${s.ticker}`} className="flex items-center gap-3 py-2.5 hover:bg-zinc-900/50 -mx-2 px-2 rounded-lg transition-colors">
        <span className="w-4 text-[11px] font-mono text-zinc-600">{rank}</span>
        <span className="flex-1 min-w-0">
          <span className="block font-mono font-bold text-sm text-white">{s.ticker}</span>
          <span className="block text-[11px] text-zinc-500 truncate">{s.name}</span>
        </span>
        <span className="font-mono text-sm font-semibold tabular-nums" style={{ color: "var(--accent)" }}>
          {val(s[metric], unit)}
        </span>
      </Link>
    </li>
  );
}

export function StockLeaderboards({ u }: { u: Universe }) {
  const boards = buildLeaderboards(u, 5).filter((b) => b.rows.length > 0);
  if (boards.length === 0) return null;

  // Sektör özeti: hisse sayısı + medyan F/K, ROE (en kalabalık 8 sektör)
  const counts = new Map<string, number>();
  u.stocks.forEach((s) => counts.set(s.sector, (counts.get(s.sector) ?? 0) + 1));
  const sectorRows = [...counts.entries()]
    .sort((a, b) => b[1] - a[1])
    .slice(0, 8)
    .map(([name, n]) => ({ name, n, med: u.sector_median[name] ?? {} }));

  return (
    <section className="py-12 border-b" style={{ borderColor: "var(--border)" }}>
      <div className="container mx-auto px-6">
        <div className="flex items-baseline justify-between mb-8">
          <h2 className="text-xs font-bold tracking-[0.15em] uppercase" style={{ color: "var(--text-muted)" }}>
            Verinin Öne Çıkardıkları
          </h2>
          <Link href="/hisseler" className="text-xs flex items-center gap-1 hover:opacity-70" style={{ color: "var(--text-secondary)" }}>
            Tüm hisseler <ArrowUpRight className="w-3 h-3" />
          </Link>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
          {boards.map((b) => (
            <div key={b.title} className="rounded-2xl border p-5" style={{ borderColor: "var(--border)", background: "var(--surface)" }}>
              <h3 className="text-sm font-bold font-display">{b.title}</h3>
              <p className="text-[11px] mb-3" style={{ color: "var(--text-muted)" }}>
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

        <h3 className="text-xs font-bold tracking-[0.15em] uppercase mt-12 mb-4" style={{ color: "var(--text-muted)" }}>
          Sektörlere Göre
        </h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {sectorRows.map((s) => (
            <Link
              key={s.name}
              href={`/hisseler?sector=${encodeURIComponent(s.name)}`}
              className="rounded-xl border p-4 hover:border-zinc-600 transition-colors"
              style={{ borderColor: "var(--border)", background: "var(--surface)" }}
            >
              <span className="block text-sm font-semibold">{s.name}</span>
              <span className="block text-[11px] mb-2" style={{ color: "var(--text-muted)" }}>
                {s.n} hisse
              </span>
              <span className="block text-[11px] font-mono text-zinc-400">
                F/K {val(s.med.pe, "x")} · ROE {val(s.med.roe, "%")}
              </span>
            </Link>
          ))}
        </div>
        <p className="text-[11px] mt-3" style={{ color: "var(--text-muted)" }}>
          Sektör değerleri medyandır; en az 3 hisseli sektörlerde gösterilir. Liderlik tablolarında piyasa değeri 5 milyar TL altı şirketler yer almaz. Veriler Yahoo Finance bilançolarına dayanır, KAP ile teyit edilmemiştir; yatırım tavsiyesi değildir.
        </p>
      </div>
    </section>
  );
}
