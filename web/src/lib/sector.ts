/**
 * Sektör içi konum hesapları — saf fonksiyonlar (universe.json satırları üzerinde).
 * Şüpheli (uç değer / Yahoo çapraz kontrolü) hisseler istatistikten (medyan, sıra, aralık) hariç tutulur.
 */
import type { UniverseStock } from "./stocks";

export type MetricKey = "pe" | "pb" | "ev_ebitda" | "roe" | "net_margin" | "dividend_yield" | "net_debt_ebitda";

export interface MetricDef {
  key: MetricKey;
  label: string;
  unit: "x" | "%";
  better: "low" | "high";
  hint: string;
  nonFinancialOnly?: boolean;
  /** anlamlı değer mi? (örn. F/K yalnızca pozitifte) */
  valid: (v: number) => boolean;
}

export const METRICS: MetricDef[] = [
  { key: "pe", label: "F/K", unit: "x", better: "low", hint: "Düşük = ucuz", valid: (v) => v > 0 },
  { key: "pb", label: "PD/DD", unit: "x", better: "low", hint: "Düşük = ucuz", valid: (v) => v > 0 },
  { key: "ev_ebitda", label: "FD/FAVÖK", unit: "x", better: "low", hint: "Düşük = ucuz", nonFinancialOnly: true, valid: (v) => v > 0 },
  { key: "roe", label: "ROE", unit: "%", better: "high", hint: "Yüksek = verimli", valid: (v) => Math.abs(v) < 200 },
  { key: "net_margin", label: "Net Marj", unit: "%", better: "high", hint: "Yüksek = kârlı", valid: () => true },
  { key: "dividend_yield", label: "Temettü Verimi", unit: "%", better: "high", hint: "Yüksek = fazla ödeme", valid: () => true },
  { key: "net_debt_ebitda", label: "Net Borç/FAVÖK", unit: "x", better: "low", hint: "Düşük = az borçlu", nonFinancialOnly: true, valid: (v) => v > -50 && v < 50 },
];

export interface MetricPosition {
  def: MetricDef;
  value: number | null;
  median: number | null;
  rank: number | null; // 1 = en iyi
  of: number; // karşılaştırılan hisse sayısı
  min: number | null; // aralık: %10 – %90 (uçları kırp)
  max: number | null;
  /** 0-1: aralıktaki konum (kırpılmış) */
  pos: number | null;
  medianPos: number | null;
}

function percentile(sorted: number[], p: number): number {
  if (sorted.length === 1) return sorted[0];
  const idx = (sorted.length - 1) * p;
  const lo = Math.floor(idx), hi = Math.ceil(idx);
  return sorted[lo] + (sorted[hi] - sorted[lo]) * (idx - lo);
}

export function median(values: number[]): number | null {
  if (values.length === 0) return null;
  const s = [...values].sort((a, b) => a - b);
  const m = s.length >> 1;
  return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2;
}

/** Bir hissenin sektöründeki konumu. Sektörde ≥ 3 geçerli değer yoksa medyan/sıra null. */
export function sectorPositions(stock: UniverseStock, all: UniverseStock[]): MetricPosition[] {
  const peers = all.filter((s) => s.sector === stock.sector && !s.suspect);
  return METRICS.filter((d) => !(d.nonFinancialOnly && stock.financial)).map((def) => {
    const raw = stock[def.key] as number | null;
    const value = raw !== null && def.valid(raw) ? raw : null;
    const vals = peers
      .map((p) => p[def.key] as number | null)
      .filter((v): v is number => v !== null && def.valid(v));
    const enough = vals.length >= 3;
    const sorted = [...vals].sort((a, b) => a - b);
    const med = enough ? median(vals) : null;
    const lo = enough ? percentile(sorted, 0.1) : null;
    const hi = enough ? percentile(sorted, 0.9) : null;
    const norm = (v: number | null) =>
      v === null || lo === null || hi === null || hi === lo ? null : Math.max(0, Math.min(1, (v - lo) / (hi - lo)));
    let rank: number | null = null;
    if (value !== null && enough) {
      const better = vals.filter((v) => (def.better === "low" ? v < value : v > value)).length;
      rank = 1 + better;
    }
    return {
      def,
      value,
      median: med,
      rank,
      of: vals.length,
      min: lo,
      max: hi,
      pos: norm(value),
      medianPos: norm(med),
    };
  });
}
