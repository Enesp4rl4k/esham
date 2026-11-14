import Link from "next/link";
import {
  type Report,
  type CategorySlug,
  CATEGORIES,
  formatDate,
  readingMinutes,
  getReportImageUrl,
} from "@/lib/content-utils";

const catColor: Record<CategorySlug, string> = {
  bist:      "text-sky-400",
  global:    "text-violet-400",
  ipo:       "text-emerald-400",
  viop:      "text-orange-400",
  gundem:    "text-amber-400",
  kripto:    "text-orange-300",
  teknoloji: "text-pink-400",
};

const catBorder: Record<CategorySlug, string> = {
  bist:      "border-sky-400/20",
  global:    "border-violet-400/20",
  ipo:       "border-emerald-400/20",
  viop:      "border-orange-400/20",
  gundem:    "border-amber-400/20",
  kripto:    "border-orange-300/20",
  teknoloji: "border-pink-400/20",
};

/**
 * Editorial rapor kartı — sade, içeriğe odaklı.
 * Görsel önemli ama metin hiyerarşisi onu yönetir.
 */
export function ReportCard({ report }: { report: Report }) {
  const imageUrl = getReportImageUrl(report);
  const color = catColor[report.category];
  const border = catBorder[report.category];

  return (
    <Link href={`/rapor/${report.slug}`} className="group block">
      {/* Görsel */}
      <div
        className={`aspect-[2/1] rounded-lg overflow-hidden mb-4 border ${border} relative`}
        style={{ background: "var(--surface)" }}
      >
        <img
          src={imageUrl}
          alt={report.title}
          className="w-full h-full object-cover opacity-75 group-hover:opacity-95 transition-all duration-500 group-hover:scale-[1.02]"
        />
        {/* Alt solda kategori etiketi */}
        <div className="absolute bottom-3 left-3">
          <span
            className={`text-xs font-bold tracking-wider uppercase px-2 py-0.5 rounded ${color}`}
            style={{ background: "rgba(10,10,10,0.75)", backdropFilter: "blur(4px)" }}
          >
            {CATEGORIES[report.category].label}
          </span>
        </div>
      </div>

      {/* Meta */}
      <div className="flex items-center gap-2 mb-2">
        <time
          dateTime={report.publishedAt}
          className="text-xs"
          style={{ color: "var(--text-muted)" }}
        >
          {formatDate(report.publishedAt)}
        </time>
        <span style={{ color: "var(--border-2)" }}>·</span>
        <span className="text-xs" style={{ color: "var(--text-muted)" }}>
          {readingMinutes(report.body)} dk
        </span>
      </div>

      {/* Başlık */}
      <h3
        className="text-base font-display font-semibold leading-snug mb-2 group-hover:opacity-70 transition-opacity"
        style={{ letterSpacing: "-0.01em" }}
      >
        {report.title}
      </h3>

      {/* Özet */}
      <p
        className="text-sm leading-relaxed line-clamp-2"
        style={{ color: "var(--text-secondary)" }}
      >
        {report.summary}
      </p>
    </Link>
  );
}
