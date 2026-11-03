import Link from "next/link";
import { promises as fs } from "fs";
import path from "path";
import {
  ArrowUpRight,
  Wheat,
  Beef,
  TrendingUp,
  TrendingDown,
  Warehouse,
  ArrowRight,
  Database,
} from "lucide-react";
import {
  getAllReports,
  formatDate,
  CATEGORIES,
  type CategorySlug,
} from "@/lib/content";
import { ReportCard } from "@/components/ReportCard";
import { Newsletter } from "@/components/Newsletter";
import { TickerBand } from "@/components/TickerBand";
import { MarketMatrix } from "@/components/MarketMatrix";

// Kategori etiket renkleri — CSS değişkenleriyle
const catColors: Record<CategorySlug, string> = {
  bist:      "text-sky-400   border-sky-400/30   bg-sky-400/8",
  global:    "text-violet-400 border-violet-400/30 bg-violet-400/8",
  ipo:       "text-emerald-400 border-emerald-400/30 bg-emerald-400/8",
  viop:      "text-orange-400 border-orange-400/30 bg-orange-400/8",
  gundem:    "text-amber-400  border-amber-400/30  bg-amber-400/8",
  kripto:    "text-orange-300 border-orange-300/30 bg-orange-300/8",
  teknoloji: "text-pink-400   border-pink-400/30   bg-pink-400/8",
};

