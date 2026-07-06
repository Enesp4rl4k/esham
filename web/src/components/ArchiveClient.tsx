"use client";

import { useState } from "react";
import { ReportCard } from "@/components/ReportCard";
import type { Report, CategorySlug } from "@/lib/content-utils";
import { CATEGORIES } from "@/lib/content-utils";

const PAGE_SIZE = 12;

/**
 * Arşiv sayfası için kategori filtresi + "Daha Fazla Yükle".
 * Tüm veriler derleme anında gömülür; filtreleme ve sayfalama client'ta çalışır.
 */
export function ArchiveClient({ reports }: { reports: Report[] }) {
  const [activeCategory, setActiveCategory] = useState<CategorySlug | "all">("all");
  const [visible, setVisible] = useState(PAGE_SIZE);

  const filtered =
    activeCategory === "all"
      ? reports
      : reports.filter((r) => r.category === activeCategory);

  const shown = filtered.slice(0, visible);
  const hasMore = visible < filtered.length;

  const categories: { slug: CategorySlug | "all"; label: string }[] = [
    { slug: "all", label: "Tümü" },
    ...(Object.keys(CATEGORIES) as CategorySlug[]).map((slug) => ({
      slug,
      label: CATEGORIES[slug].label,
    })),
  ];

  function handleFilter(cat: CategorySlug | "all") {
    setActiveCategory(cat);
    setVisible(PAGE_SIZE); // kategori değişince sayacı sıfırla
  }

  return (
    <div>
      {/* Filtre çubuğu */}
      <div className="flex flex-wrap gap-2 mb-12" role="group" aria-label="Kategori filtresi">
        {categories.map(({ slug, label }) => (
          <button
            key={slug}
            onClick={() => handleFilter(slug as CategorySlug | "all")}
            aria-pressed={activeCategory === slug}
            className={`px-4 py-2 rounded-full text-sm font-medium transition-colors border ${
              activeCategory === slug
                ? "bg-cyan-500 border-cyan-500 text-black"
                : "bg-zinc-900 border-zinc-800 text-zinc-400 hover:bg-zinc-800 hover:text-white"
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {/* Sonuç sayısı */}
      <p className="text-sm text-zinc-600 mb-8">
        {filtered.length} rapor
      </p>

      {/* Rapor grid */}
      {filtered.length === 0 ? (
        <div className="rounded-2xl border border-zinc-800 bg-zinc-900/40 p-12 text-center">
          <p className="text-zinc-400">Bu kategoride henüz rapor yok.</p>
        </div>
      ) : (
        <>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-x-6 gap-y-12">
            {shown.map((report) => (
              <ReportCard key={report.slug} report={report} />
            ))}
          </div>

          {hasMore && (
            <div className="mt-14 text-center">
              <button
                onClick={() => setVisible((v) => v + PAGE_SIZE)}
                className="px-8 py-3 rounded-full bg-zinc-900 border border-zinc-800 text-sm font-medium text-zinc-300 hover:bg-zinc-800 hover:text-white transition-colors"
              >
                Daha Fazla Göster ({filtered.length - visible} rapor kaldı)
              </button>
            </div>
          )}

          <p className="mt-6 text-center text-xs text-zinc-700">
            {shown.length} / {filtered.length} rapor gösteriliyor
          </p>
        </>
      )}
    </div>
  );
}
