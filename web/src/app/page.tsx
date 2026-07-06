import Link from "next/link";
import { ArrowUpRight } from "lucide-react";
import {
  getAllReports,
  formatDate,
  CATEGORIES,
  type CategorySlug,
} from "@/lib/content";
import { ReportCard } from "@/components/ReportCard";
import { Newsletter } from "@/components/Newsletter";
import { TickerBand } from "@/components/TickerBand";

// Kategori etiket renkleri — CSS değişkenleriyle
const catColors: Record<CategorySlug, string> = {
  bist:   "text-sky-400   border-sky-400/30   bg-sky-400/8",
  global: "text-violet-400 border-violet-400/30 bg-violet-400/8",
  ipo:    "text-emerald-400 border-emerald-400/30 bg-emerald-400/8",
  viop:   "text-orange-400 border-orange-400/30 bg-orange-400/8",
  gundem: "text-amber-400  border-amber-400/30  bg-amber-400/8",
};

export default async function Home() {
  const reports = getAllReports();
  const latest = reports.slice(0, 6);
  const featured = reports[0];
  const secondary = reports.slice(1, 4);

  return (
    <div className="flex flex-col min-h-screen">

      {/* ── Ticker Bant — canlı fiyat (bot tarafından güncellenen JSON) ── */}
      <TickerBand />

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
