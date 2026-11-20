import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { HeroSearch } from "./HeroSearch";
import type { Universe, UniverseStock } from "@/lib/stocks";

const POPULAR = ["THYAO", "ASELS", "BIMAS", "GARAN", "EREGL", "TUPRS"];
const nf = new Intl.NumberFormat("tr-TR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const x = (v: number | null) => (typeof v === "number" ? `${nf.format(v)}x` : "—");
const pct = (v: number | null) => (typeof v === "number" ? `%${nf.format(v)}` : "—");

/** Hazır taramalar: StockScreener'daki ön ayar kimlikleriyle (?f=) aynı; sayılar evrenden hesaplanır. */
const SCANS: { id: string; title: string; hint: string; test: (s: UniverseStock) => boolean }[] = [
  { id: "ucuz", title: "Düşük F/K", hint: "F/K 8'in altı", test: (s) => s.pe !== null && s.pe > 0 && s.pe < 8 },
  { id: "roe", title: "Yüksek ROE", hint: "%25 üzeri", test: (s) => s.roe !== null && s.roe > 25 && s.roe < 200 },
  { id: "temettu", title: "Temettü", hint: "Verim %3 üzeri", test: (s) => (s.dividend_yield ?? 0) > 3 },
  { id: "borc", title: "Düşük borç", hint: "ND/FAVÖK < 1", test: (s) => s.net_debt_ebitda !== null && s.net_debt_ebitda < 1 },
];

function PreviewCard({ s, median }: { s: UniverseStock; median?: number }) {
  const rel = typeof s.pe === "number" && typeof median === "number" && median > 0 ? s.pe / median : null;
  // Konum çubuğu: F/K'nın sektör medyanına göre konumu (0.5x–1.5x aralığı)
  const pos = rel === null ? null : Math.min(100, Math.max(0, ((rel - 0.5) / 1) * 100));
  return (
    <Link
      href={`/hisse/${s.ticker}`}
      className="block rounded-2xl border p-5 hover:border-zinc-600 transition-colors"
      style={{ borderColor: "var(--border)", background: "var(--surface)" }}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="font-bold text-xl">{s.ticker}</div>
          <div className="text-sm truncate" style={{ color: "var(--text-muted)" }}>{s.sector}</div>
        </div>
        <div className="text-right tabular-nums">
          <div className="font-bold text-xl">{typeof s.price === "number" ? `${nf.format(s.price)} ₺` : "—"}</div>
        </div>
      </div>
      {pos !== null && (
        <div className="mt-4">
          <div className="flex justify-between text-xs" style={{ color: "var(--text-muted)" }}>
            <span>Sektör medyanından ucuz</span>
            <span>pahalı</span>
          </div>
          <div className="relative h-2 rounded-full mt-1.5 bg-zinc-800" role="img" aria-label={`F/K sektör medyanının ${nf.format(rel!)} katı`}>
            <span className="absolute -top-1 w-1.5 h-4 rounded-sm -translate-x-1/2" style={{ left: `${pos}%`, background: "var(--accent)" }} />
          </div>
          <div className="text-xs mt-1.5 tabular-nums" style={{ color: "var(--text-secondary)" }}>
            F/K {x(s.pe)} · sektör medyanı {x(median ?? null)}
          </div>
        </div>
      )}
      <dl className="mt-4 grid grid-cols-3 gap-3 tabular-nums">
        {[
          ["PD/DD", x(s.pb)],
          ["ROE", pct(s.roe)],
          ["Temettü", pct(s.dividend_yield)],
        ].map(([k, v]) => (
          <div key={k}>
            <dt className="text-xs" style={{ color: "var(--text-muted)" }}>{k}</dt>
            <dd className="font-semibold">{v}</dd>
          </div>
        ))}
      </dl>
    </Link>
  );
}

/** Ana sayfa ilk ekranı: vaat + arama + gerçek hisse önizlemesi + hazır taramalar. */
export function HomeHero({ u }: { u: Universe | null }) {
  const preview = u?.stocks.find((s) => s.ticker === "BIMAS" && !s.suspect) ?? u?.stocks.find((s) => !s.suspect && s.pe !== null);
  const scans = u ? SCANS.map((sc) => ({ ...sc, n: u.stocks.filter((s) => !s.suspect && sc.test(s)).length })) : [];
  return (
    <section className="border-b" style={{ borderColor: "var(--border)" }}>
      <div className="container mx-auto px-6 py-8 md:py-12">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 lg:gap-12 items-center">
          <div className="lg:col-span-7">
            <p className="text-sm font-semibold mb-2" style={{ color: "var(--text-muted)" }}>Borsa İstanbul için hisse analiz aracı</p>
            <h1 className="font-display font-extrabold text-4xl md:text-5xl leading-[1.05] mb-4" style={{ letterSpacing: "-0.03em" }}>
              Her hisseyi rakamlarla anla.
            </h1>
            <p className="text-base md:text-lg mb-6 max-w-xl" style={{ color: "var(--text-secondary)" }}>
              {u ? `${u.count} hissenin` : "Hisselerin"} oranları, finansalları ve değerlemesi. Bilançodan hesaplanır, kaynağı yanında yazar.
            </p>
            {u && <HeroSearch stocks={u.stocks.map((s) => ({ ticker: s.ticker, name: s.name, sector: s.sector }))} />}
            <div className="mt-4 flex flex-wrap items-center gap-2">
              <span className="text-sm" style={{ color: "var(--text-muted)" }}>Popüler:</span>
              {POPULAR.map((t) => (
                <Link
                  key={t}
                  href={`/hisse/${t}`}
                  className="inline-flex items-center min-h-11 px-3.5 rounded-lg text-sm font-semibold bg-zinc-900 border border-zinc-800 text-zinc-200 hover:text-white hover:border-zinc-600 transition-colors"
                >
                  {t}
                </Link>
              ))}
            </div>
          </div>
          {preview && u && (
            <div className="lg:col-span-5">
              <PreviewCard s={preview} median={u.sector_median[preview.sector]?.pe} />
            </div>
          )}
        </div>

        {scans.length > 0 && (
          <div className="mt-8">
            <div className="flex items-baseline justify-between mb-3">
              <h2 className="text-lg font-display font-semibold text-white">Hazır taramalar</h2>
              <Link href="/hisseler" className="inline-flex items-center gap-1 text-sm font-semibold hover:opacity-80" style={{ color: "var(--accent)" }}>
                Hisse tarayıcı <ArrowRight className="w-3.5 h-3.5" />
              </Link>
            </div>
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
              {scans.map((sc) => (
                <Link
                  key={sc.id}
                  href={`/hisseler?f=${sc.id}`}
                  className="rounded-xl border p-4 min-h-11 hover:border-zinc-600 transition-colors"
                  style={{ borderColor: "var(--border)", background: "var(--surface)" }}
                >
                  <span className="block font-bold">{sc.title}</span>
                  <span className="block text-sm" style={{ color: "var(--text-muted)" }}>{sc.hint}</span>
                  <span className="block text-sm mt-1.5 font-semibold tabular-nums" style={{ color: "var(--text-secondary)" }}>{sc.n} hisse</span>
                </Link>
              ))}
            </div>
          </div>
        )}
      </div>
    </section>
  );
}
