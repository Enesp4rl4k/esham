"use client";

import React from "react";
import { Fuel, Info } from "lucide-react";
import type { PetrolTankerDataset } from "@/app/tarim-emtia/client";

interface PetrolTankerSectionProps {
  data?: PetrolTankerDataset;
}

/**
 * Petrol & tanker bölümü: yalnızca botun yayınladığı GERÇEK Brent kotasyonunu gösterir.
 * Önceki sürümdeki gömülü örnek veriler (WTI, Urals, crack spread, BDTI/BCTI, VLSFO, tanker kiralama
 * ücretleri, boğaz bekleme/demuraj rakamları) kaldırıldı: bu alanlar için gerçek kaynak yok ve veri
 * yokken sabit sayı gösterilmez.
 */
export function PetrolTankerSection({ data }: PetrolTankerSectionProps) {
  const brent = data?.oilBenchmarks?.brent;
  const asOf = data?.date || (data?.updatedAt ? data.updatedAt.slice(0, 10) : null);
  const stale = Boolean((data as { stale?: boolean } | undefined)?.stale);
  const up = (brent?.changePct ?? 0) >= 0;

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

      <p className="mt-4 flex items-start gap-2 text-xs text-zinc-400 leading-relaxed">
        <Info className="w-3.5 h-3.5 mt-0.5 shrink-0" />
        Tanker navlun endeksleri (BDTI/BCTI), kiralama ücretleri (TCE), WTI/Urals farkları, crack spread ve boğaz
        bekleme süreleri için doğrulanmış bir veri kaynağı bağlı değil; bu alanlar için sayı gösterilmez.
      </p>
    </section>
  );
}
