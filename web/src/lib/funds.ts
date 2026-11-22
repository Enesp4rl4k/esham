/**
 * TEFAS fon verisi: tipler + saf yardımcılar (kategori grupları, sıralamalar, metin üretimi). İstemci bileşenleri de
 * kullanır, bu yüzden `fs` içermez; dosya okuyucular `funds-data.ts` içindedir.
 * Bot: `python -m esham.main funds` → public/data/universe-funds.json ve public/data/funds/<KOD>.json.
 */

export interface FundRow {
  /** Satırın kendi veri zamanı; bot son turda alamadıysa `stale: true` */
  updated_at?: string;
  stale?: boolean;
  code: string;
  name: string;
  category: string;
  risk: number | null;
  price: number | null;
  daily: number | null;
  aum: number | null;
  investors: number | null;
  fee: number | null;
  as_of: string | null;
  r1m: number | null;
  r3m: number | null;
  r6m: number | null;
  ytd: number | null;
  r1y: number | null;
  r3y: number | null;
  r5y: number | null;
  real_1y: number | null;
  vol: number | null;
  mdd: number | null;
  sharpe: number | null;
  rank: number | null;
  rank_of: number | null;
}

export interface FundUniverse {
  updated_at: string;
  source: string;
  count: number;
  category_median_1y: Record<string, number>;
  funds: FundRow[];
}

export interface FundDetail {
  code: string;
  name: string;
  category: string;
  risk: number | null;
  updated_at: string;
  as_of: string | null;
  price: number | null;
  daily: number | null;
  aum: number | null;
  units: number | null;
  investors: number | null;
  market_share: number | null;
  fee: number | null;
  returns: Record<"1m" | "3m" | "6m" | "ytd" | "1y" | "3y" | "5y", number | null>;
  real_1y: number | null;
  usd_1y: number | null;
  metrics: { volatility: number | null; max_drawdown: number | null; sharpe: number | null };
  category_rank: { rank: number; of: number; by: string } | null;
  category_median_1y: number | null;
  benchmarks: Record<string, number>;
  allocation: { type: string; pct: number }[] | null;
  prices: [string, number][];
  source: string;
}

// Not: sade Node test koşucusu uzantısız göreli import çözemediği için küçük yardımcılar burada tekrarlanır.
const fold = (s: string) =>
  s.replace(/İ/g, "i").replace(/I/g, "i").toLowerCase().replace(/ı/g, "i").normalize("NFD").replace(/[̀-ͯ]/g, "");
export const fundSlug = (s: string) => fold(s).replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "");

export const MIN_CATEGORY_FUNDS = 3;

export interface FundCategory {
  name: string;
  slug: string;
  funds: FundRow[];
}

/** Kategori grupları (fon sayısına göre azalan); az fonlu kategoriler listelenir ama dizine alınmaz. */
export function categoryGroups(funds: FundRow[]): FundCategory[] {
  const by = new Map<string, FundRow[]>();
  for (const f of funds) by.set(f.category, [...(by.get(f.category) ?? []), f]);
  return [...by.entries()]
    .map(([name, fs]) => ({ name, slug: fundSlug(name), funds: fs }))
    .sort((a, b) => b.funds.length - a.funds.length || a.name.localeCompare(b.name, "tr"));
}

export type ReturnKey = "r1m" | "r3m" | "r6m" | "ytd" | "r1y" | "r3y" | "r5y";

/** Verilen getiri anahtarına göre sırala (boşlar sonda); `dir` -1 = yüksekten düşüğe. */
export function sortBy(funds: FundRow[], key: keyof FundRow, dir: 1 | -1 = -1): FundRow[] {
  return [...funds].sort((a, b) => {
    const av = a[key], bv = b[key];
    if (av === null || av === undefined) return 1;
    if (bv === null || bv === undefined) return -1;
    if (typeof av === "string" || typeof bv === "string") return dir * String(av).localeCompare(String(bv), "tr");
    return dir * ((av as number) - (bv as number));
  });
}

export function topBy(funds: FundRow[], key: ReturnKey, n = 10): FundRow[] {
  return sortBy(funds.filter((f) => f[key] !== null), key, -1).slice(0, n);
}

/** Ortalama ± getiri tablosunda gösterilen dönemler. */
export const PERIODS: { key: ReturnKey; label: string }[] = [
  { key: "r1m", label: "1 Ay" },
  { key: "r3m", label: "3 Ay" },
  { key: "r6m", label: "6 Ay" },
  { key: "ytd", label: "Yılbaşından beri" },
  { key: "r1y", label: "1 Yıl" },
  { key: "r3y", label: "3 Yıl" },
  { key: "r5y", label: "5 Yıl" },
];

