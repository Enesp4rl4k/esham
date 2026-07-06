"use client";

import { useState } from "react";
import { ReportCard } from "@/components/ReportCard";
import type { Report } from "@/lib/content-utils";

const PAGE_SIZE = 8;

/**
 * Kategori sayfası için "Daha Fazla Yükle" mantığı.
 * Statik export'ta sunucu taraflı sayfalama olmadığı için
 * tüm raporlar derleme anında gömülür, görünürlük client'ta artar.
 */
export function CategoryReports({ reports }: { reports: Report[] }) {
  const [visible, setVisible] = useState(PAGE_SIZE);

  const shown = reports.slice(0, visible);
  const hasMore = visible < reports.length;

  if (reports.length === 0) {
    return (
      <div className="rounded-2xl border border-zinc-800 bg-zinc-900/40 p-12 text-center">
        <p className="text-zinc-400">Bu kategoride henüz rapor yok.</p>
      </div>
    );
  }

  return (
    <div>
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
            Daha Fazla Göster ({reports.length - visible} rapor kaldı)
          </button>
        </div>
      )}

      <p className="mt-6 text-center text-xs text-zinc-700">
        {shown.length} / {reports.length} rapor gösteriliyor
      </p>
    </div>
  );
}
