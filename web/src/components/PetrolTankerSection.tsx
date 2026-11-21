"use client";

import React from "react";
import { Fuel, Info } from "lucide-react";
import type { PetrolTankerDataset } from "@/app/tarim-emtia/client";

interface StraitCounts {
  tanker: number;
  total: number;
}

export interface StraitEntry {
  strait: string;
  name: string;
  weekStart: string;
  weekEnd: string;
  asOf?: string;
  stale?: boolean;
  counts: StraitCounts;
  previousWeek?: { weekStart: string; weekEnd: string; counts: StraitCounts } | null;
  dataUpdatedAt?: string | null;
  source?: string;
  sourceUrl?: string;
}

interface PetrolTankerSectionProps {
  data?: PetrolTankerDataset & { straits?: StraitEntry[] };
}

const MONTHS = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"];

/** "2026-11-09","2026-11-15" -> "9–15 Kasım 2026" (ay/yıl değişirse tam biçim). */
export function formatWeekRange(start: string, end: string): string {
  const [sy, sm, sd] = start.split("-").map(Number);
  const [ey, em, ed] = end.split("-").map(Number);
  if (!sy || !sm || !sd || !ey || !em || !ed) return `${start} – ${end}`;
  if (sy === ey && sm === em) return `${sd}–${ed} ${MONTHS[em - 1]} ${ey}`;
  if (sy === ey) return `${sd} ${MONTHS[sm - 1]} – ${ed} ${MONTHS[em - 1]} ${ey}`;
  return `${sd} ${MONTHS[sm - 1]} ${sy} – ${ed} ${MONTHS[em - 1]} ${ey}`;
}

/** Düz sayı farkı (renk/ok yok): "+16", "-5", "0". */
export function formatDelta(now: number, before: number): string {
  const d = now - before;
  return d > 0 ? `+${d}` : String(d);
}

export const STRAIT_DISCLAIMER =
  "Tahmini — gemilerin kendi AIS yayınına dayanır; AIS kapatan gemiler sayılmaz. Resmî istatistik değildir.";
export const STRAIT_CITATION = "Sources: UN Global Platform; IMF PortWatch (portwatch.imf.org).";

/**
 * Petrol & tanker bölümü: botun yayınladığı GERÇEK Brent kotasyonunu ve (varsa) IMF PortWatch boğaz
 * geçiş sayılarını gösterir; boğaz sayıları gözlemdir, sinyal/öngörü/tavsiye değildir.
 * Önceki sürümdeki gömülü örnek veriler (WTI, Urals, crack spread, BDTI/BCTI, VLSFO, tanker kiralama
 * ücretleri, boğaz bekleme/demuraj rakamları) kaldırıldı: bu alanlar için gerçek kaynak yok ve veri
 * yokken sabit sayı gösterilmez.
 */