const nf = new Intl.NumberFormat("tr-TR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
export const fmtPct = (v: number | null | undefined): string =>
  v === null || v === undefined ? "—" : `${v < 0 ? "−" : ""}%${nf.format(Math.abs(v))}`;
export const fmtSigned = (v: number | null | undefined): string =>
  v === null || v === undefined ? "—" : `${v >= 0 ? "▲" : "▼"} %${nf.format(Math.abs(v))}`;
export function fmtMoney(v: number | null | undefined): string {
  if (v === null || v === undefined) return "—";
  if (v >= 1e9) return `${nf.format(v / 1e9)} Mr ₺`;
  if (v >= 1e6) return `${nf.format(v / 1e6)} Mn ₺`;
  return `${nf.format(v)} ₺`;
}
export const fmtPrice = (v: number | null | undefined): string =>
  v === null || v === undefined ? "—" : new Intl.NumberFormat("tr-TR", { minimumFractionDigits: 4, maximumFractionDigits: 6 }).format(v);
export const fmtInt = (v: number | null | undefined): string => (v === null || v === undefined ? "—" : new Intl.NumberFormat("tr-TR").format(v));

/** TEFAS risk değeri 1-7 (düşük → yüksek). */
export function riskLabel(r: number | null): string {
  if (r === null) return "—";
  return `${r}/7 · ${r <= 2 ? "düşük" : r <= 4 ? "orta" : r <= 5 ? "orta-yüksek" : "yüksek"}`;
}

/**
 * Fon sayfası için yalnızca veriden türeyen, nötr dilli açıklama paragrafları (tavsiye/yönlendirme yok).
 * Kalite kapısı: her cümle bir ölçüme dayanır; veri eksikse cümle hiç yazılmaz.
 */
export function describeFund(f: FundDetail): string[] {
  const out: string[] = [];
  const r = f.returns;
  const first: string[] = [`${f.code} (${f.name}), TEFAS'ta işlem gören bir ${f.category.toLocaleLowerCase("tr")} fonudur.`];
  if (f.aum) first.push(`Portföy büyüklüğü ${fmtMoney(f.aum)}${f.investors ? `, yatırımcı sayısı ${fmtInt(f.investors)}` : ""}.`);
  if (f.fee !== null && f.fee !== undefined) first.push(`Uygulanan yıllık yönetim ücreti %${nf.format(f.fee)}.`);
  out.push(first.join(" "));

  if (r["1y"] !== null) {
    const s = [`Son 1 yılda nominal getirisi ${fmtPct(r["1y"])}.`];
    if (f.category_median_1y !== null && f.category_median_1y !== undefined) {
      const d = r["1y"] - f.category_median_1y;
      s.push(`Aynı kategorideki fonların medyan 1 yıllık getirisi ${fmtPct(f.category_median_1y)}; fon bu medyanın ${nf.format(Math.abs(d))} puan ${d >= 0 ? "üzerinde" : "altında"}.`);
    }
    if (f.category_rank) s.push(`Esham'ın hesabına göre kategorideki ${f.category_rank.of} fon arasında 1 yıllık getiriye göre ${f.category_rank.rank}. sırada (1 = en yüksek getiri).`);
    out.push(s.join(" "));
  }

  const infl = f.benchmarks?.cpi, dep = f.benchmarks?.deposit, usd = f.benchmarks?.usd;
  if (r["1y"] !== null && (infl !== undefined || dep !== undefined)) {
    const s: string[] = [];
    if (infl !== undefined && f.real_1y !== null) s.push(`Aynı dönemde TÜFE %${nf.format(infl)} olduğundan reel (enflasyondan arındırılmış) getiri ${fmtPct(f.real_1y)}.`);
    if (usd !== undefined && f.usd_1y !== null) s.push(`ABD doları %${nf.format(usd)} arttığı için dolar bazında getiri ${fmtPct(f.usd_1y)}.`);
    if (dep !== undefined) s.push(`Karşılaştırma için TCMB ağırlıklı ortalama mevduat faizi %${nf.format(dep)}.`);
    if (s.length) out.push(s.join(" "));
  }

  const m = f.metrics;
  if (m.volatility !== null || m.max_drawdown !== null) {
    const s: string[] = [];
    if (m.volatility !== null) s.push(`Son 1 yılda günlük getirilerin yıllıklandırılmış oynaklığı ${fmtPct(m.volatility)}.`);
    if (m.max_drawdown !== null) s.push(`Aynı dönemde zirveden en büyük düşüş ${fmtPct(m.max_drawdown)}.`);
    if (m.sharpe !== null) s.push(`Mevduat faizine göre hesaplanan Sharpe oranı ${nf.format(m.sharpe)}.`);
    if (f.risk !== null) s.push(`TEFAS risk değeri ${riskLabel(f.risk)}.`);
    out.push(s.join(" "));
  }
  return out;
}
