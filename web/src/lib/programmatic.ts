/**
 * Programatik SEO sayfaları (sektör + hazır tarama) için saf yardımcılar.
 * Evren verisinden türetilir; şüpheli (suspect) satırlar istatistik ve listelerden hariçtir.
 */
import type { Universe, UniverseStock } from "./stocks";

export const MIN_INDEXABLE = 3;

/** bot/esham/freshness.py içindeki STOCK_ROW_STALE_HOURS ile AYNI olmalı (test denetler). */
export const STALE_ROW_HOURS = 120;

/**
 * Bayat satır: bot `stale: true` yazdıysa ya da satırın KENDİ veri zamanı eşiği aştıysa.
 * Dosya düzeyi `updated_at` bir tarama zamanıdır, hiçbir satırın veri tarihi değildir.
 */
export function isStale(s: { stale?: boolean; updated_at?: string }, now: number = Date.now()): boolean {
  if (s.stale === true) return true;
  if (!s.updated_at) return true; // tarihsiz satır taze sayılmaz
  const t = Date.parse(s.updated_at);
  return Number.isNaN(t) || now - t > STALE_ROW_HOURS * 3600 * 1000;
}

/** "bayat — son veri: 2026-11-10" */
export function staleLabel(s: { updated_at?: string }): string {
  return `bayat — son veri: ${s.updated_at ? s.updated_at.slice(0, 10) : "bilinmiyor"}`;
}

export function freshOnly<T extends { stale?: boolean; updated_at?: string }>(rows: T[]): T[] {
  return rows.filter((r) => !isStale(r));
}

export interface StaleSummary {
  total: number;
  freshCount: number;
  staleCount: number;
  /** Satırların en yeni KENDİ veri tarihi (YYYY-MM-DD); hiç tarih yoksa null */
  lastDate: string | null;
  /** lastDate'ten bu yana geçen tam gün */
  days: number | null;
}

export function staleSummary(rows: { stale?: boolean; updated_at?: string }[], now: number = Date.now()): StaleSummary {
  const freshCount = rows.filter((r) => !isStale(r, now)).length;
  const stamps = rows.map((r) => (r.updated_at ? Date.parse(r.updated_at) : NaN)).filter((t) => !Number.isNaN(t));
  const last = stamps.length ? Math.max(...stamps) : null;
  return {
    total: rows.length,
    freshCount,
    staleCount: rows.length - freshCount,
    lastDate: last === null ? null : new Date(last).toISOString().slice(0, 10),
    days: last === null ? null : Math.floor((now - last) / 86400000),
  };
}

/** Hiç taze satır yokken boş tablo yerine açık durum cümlesi; en az bir taze satır varsa null. */
export function emptyStateText(sum: StaleSummary): string | null {
  if (sum.total === 0 || sum.freshCount > 0) return null;
  const since = sum.days === null ? "bir süredir" : `${sum.days} gündür`;
  return `Veriler ${since} güncellenemedi; sıralama gösterilmiyor. Son başarılı tarama: ${sum.lastDate ?? "bilinmiyor"}.`;
}


// Not: sade Node test koşucusu uzantısız göreli import çözemediği için küçük yardımcılar burada tekrarlanır.
const fold = (s: string) =>
  s.replace(/İ/g, "i").replace(/I/g, "i").toLowerCase().replace(/ı/g, "i").normalize("NFD").replace(/[̀-ͯ]/g, "");

function median(values: number[]): number | null {
  if (values.length === 0) return null;
  const s = [...values].sort((a, b) => a - b);
  const m = s.length >> 1;
  return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2;
}

export function slugify(s: string): string {
  return fold(s).replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "");
}

export interface SectorGroup {
  name: string;
  slug: string;
  stocks: UniverseStock[];
}

export function sectorGroups(u: Universe): SectorGroup[] {
  const map = new Map<string, UniverseStock[]>();
  for (const s of u.stocks) {
    if (!map.has(s.sector)) map.set(s.sector, []);
    map.get(s.sector)!.push(s);
  }
  return [...map.entries()]
    .map(([name, stocks]) => ({
      name,
      slug: slugify(name),
      stocks: [...stocks].sort((a, b) => (b.market_cap ?? 0) - (a.market_cap ?? 0)),
    }))
    .sort((a, b) => b.stocks.length - a.stocks.length || a.name.localeCompare(b.name, "tr"));
}