export function PetrolTankerSection({ data }: PetrolTankerSectionProps) {
  const brent = data?.oilBenchmarks?.brent;
  const asOf = data?.date || (data?.updatedAt ? data.updatedAt.slice(0, 10) : null);
  const stale = Boolean((data as { stale?: boolean } | undefined)?.stale);
  const up = (brent?.changePct ?? 0) >= 0;
  const straits = (data?.straits ?? []).filter((e) => e?.counts && typeof e.counts.total === "number");

  return (
    <section className="mb-10 rounded-2xl border border-zinc-800 bg-zinc-950/80 p-6" aria-label="Petrol">
      <div className="flex items-center gap-2.5 mb-4">
        <span className="p-2 rounded-xl bg-amber-500/10 text-amber-400 border border-amber-500/20">
          <Fuel className="w-5 h-5" />
        </span>
        <div>
          <h2 className="text-sm font-bold text-white tracking-tight">Petrol (Brent)</h2>
          <p className="text-xs text-zinc-400">Yayın anındaki Brent vadeli kotasyonu (BZ=F)</p>
        </div>
      </div>

      {brent ? (
        <div className="flex items-baseline gap-3 font-mono">
          <span className="text-2xl font-extrabold text-white">{brent.priceStr}</span>
          <span className={`text-xs font-semibold ${up ? "text-emerald-400" : "text-rose-400"}`}>{brent.changeStr}</span>
          <span className="text-xs text-zinc-400">
            Veri tarihi: {asOf ?? "yok"}
            {stale ? " (güncel değil, son iyi değer)" : ""}
          </span>
        </div>
      ) : (
        <p className="text-sm text-zinc-300 font-mono">Veri yok</p>
      )}

      <div className="mt-6 border-t border-zinc-800 pt-4">
        <h3 className="text-xs font-bold text-white tracking-tight">Boğaz geçişleri (gözlem)</h3>
        {straits.length > 0 ? (
          straits.map((e) => (
            <div key={e.strait} className="mt-3 font-mono text-xs text-zinc-300">
              <p className="text-sm font-semibold text-white">
                {e.name} <span className="text-xs font-normal text-zinc-400">— {formatWeekRange(e.weekStart, e.weekEnd)} haftası</span>
              </p>
              <p className="mt-1">
                Tanker: <span className="text-white">{e.counts.tanker}</span> geçiş · Toplam:{" "}
                <span className="text-white">{e.counts.total}</span> geçiş
              </p>
              {e.previousWeek ? (
                <p className="mt-1 text-zinc-400">
                  Önceki haftaya göre fark ({formatWeekRange(e.previousWeek.weekStart, e.previousWeek.weekEnd)} ile): tanker{" "}
                  {formatDelta(e.counts.tanker, e.previousWeek.counts.tanker)} ({e.previousWeek.counts.tanker} → {e.counts.tanker}),
                  toplam {formatDelta(e.counts.total, e.previousWeek.counts.total)} ({e.previousWeek.counts.total} → {e.counts.total})
                </p>
              ) : null}
              <p className="mt-1 text-zinc-400">
                Veri tarihi: {e.asOf ?? e.weekEnd}
                {e.dataUpdatedAt ? ` · kaynak güncellemesi: ${e.dataUpdatedAt}` : ""}
                {e.stale ? " (güncel değil, son iyi değer)" : ""}
              </p>
            </div>
          ))
        ) : (
          <p className="mt-2 text-sm text-zinc-300 font-mono">Veri yok</p>
        )}
        {straits.length > 0 ? (
          <>
            <p className="mt-3 flex items-start gap-2 text-xs text-zinc-400 leading-relaxed">
              <Info className="w-3.5 h-3.5 mt-0.5 shrink-0" />
              {STRAIT_DISCLAIMER}
            </p>
            <p className="mt-1 pl-5 text-xs text-zinc-400">
              {straits[0].sourceUrl ? (
                <a href={straits[0].sourceUrl} target="_blank" rel="noopener noreferrer" className="underline">
                  {STRAIT_CITATION}
                </a>
              ) : (
                STRAIT_CITATION
              )}
            </p>
          </>
        ) : null}
      </div>

      <p className="mt-4 flex items-start gap-2 text-xs text-zinc-400 leading-relaxed">
        <Info className="w-3.5 h-3.5 mt-0.5 shrink-0" />
        {straits.length > 0
          ? "Tanker navlun endeksleri (BDTI/BCTI), kiralama ücretleri (TCE), WTI/Urals farkları, crack spread ve boğaz bekleme süreleri için doğrulanmış bir veri kaynağı bağlı değil; bu alanlar için sayı gösterilmez. Yukarıdaki sayılar yalnızca geçiş adedidir."
          : "Tanker navlun endeksleri (BDTI/BCTI), kiralama ücretleri (TCE), WTI/Urals farkları, crack spread ve boğaz bekleme süreleri için doğrulanmış bir veri kaynağı bağlı değil; bu alanlar için sayı gösterilmez."}
      </p>
    </section>
  );
}