async function loadTuribSnapshot() {
  try {
    const filePath = path.join(process.cwd(), "public", "data", "turib-market.json");
    const raw = await fs.readFile(filePath, "utf-8");
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

async function loadMarketTickerData() {
  try {
    const filePath = path.join(process.cwd(), "public", "data", "market-ticker.json");
    const raw = await fs.readFile(filePath, "utf-8");
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

export default async function Home() {
  const reports = getAllReports();
  const latest = reports.slice(0, 6);
  const featured = reports[0];
  const secondary = reports.slice(1, 4);
  const turibData = await loadTuribSnapshot();
  const tickerData = await loadMarketTickerData();

  const trbHub = turibData?.indices?.find((i: any) => i.code === "TRBHUB");
  const bugdaySpot = turibData?.spotCommodities?.find((p: any) =>
    p.name.includes("BUĞDAY")
  );
  const danaYem = turibData?.meatFeed?.parities?.find((p: any) =>
    p.title?.includes("Dana")
  );
  const meatCpiPct = turibData?.meatFeed?.meatCpiAnnualPct;

  return (
    <div className="flex flex-col min-h-screen">

      {/* ── Ticker Bant — canlı fiyat (bot tarafından güncellenen JSON) ── */}
      <TickerBand />

      {/* ── Canlı Piyasa Matrisi & Terminal Widget ── */}
      <section className="border-b bg-zinc-950/40 py-4" style={{ borderColor: "var(--border)" }}>
        <div className="container mx-auto px-6">
          <MarketMatrix tickerData={tickerData} turibData={turibData} />
        </div>
      </section>

      {/* ── Hero — Editorial ────────────────────────────────────── */}
      <section className="py-16 md:py-24 border-b" style={{ borderColor: "var(--border)" }}>
        <div className="container mx-auto px-6">

          {/* Üst satır — tarih + etiket */}
          <div className="flex items-center justify-between mb-10">
            <div className="flex items-center gap-3">
              <span
                className="text-[10px] font-bold tracking-[0.15em] uppercase px-2.5 py-1 rounded border"
                style={{ color: "var(--accent)", borderColor: "var(--accent-dim)", background: "var(--accent-glow)" }}
              >
                Canlı Analiz
              </span>
              <span className="text-xs" style={{ color: "var(--text-muted)" }}>
                {featured ? formatDate(featured.publishedAt) : new Date().toLocaleDateString("tr-TR", { day: "numeric", month: "long", year: "numeric" })}
              </span>
            </div>
            <Link
              href="/arsiv"
              className="flex items-center gap-1 text-xs transition-opacity hover:opacity-70"
              style={{ color: "var(--text-secondary)" }}
            >
              Tüm raporlar <ArrowUpRight className="w-3 h-3" />
            </Link>
          </div>

          {/* İki sütun — öne çıkan + son raporlar */}
          {featured ? (
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-10 lg:gap-16">

              {/* Sol — öne çıkan rapor */}
              <div className="lg:col-span-7">
                <Link href={`/rapor/${featured.slug}`} className="group block">
                  <div
                    className="aspect-[16/9] rounded-xl overflow-hidden mb-6 relative"
                    style={{ background: "var(--surface)" }}
                  >
                    <img
                      src={featured.image ?? `/cards/default-${featured.category}.png`}
                      alt={featured.title}
                      className="w-full h-full object-cover opacity-80 group-hover:opacity-100 transition-opacity duration-500"
                    />
                    <div
                      className="absolute inset-0"
                      style={{ background: "linear-gradient(to top, rgba(10,10,10,0.6) 0%, transparent 60%)" }}
                    />
                    <div className="absolute bottom-4 left-4">
                      <span className={`text-[10px] font-bold tracking-wider uppercase px-2 py-1 rounded border ${catColors[featured.category]}`}>
                        {CATEGORIES[featured.category].label}
                      </span>
                    </div>
                  </div>
                  <p className="text-xs mb-3" style={{ color: "var(--text-muted)" }}>
                    {formatDate(featured.publishedAt)}
                  </p>
                  <h2
                    className="text-2xl md:text-3xl font-display font-bold leading-tight mb-3 group-hover:opacity-75 transition-opacity"
                    style={{ letterSpacing: "-0.02em" }}
                  >
                    {featured.title}
                  </h2>
                  <p className="text-sm leading-relaxed" style={{ color: "var(--text-secondary)" }}>
                    {featured.summary}
                  </p>
                </Link>
              </div>

              {/* Sağ — 3 küçük rapor */}
              <div className="lg:col-span-5 flex flex-col divide-y" style={{ borderColor: "var(--border)" }}>
                {secondary.map((report) => (
                  <Link
                    key={report.slug}
                    href={`/rapor/${report.slug}`}
                    className="group flex gap-4 py-5 first:pt-0 last:pb-0 hover:opacity-75 transition-opacity"
                  >
                    <div
                      className="w-20 h-16 rounded-lg overflow-hidden flex-shrink-0"
                      style={{ background: "var(--surface-2)" }}
                    >
                      <img
                        src={report.image ?? `/cards/default-${report.category}.png`}
                        alt=""
                        className="w-full h-full object-cover opacity-80"
                      />
                    </div>
                    <div className="flex-1 min-w-0">
                      <span className={`text-[10px] font-bold tracking-wider uppercase ${catColors[report.category].split(" ")[0]}`}>
                        {CATEGORIES[report.category].label}
                      </span>
                      <h3 className="text-sm font-semibold leading-snug mt-1 line-clamp-2">
                        {report.title}
                      </h3>
                      <p className="text-[11px] mt-1" style={{ color: "var(--text-muted)" }}>
                        {formatDate(report.publishedAt)}
                      </p>
                    </div>
                  </Link>
                ))}
                <div className="pt-5">
                  <Link
                    href="/arsiv"
                    className="flex items-center gap-2 text-sm font-medium transition-opacity hover:opacity-70"
                    style={{ color: "var(--accent)" }}
                  >
                    Tüm analizleri gör <ArrowUpRight className="w-4 h-4" />
                  </Link>
                </div>
              </div>

            </div>
          ) : (
            /* İçerik yokken */
            <div
              className="rounded-xl border p-16 text-center"
              style={{ borderColor: "var(--border)", background: "var(--surface)" }}
            >
              <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
                Henüz rapor yayınlanmadı.
              </p>
              <p className="text-xs mt-2" style={{ color: "var(--text-muted)" }}>
                <code className="text-amber-400">py -m esham.main morning-report</code>
              </p>
            </div>
          )}
        </div>
      </section>

      {/* ── TÜRİB ELÜS & Tarımsal Emtia Vitrini ─────────────────────── */}
      <section className="py-12 border-b" style={{ borderColor: "var(--border)", background: "rgba(232, 160, 48, 0.02)" }}>
        <div className="container mx-auto px-6">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-8">
            <div>
              <div className="flex items-center gap-2 mb-2">
                <span
                  className="text-[10px] font-bold tracking-[0.15em] uppercase px-2 py-0.5 rounded border"
                  style={{ color: "var(--accent)", borderColor: "var(--accent-dim)", background: "var(--accent-glow)" }}
                >
                  <Database className="w-3 h-3 inline mr-1" />
                  Piyasa Veri Seti
                </span>
                <span className="text-xs" style={{ color: "var(--text-muted)" }}>
                  TÜRİB + LİDAŞ + TÜİK + TMO
                </span>
              </div>
              <h2 className="text-xl md:text-2xl font-display font-bold">
                Tarımsal Emtia, TÜRİB & Et-Yem Terminali
              </h2>
            </div>

            <Link
              href="/tarim-emtia"
              className="inline-flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold border transition-all hover:scale-[1.02] self-start md:self-auto"
              style={{
                borderColor: "var(--accent)",
                color: "var(--accent)",
                background: "var(--accent-glow)",
              }}
            >
              Tüm Veri Terminalini İncele <ArrowRight className="w-4 h-4" />
            </Link>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {/* TRBHUB */}
            <Link
              href="/tarim-emtia"
              className="p-5 rounded-xl border transition-all hover:border-[var(--accent)] group"
              style={{ background: "var(--surface)", borderColor: "var(--border)" }}
            >
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-mono font-bold text-amber-400">TRBHUB</span>
                <span className="text-xs font-semibold text-emerald-400 flex items-center gap-0.5">
                  <TrendingUp className="w-3 h-3" />
                  {trbHub?.changeStr || "+2,12%"}
                </span>
              </div>
              <p className="text-2xl font-bold font-display">{trbHub?.valueStr || "7.910,25"}</p>
              <p className="text-[11px] mt-1 text-zinc-500">TÜRİB Hububat Endeksi</p>
            </Link>

            {/* Buğday Spot */}
            <Link
              href="/tarim-emtia"
              className="p-5 rounded-xl border transition-all hover:border-[var(--accent)] group"
              style={{ background: "var(--surface)", borderColor: "var(--border)" }}
            >
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-semibold text-zinc-300">Buğday Ekmeklik</span>
                <span className="text-xs font-semibold text-emerald-400 flex items-center gap-0.5">
                  <TrendingUp className="w-3 h-3" />
                  {bugdaySpot?.changeStr || "+5,40%"}
                </span>
              </div>
              <p className="text-2xl font-bold font-display" style={{ color: "var(--accent)" }}>
                {bugdaySpot?.avgPriceStr || "18,19 ₺/kg"}
              </p>
              <p className="text-[11px] mt-1 text-zinc-500">Lisanslı Depo (ELÜS) Spot</p>
            </Link>

            {/* Dana Besi / Yem */}
            <Link
              href="/tarim-emtia"
              className="p-5 rounded-xl border transition-all hover:border-[var(--accent)] group"
              style={{ background: "var(--surface)", borderColor: "var(--border)" }}
            >
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-semibold text-zinc-300">Dana Besi / Yem</span>
                <span className="text-[10px] font-semibold px-1.5 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                  {danaYem?.status || "KÂRLI BESI"}
                </span>
              </div>
              <p className="text-2xl font-bold font-display text-emerald-400">
                {danaYem?.ratio ? `${danaYem.ratio.toFixed(1)}x` : "28.2x"}
              </p>
              <p className="text-[11px] mt-1 text-zinc-500">1 kg et = 28.2 kg yem (Eşik: 20)</p>
            </Link>

            {/* Et TÜFE */}
            <Link
              href="/tarim-emtia"
              className="p-5 rounded-xl border transition-all hover:border-[var(--accent)] group"
              style={{ background: "var(--surface)", borderColor: "var(--border)" }}
            >
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-semibold text-rose-400">Et TÜFE (Yıllık)</span>
                <span className="text-xs text-zinc-400">Manşet: %31.5</span>
              </div>
              <p className="text-2xl font-bold font-display">
                %{meatCpiPct ? meatCpiPct.toFixed(1) : "30.5"}
              </p>
              <p className="text-[11px] mt-1 text-zinc-500">Enflasyon Primi: -1.0 puan</p>
            </Link>
          </div>
        </div>
      </section>

      {/* ── Kategori Şeridi ──────────────────────────────────────── */}
      <section className="py-14 border-b" style={{ borderColor: "var(--border)" }}>
        <div className="container mx-auto px-6">
          <div className="flex items-baseline justify-between mb-8">
            <h2 className="text-xs font-bold tracking-[0.15em] uppercase" style={{ color: "var(--text-muted)" }}>
              Kapsama Alanları
            </h2>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3">
            {(Object.keys(CATEGORIES) as CategorySlug[]).map((slug) => (
              <Link
                key={slug}
                href={`/kategori/${slug}`}
                className="group p-5 rounded-xl border transition-all duration-200 hover:scale-[1.02]"
                style={{
                  borderColor: "var(--border)",
                  background: "var(--surface)",
                }}
              >
                <div className="mb-3">
                  <span className={`text-[10px] font-bold tracking-wider uppercase px-2 py-0.5 rounded border ${catColors[slug]}`}>
                    {slug.toUpperCase()}
                  </span>
                </div>
                <p className="text-sm font-semibold leading-snug mb-1 group-hover:opacity-75 transition-opacity">
                  {CATEGORIES[slug].label}
                </p>
                <p className="text-xs leading-relaxed line-clamp-2" style={{ color: "var(--text-muted)" }}>
                  {CATEGORIES[slug].description}
                </p>
              </Link>
            ))}
          </div>
        </div>
      </section>

      {/* ── Son Raporlar Grid ────────────────────────────────────── */}
      {latest.length > 0 && (
        <section className="py-20">
          <div className="container mx-auto px-6">
            <div className="flex items-baseline justify-between mb-10">
              <h2 className="text-xs font-bold tracking-[0.15em] uppercase" style={{ color: "var(--text-muted)" }}>
                Son Yayınlar
              </h2>
              <Link
                href="/arsiv"
                className="text-xs flex items-center gap-1 transition-opacity hover:opacity-70"
                style={{ color: "var(--text-secondary)" }}
              >
                Arşiv <ArrowUpRight className="w-3 h-3" />
              </Link>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
              {latest.map((report) => (
                <ReportCard key={report.slug} report={report} />
              ))}
            </div>
          </div>
        </section>
      )}

      {/* ── Newsletter ───────────────────────────────────────────── */}
      <Newsletter />

    </div>
  );
}
