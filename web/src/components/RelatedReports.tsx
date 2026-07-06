import Link from "next/link";
import Image from "next/image";
import {
  type Report,
  accentClasses,
  categoryLabel,
  formatDate,
  readingMinutes,
  CATEGORIES,
  getReportImageUrl,
} from "@/lib/content-utils";
import { getReportsByCategory } from "@/lib/content";

/**
 * Aynı kategoriden en fazla 3 ilgili raporu gösterir.
 * Mevcut raporun kendisi listeden çıkarılır.
 */
export function RelatedReports({
  currentSlug,
  category,
}: {
  currentSlug: string;
  category: Report["category"];
}) {
  const related = getReportsByCategory(category)
    .filter((r) => r.slug !== currentSlug)
    .slice(0, 3);

  if (related.length === 0) return null;

  return (
    <section className="mt-16 pt-12 border-t border-zinc-800">
      <h2 className="text-xl font-outfit font-bold mb-8 text-zinc-100">
        İlgili Raporlar
      </h2>
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-6">
        {related.map((report) => {
          const accent = accentClasses(CATEGORIES[report.category].accent);
          const imageUrl = getReportImageUrl(report);
          return (
            <Link
              key={report.slug}
              href={`/rapor/${report.slug}`}
              className="group block"
            >
              <div className="aspect-[2/1] rounded-xl bg-zinc-900 mb-3 overflow-hidden border border-zinc-800 relative">
                <Image
                  src={imageUrl}
                  alt={report.title}
                  fill
                  sizes="(max-width: 640px) 100vw, 33vw"
                  className="object-cover opacity-60 mix-blend-overlay transition-all duration-500 group-hover:opacity-90 group-hover:scale-105"
                />
                <div
                  className={`absolute inset-0 bg-gradient-to-tr ${accent.gradient}`}
                />
              </div>
              <p className="text-xs text-zinc-500 mb-1">
                {formatDate(report.publishedAt)} •{" "}
                {readingMinutes(report.body)} dk
              </p>
              <h3
                className={`text-sm font-semibold leading-snug transition-colors line-clamp-2 ${accent.groupHoverText}`}
              >
                {report.title}
              </h3>
              <p className="text-xs text-zinc-500 mt-1">
                {categoryLabel(report.category)}
              </p>
            </Link>
          );
        })}
      </div>
    </section>
  );
}