export function sectorStats(stocks: UniverseStock[]) {
  const ok = stocks.filter((s) => !s.suspect && !isStale(s));
  const pick = (k: keyof UniverseStock, valid: (v: number) => boolean) =>
    median(ok.map((s) => s[k] as number | null).filter((v): v is number => typeof v === "number" && valid(v)));
  return {
    count: stocks.length,
    staleCount: stocks.filter((s) => isStale(s)).length,
    pe: pick("pe", (v) => v > 0),
    pb: pick("pb", (v) => v > 0),
    roe: pick("roe", (v) => Math.abs(v) < 200),
    dividend_yield: pick("dividend_yield", () => true),
  };
}

export interface Scan {
  slug: string;
  /** StockScreener ön ayar kimliği (?f=) */
  id: string;
  title: string;
  h1: string;
  hint: string;
  metric: "pe" | "roe" | "dividend_yield" | "net_debt_ebitda" | "pb" | "net_margin";
  dir: 1 | -1;
  explain: string;
  test: (s: UniverseStock) => boolean;
}

export const SCANS: Scan[] = [
  {
    slug: "dusuk-fk", id: "ucuz", title: "Düşük F/K'lı Hisseler", h1: "F/K oranı düşük BIST hisseleri", hint: "F/K 8'in altı",
    metric: "pe", dir: 1,
    explain: "F/K (fiyat/kazanç), hissenin fiyatının son 12 aylık net kârının kaç katı olduğunu gösterir. Oran; kârın geçici değişimi, sektörün yapısı ve enflasyon muhasebesi etkisinden etkilenir, bu nedenle sektör medyanıyla birlikte okunur.",
    test: (s) => s.pe !== null && s.pe > 0 && s.pe < 8,
  },
  {
    slug: "yuksek-roe", id: "roe", title: "Yüksek ROE'li Hisseler", h1: "Özkaynak kârlılığı (ROE) yüksek BIST hisseleri", hint: "ROE %25 üzeri",
    metric: "roe", dir: -1,
    explain: "ROE (özkaynak kârlılığı), şirketin özkaynağıyla ne kadar kâr ürettiğini gösterir. Oran, yüksek borçla şişmiş olabilir; bu nedenle net borç/FAVÖK ile birlikte okunur. %200 üzerindeki değerler anlamsız kabul edilip listeden çıkarılır.",
    test: (s) => s.roe !== null && s.roe > 25 && s.roe < 200,
  },
  {
    slug: "yuksek-temettu", id: "temettu", title: "Temettü Verimi Yüksek Hisseler", h1: "Temettü verimi yüksek BIST hisseleri", hint: "Verim %3 üzeri",
    metric: "dividend_yield", dir: -1,
    explain: "Temettü verimi, son 12 ayda ödenen nakit kâr payının hisse fiyatına oranıdır. Geçmiş ödeme gelecekte tekrarlanacağını garanti etmez; dağıtım politikasını ve kârın sürdürülebilirliğini şirketin KAP açıklamalarından doğrulayın.",
    test: (s) => (s.dividend_yield ?? 0) > 3,
  },
  {
    slug: "dusuk-borc", id: "borc", title: "Düşük Borçlu Hisseler", h1: "Net borcu düşük BIST hisseleri", hint: "Net borç/FAVÖK 1'in altı",
    metric: "net_debt_ebitda", dir: 1,
    explain: "Net borç/FAVÖK, şirketin net borcunu kaç yılda faaliyet kârıyla kapatabileceğini yaklaşık gösterir. Negatif değer net nakit pozisyonu demektir. Bankalar ve finansal kuruluşlar için bu oran anlamlı olmadığından listede yer almaz.",
    test: (s) => !s.financial && s.net_debt_ebitda !== null && s.net_debt_ebitda < 1,
  },
  {
    slug: "defter-degerinin-altinda", id: "iskonto", title: "PD/DD 1'in Altındaki Hisseler", h1: "Defter değerinin altında işlem gören BIST hisseleri", hint: "PD/DD 1'in altı",
    metric: "pb", dir: 1,
    explain: "PD/DD, piyasa değerinin defter değerine (özkaynak) oranıdır. 1'in altı, piyasa değerinin muhasebe özkaynağından düşük olduğu anlamına gelir; varlıkların gerçek değeri defter değerinden farklı olabileceği için oran tek başına bir sonuç vermez.",
    test: (s) => s.pb !== null && s.pb > 0 && s.pb < 1,
  },
  {
    slug: "yuksek-net-marj", id: "marj", title: "Net Kâr Marjı Yüksek Hisseler", h1: "Net kâr marjı yüksek BIST hisseleri", hint: "Net marj %20 üzeri",
    metric: "net_margin", dir: -1,
    explain: "Net marj, satış gelirinin ne kadarının net kâra dönüştüğünü gösterir. Bankalarda ve holdinglerde gelir tanımı farklı olduğundan marjlar sektörler arasında doğrudan kıyaslanmamalıdır.",
    test: (s) => s.net_margin !== null && s.net_margin > 20 && s.net_margin < 100,
  },
];

