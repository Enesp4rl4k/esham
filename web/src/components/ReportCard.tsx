import Link from "next/link";
import {
  type Report,
  accentClasses,
  categoryLabel,
  formatDate,
  readingMinutes,
  CATEGORIES,
  getReportImageUrl,
} from "@/lib/content";

/**
 * Bir raporun liste/grid kartı. Ana sayfa, kategori sayfaları ve arşivde kullanılır.
 */
export function ReportCard({ report }: { report: Report }) {
  const accent = accentClasses(CATEGORIES[report.category].accent);
  const imageUrl = getReportImageUrl(report, 800, 400);

  return (
    <Link href={`/rapor/${report.slug}`} className="group block">
      <div
        className={`aspect-[2/1] rounded-2xl bg-zinc-900 mb-6 overflow-hidden border border-zinc-800 relative`}
      >
        {/* Görsel Arka Plan */}
        <img 
          src={imageUrl} 
          alt={report.title} 
          className="absolute inset-0 w-full h-full object-cover opacity-60 mix-blend-overlay transition-all duration-500 group-hover:opacity-100 group-hover:scale-105" 
          loading="lazy" 
        />
        <div className={`absolute inset-0 bg-gradient-to-tr ${accent.gradient}`} />
        <div className="absolute bottom-4 left-4">
          <span
            className={`px-3 py-1 bg-black/60 backdrop-blur-md rounded-lg text-xs font-medium border ${accent.badge}`}
          >
            {categoryLabel(report.category)}
          </span>
        </div>
      </div>
      <p className="text-sm text-zinc-500 mb-2">
        {formatDate(report.publishedAt)} • {readingMinutes(report.body)} dk okuma
      </p>
      <h3
        className={`text-2xl font-bold font-outfit mb-3 transition-colors ${accent.groupHoverText}`}
      >
        {report.title}
      </h3>
      <p className="text-zinc-400 line-clamp-2">{report.summary}</p>
    </Link>
  );
}
