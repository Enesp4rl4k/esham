"use client";

import { useState, useMemo } from "react";
import { Search, X } from "lucide-react";
import { ReportCard } from "@/components/ReportCard";
import type { Report } from "@/lib/content-utils";

/**
 * Tamamen istemci taraflı arama — statik export için sunucu gerekmez.
 * Başlık, özet ve etiketlerde büyük/küçük harf duyarsız metin araması yapar.
 */
export function SearchClient({ reports }: { reports: Report[] }) {
  const [query, setQuery] = useState("");

  const results = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return [];
    return reports.filter((r) => {
      return (
        r.title.toLowerCase().includes(q) ||
        r.summary.toLowerCase().includes(q) ||
        r.tags.some((t) => t.toLowerCase().includes(q))
      );
    });
  }, [query, reports]);

  const hasQuery = query.trim().length > 0;

  return (
    <div>
      {/* Arama kutusu */}
      <div className="relative mb-10">
        <Search
          className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-zinc-400"
          aria-hidden="true"
        />
        <input
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Rapor başlığı, özet veya etiket ara…"
          aria-label="Rapor ara"
          className="w-full bg-zinc-900 border border-zinc-800 rounded-xl pl-12 pr-12 py-4 text-zinc-100 placeholder:text-zinc-600 focus:outline-none focus:ring-2 focus:ring-cyan-500/50 focus:border-cyan-700 transition-colors"
        />
        {hasQuery && (
          <button
            onClick={() => setQuery("")}
            aria-label="Aramayı temizle"
            className="absolute right-4 top-1/2 -translate-y-1/2 text-zinc-400 hover:text-white transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        )}
      </div>

      {/* Sonuçlar */}
      {hasQuery && (
        <>
          <p className="text-sm text-zinc-400 mb-8">
            {results.length > 0
              ? `${results.length} sonuç bulundu`
              : "Sonuç bulunamadı"}
          </p>

          {results.length > 0 ? (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-x-6 gap-y-12">
              {results.map((report) => (
                <ReportCard key={report.slug} report={report} />
              ))}
            </div>
          ) : (
            <div className="rounded-2xl border border-zinc-800 bg-zinc-900/40 p-12 text-center">
              <p className="text-zinc-400">
                &ldquo;{query}&rdquo; için rapor bulunamadı.
              </p>
              <p className="text-zinc-400 text-sm mt-2">
                Farklı bir anahtar kelime deneyin.
              </p>
            </div>
          )}
        </>
      )}

      {/* Boş durum — henüz arama yapılmadı */}
      {!hasQuery && (
        <div className="rounded-2xl border border-zinc-800 bg-zinc-900/20 p-12 text-center">
          <Search className="w-8 h-8 text-zinc-700 mx-auto mb-4" aria-hidden="true" />
          <p className="text-zinc-400">
            Arama yapmak için yukarıya bir şeyler yazın.
          </p>
        </div>
      )}
    </div>
  );
}