export function runScan(u: Universe, sc: Scan): UniverseStock[] {
  return u.stocks
    .filter((s) => !s.suspect && !isStale(s) && sc.test(s))
    .sort((a, b) => sc.dir * ((a[sc.metric] as number) - (b[sc.metric] as number)));
}

// ─── Karşılaştırma çiftleri ────────────────────────────────────────────────
export interface PairMetric {
  key: "pe" | "pb" | "ev_ebitda" | "roe" | "net_margin" | "dividend_yield" | "net_debt_ebitda";
  label: string;
  unit: "x" | "%";
  better: "low" | "high";
  /** yalnızca finansal olmayan şirketlerde anlamlı */
  nonFinancialOnly?: boolean;
  valid: (v: number) => boolean;
}

export const PAIR_METRICS: PairMetric[] = [
  { key: "pe", label: "F/K", unit: "x", better: "low", valid: (v) => v > 0 },
  { key: "pb", label: "PD/DD", unit: "x", better: "low", valid: (v) => v > 0 },
  { key: "ev_ebitda", label: "FD/FAVÖK", unit: "x", better: "low", nonFinancialOnly: true, valid: (v) => v > 0 },
  { key: "roe", label: "ROE", unit: "%", better: "high", valid: (v) => Math.abs(v) < 200 },
  { key: "net_margin", label: "Net marj", unit: "%", better: "high", valid: () => true },
  { key: "dividend_yield", label: "Temettü verimi", unit: "%", better: "high", valid: () => true },
  { key: "net_debt_ebitda", label: "Net borç/FAVÖK", unit: "x", better: "low", nonFinancialOnly: true, valid: (v) => v > -50 && v < 50 },
];

export function pairSlug(a: string, b: string): string {
  const [x, y] = [a.toUpperCase(), b.toUpperCase()].sort((p, q) => p.localeCompare(q));
  return `${x}-vs-${y}`;
}

/** Aynı sektörde piyasa değeri en büyük `top` hissenin tüm ikilileri (şüpheli olanlar hariç). */
export function comparePairs(u: Universe, top = 4): { a: UniverseStock; b: UniverseStock; slug: string }[] {
  const out: { a: UniverseStock; b: UniverseStock; slug: string }[] = [];
  for (const g of sectorGroups(u)) {
    const pool = g.stocks.filter((s) => !s.suspect && !isStale(s)).slice(0, top);
    if (pool.length < 2 || g.stocks.length < 4) continue;
    for (let i = 0; i < pool.length; i++)
      for (let j = i + 1; j < pool.length; j++) {
        const slug = pairSlug(pool[i].ticker, pool[j].ticker);
        const [first] = slug.split("-vs-");
        const [a, b] = pool[i].ticker === first ? [pool[i], pool[j]] : [pool[j], pool[i]];
        out.push({ a, b, slug });
      }
  }
  return out;
}

export interface PairRow {
  metric: PairMetric;
  a: number | null;
  b: number | null;
  winner: "a" | "b" | null;
}

export function comparePair(a: UniverseStock, b: UniverseStock): PairRow[] {
  const fin = a.financial || b.financial;
  return PAIR_METRICS.filter((m) => !(m.nonFinancialOnly && fin)).map((m) => {
    const get = (s: UniverseStock) => {
      const v = s[m.key] as number | null;
      return v !== null && m.valid(v) ? v : null;
    };
    const va = get(a), vb = get(b);
    let winner: "a" | "b" | null = null;
    if (va !== null && vb !== null && va !== vb) {
      const aWins = m.better === "low" ? va < vb : va > vb;
      winner = aWins ? "a" : "b";
    }
    return { metric: m, a: va, b: vb, winner };
  });
}
