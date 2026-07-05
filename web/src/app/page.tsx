import Link from "next/link";
import { ArrowRight, BarChart3, Globe, Activity, FileText } from "lucide-react";
import {
  getAllReports,
  formatDate,
  CATEGORIES,
  type CategorySlug,
} from "@/lib/content";
import { ReportCard } from "@/components/ReportCard";

const featureIcons: Partial<Record<CategorySlug, React.ReactNode>> = {
  bist: <BarChart3 className="w-6 h-6" />,
  global: <Globe className="w-6 h-6" />,
  ipo: <FileText className="w-6 h-6" />,
};

export default function Home() {
  const reports = getAllReports();
  const latest = reports.slice(0, 6);
  const lastPublished = reports[0];

  return (
    <div className="flex flex-col min-h-screen">
      {/* Hero */}
      <section className="relative pt-32 pb-20 overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-b from-cyan-900/20 to-black z-0" />
        <div className="container mx-auto px-6 relative z-10 text-center">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-zinc-900 border border-zinc-800 text-cyan-400 text-sm mb-8">
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-cyan-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2 w-2 bg-cyan-500"></span>
            </span>
            {lastPublished
              ? `Son rapor: ${formatDate(lastPublished.publishedAt)}`
              : "Yapay zeka analiz motoru hazır"}
          </div>
          <h1 className="text-5xl md:text-7xl font-outfit font-bold tracking-tight mb-6">
            Piyasaları{" "}
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-cyan-400 to-blue-600">
              Yapay Zeka
            </span>{" "}
            ile Okuyun
          </h1>
          <p className="text-lg md:text-xl text-zinc-400 max-w-2xl mx-auto mb-10 font-light">
            BIST, küresel makro veriler ve KAP halka arz raporları her gün yapay zeka
            tarafından analiz edilerek önünüze gelir. Sıfır gürültü, maksimum içgörü.
          </p>
          <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
            <Link
              href="/kategori/bist"
              className="px-8 py-4 rounded-full bg-white text-black font-medium hover:bg-zinc-200 transition-colors flex items-center gap-2"
            >
              Günün BIST Raporu <ArrowRight className="w-4 h-4" />
            </Link>
            <Link
              href="/kategori/global"
              className="px-8 py-4 rounded-full bg-zinc-900 border border-zinc-800 text-white font-medium hover:bg-zinc-800 transition-colors"
            >
              Küresel Piyasalar
            </Link>
          </div>
        </div>
      </section>

      {/* Kategoriler */}
      <section className="py-20 bg-zinc-950">
        <div className="container mx-auto px-6">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            {(["bist", "global", "ipo"] as CategorySlug[]).map((slug) => (
              <Link
                key={slug}
                href={`/kategori/${slug}`}
                className="p-8 rounded-3xl bg-zinc-900/50 border border-zinc-800/50 hover:bg-zinc-900 transition-colors"
              >
                <div className="w-12 h-12 rounded-full bg-cyan-950 flex items-center justify-center text-cyan-400 mb-6">
                  {featureIcons[slug]}
                </div>
                <h3 className="text-xl font-outfit font-bold mb-3">
                  {CATEGORIES[slug].label}
                </h3>
                <p className="text-zinc-400 leading-relaxed">
                  {CATEGORIES[slug].description}
                </p>
              </Link>
            ))}
          </div>
        </div>
      </section>

      {/* Son raporlar */}
      <section className="py-24">
        <div className="container mx-auto px-6">
          <div className="flex items-center justify-between mb-12">
            <h2 className="text-3xl font-outfit font-bold flex items-center gap-3">
              <Activity className="w-8 h-8 text-cyan-400" />
              Son Raporlar
            </h2>
            <Link
              href="/kategori/bist"
              className="text-sm text-cyan-400 hover:text-cyan-300"
            >
              Tümünü Gör
            </Link>
          </div>

          {latest.length === 0 ? (
            <div className="rounded-2xl border border-zinc-800 bg-zinc-900/40 p-12 text-center">
              <p className="text-zinc-400">
                Henüz rapor yayınlanmadı. Bot ilk bülteni ürettiğinde burada
                görünecek.
              </p>
              <p className="text-zinc-600 text-sm mt-2">
                <code className="text-cyan-400">py -m esham.main morning-report</code>
              </p>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-x-6 gap-y-12">
              {latest.map((report) => (
                <ReportCard key={report.slug} report={report} />
              ))}
            </div>
          )}
        </div>
      </section>
    </div>
  );
}
