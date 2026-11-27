/**
 * Veri grafikleri (/veri) — TEK tanım.
 *
 * Kamuya açık resmî istatistiklerden üretilen zaman serisi grafikleri. Bu dosya saftır (fs, ağ, değer import'u yok):
 * Next sayfaları, `scripts/veri-scenes.mjs` (PNG kartları için sahne çıkışı) ve node testleri aynı kodu kullanır.
 *
 * Akış: `web/public/data/veri/<slug>.json` (veri kümesi, nokta bazında kaynak) → `validateDataset` →
 *   - `tableRows` / `toCsv` / `textAlternative`  (sayfadaki tablo, CSV, metin alternatifi)
 *   - `buildScene`                                (grafiğin geometrisi + tüm metinleri, renk jetonlarıyla)
 *       → sayfada SVG (DataChart.tsx) ve bot tarafında PNG (bot/esham/publishing/veri_cards.py).
 * Sayılar yalnızca `fmtValue` ile biçimlenir; tablo, grafik ve kart aynı fonksiyondan geçtiği için farklılaşamaz.
 * PNG kartı, üretildiği sahnenin sha256 özetini taşır; test, kartın güncel sahneyle aynı olduğunu doğrular.
 *
 * Kurallar: eksik nokta `null` (çizgide boşluk; ara değer ÜRETİLMEZ), her dolu noktanın kaynağı vardır,
 * metinler betimleyicidir (sıralama/yorum/tahmin yok; tarafsız dil testleri).
 */

export const VERI_SCHEMA = 1;

export type PeriodType = "quarter" | "month" | "year";

/** İzin verilen birimler (gösterimdeki yazımıyla). */
export const UNITS = ["adet", "kişi", "TL", "bin TL", "milyon TL", "milyar TL", "%", "USD", "milyon USD"] as const;
export type Unit = (typeof UNITS)[number];
const INTEGER_UNITS: readonly string[] = ["adet", "kişi"];

export interface VeriFile {
  /** Kaynak dosyanın özgün adı (ör. "Banka Çalışan ve Şube Sayıları-Eylül 2026.xlsx") */
  name: string;
  /** Dosyanın indirildiği adres */
  url: string;
  /** Dosyanın yayımlandığı sayfa */
  page: string;
  /** İndirme tarihi (YYYY-MM-DD) */
  retrieved: string;
}

export interface VeriProvenance {
  /** `files` içindeki anahtar */
  file: string;
  /** Tablo sayfasının adı */
  sheet: string;
  /** Hücre adresi (A1 biçimi) */
  cell: string;
  /** Tablodaki özgün satır etiketi */
  label: string;
}

export interface VeriSeries {
  id: string;
  /** Grafikte görünen kısa ad */
  label: string;
  /** Kaynak tablodaki ad */
  sourceLabel: string;
  /** Varsa Borsa İstanbul kodu (iç bağlantı için) */
  ticker?: string;
  /** `periods` ile aynı uzunlukta; eksik = null */
  values: (number | null)[];
  /** `periods` ile aynı uzunlukta; dolu her değerin kaynağı zorunlu */
  provenance: (VeriProvenance | null)[];
}

export interface VeriDataset {
  schema: number;
  slug: string;
  title: string;
  /** Kısa bölüm etiketi (ör. "Bankacılık") */
  kicker: string;
  /** Neyin sayıldığı (ör. "Şube sayısı") */
  measure: string;
  unit: Unit;
  decimals?: number;
  periodType: PeriodType;
  /** Kapsam (ör. "Yurt içi ve yurt dışı şubeler, dönem sonu") */
  coverage: string;
  /** Meta açıklama (≤155 karakter önerilir) */
  description: string;
  /** Örnek (sentetik) veri: noindex, grafikte ve kartta "ÖRNEK VERİ" */
  sample: boolean;
  source: { name: string; short: string; publication: string; url: string; termsUrl: string; terms: string };
  methodology: string[];
  breaks: { period: string; note: string }[];
  updatedAt: string;
  periods: string[];
  files: Record<string, VeriFile>;
  series: VeriSeries[];
}

// ---- dönemler -------------------------------------------------------------------------------

const PERIOD_RE: Record<PeriodType, RegExp> = {
  quarter: /^(\d{4})-Q([1-4])$/,
  month: /^(\d{4})-(0[1-9]|1[0-2])$/,
  year: /^(\d{4})$/,
};
const MONTHS_SHORT = ["Oca", "Şub", "Mar", "Nis", "May", "Haz", "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara"];
const MONTHS_LONG = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"];

export function isPeriod(p: string, t: PeriodType): boolean {
  return PERIOD_RE[t].test(p);
}

export function nextPeriod(p: string, t: PeriodType): string {
  const m = PERIOD_RE[t].exec(p);
  if (!m) throw new Error(`dönem biçimi tanınmadı: ${p}`);
  const y = Number(m[1]);
  if (t === "year") return String(y + 1);
  const n = Number(m[2]);
  if (t === "quarter") return n === 4 ? `${y + 1}-Q1` : `${y}-Q${n + 1}`;
  return n === 12 ? `${y + 1}-01` : `${y}-${String(n + 1).padStart(2, "0")}`;
}

/** Kısa etiket: "3Ç 2026", "Eyl 2026", "2026". */
export function periodLabel(p: string, t: PeriodType): string {
  const m = PERIOD_RE[t].exec(p);
  if (!m) return p;
  if (t === "quarter") return `${m[2]}Ç ${m[1]}`;
  if (t === "month") return `${MONTHS_SHORT[Number(m[2]) - 1]} ${m[1]}`;
  return m[1];
}

/** Uzun etiket: "2026 3. çeyrek (Eylül sonu)", "Eylül 2026", "2026". */
export function periodLong(p: string, t: PeriodType): string {
  const m = PERIOD_RE[t].exec(p);
  if (!m) return p;
  if (t === "quarter") return `${m[1]} ${m[2]}. çeyrek (${MONTHS_LONG[Number(m[2]) * 3 - 1]} sonu)`;
  if (t === "month") return `${MONTHS_LONG[Number(m[2]) - 1]} ${m[1]}`;
  return m[1];
}

function periodYear(p: string): string {
  return p.slice(0, 4);
}

function isYearStart(p: string, t: PeriodType): boolean {
  return t === "year" || p.endsWith("-Q1") || p.endsWith("-01");
}

// ---- sayı biçimi (tek yer) --------------------------------------------------------------------

/** Türkçe sayı: binlik ".", ondalık ","; ICU'ya bağlı değil (sunucu, tarayıcı ve kart aynı metni üretir). */
export function fmtNumber(v: number, decimals = 0): string {
  const neg = v < 0;
  const fixed = Math.abs(v).toFixed(decimals);
  const [int, frac] = fixed.split(".");
  const grouped = int.replace(/\B(?=(\d{3})+(?!\d))/g, ".");
  return `${neg ? "−" : ""}${grouped}${frac ? `,${frac}` : ""}`;
}

export function fmtValue(ds: Pick<VeriDataset, "decimals">, v: number | null): string {
  return v === null ? "—" : fmtNumber(v, ds.decimals ?? 0);
}

// ---- doğrulama ------------------------------------------------------------------------------

const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/;
const CELL_RE = /^[A-Z]{1,3}[1-9]\d{0,6}$/;
const SLUG_RE = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;
const isStr = (v: unknown): v is string => typeof v === "string" && v.trim().length > 0;
const isHttps = (v: unknown): v is string => typeof v === "string" && /^https:\/\/[^\s]+$/.test(v);

/** Şema denetimi. Boş dizi = geçerli. Hatalar Türkçe ve yol bilgisiyle döner. */
export function validateDataset(d: unknown): string[] {
  const e: string[] = [];
  const ds = d as VeriDataset;
  if (!ds || typeof ds !== "object") return ["veri kümesi nesne değil"];
  if (ds.schema !== VERI_SCHEMA) e.push(`schema ${VERI_SCHEMA} olmalı`);
  if (!isStr(ds.slug) || !SLUG_RE.test(ds.slug)) e.push("slug geçersiz");
  for (const k of ["title", "kicker", "measure", "coverage", "description"] as const) if (!isStr(ds[k])) e.push(`${k} boş`);
  if (!(UNITS as readonly string[]).includes(ds.unit)) e.push(`birim izinli listede değil: ${String(ds.unit)}`);
  if (ds.decimals !== undefined && !(Number.isInteger(ds.decimals) && ds.decimals >= 0 && ds.decimals <= 4)) e.push("decimals 0-4 arası tam sayı olmalı");
  if (!["quarter", "month", "year"].includes(ds.periodType)) e.push("periodType geçersiz");
  if (typeof ds.sample !== "boolean") e.push("sample true/false olmalı");
  const s = ds.source;
  if (!s || !isStr(s.name) || !isStr(s.short) || !isStr(s.publication) || !isHttps(s.url) || !isHttps(s.termsUrl) || !isStr(s.terms))
    e.push("source alanları eksik (name, short, publication, url, termsUrl, terms)");
  if (!Array.isArray(ds.methodology) || ds.methodology.length === 0 || !ds.methodology.every(isStr)) e.push("methodology boş");
  if (!isStr(ds.updatedAt) || !ISO_DATE.test(ds.updatedAt)) e.push("updatedAt YYYY-MM-DD olmalı");
  if (!Array.isArray(ds.periods) || ds.periods.length < 2) {
    e.push("en az iki dönem gerekli");
    return e;
  }
  if (e.some((x) => x.startsWith("periodType"))) return e;
  ds.periods.forEach((p, i) => {
    if (!isPeriod(p, ds.periodType)) e.push(`dönem biçimi hatalı: ${p}`);
    else if (i > 0 && isPeriod(ds.periods[i - 1], ds.periodType) && nextPeriod(ds.periods[i - 1], ds.periodType) !== p)
      e.push(`dönemler artan ve kesintisiz olmalı: ${ds.periods[i - 1]} → ${p}`);
  });
  if (!Array.isArray(ds.breaks) || !ds.breaks.every((b) => b && ds.periods.includes(b.period) && isStr(b.note))) e.push("breaks: dönem listede olmalı ve not boş olmamalı");
  const files = ds.files ?? {};
  for (const [k, f] of Object.entries(files)) {
    if (!f || !isStr(f.name) || !isHttps(f.url) || !isHttps(f.page) || !isStr(f.retrieved) || !ISO_DATE.test(f.retrieved)) e.push(`files.${k}: name/url/page/retrieved eksik`);
  }
  if (!Array.isArray(ds.series) || ds.series.length === 0) {
    e.push("en az bir seri gerekli");
    return e;
  }
  const ids = new Set<string>();
  for (const sr of ds.series) {
    const at = `seri ${sr?.id ?? "?"}`;
    if (!isStr(sr?.id) || !SLUG_RE.test(sr.id)) e.push(`${at}: id geçersiz`);
    if (ids.has(sr.id)) e.push(`${at}: id tekrarlanıyor`);
    ids.add(sr.id);
    if (!isStr(sr.label) || !isStr(sr.sourceLabel)) e.push(`${at}: label/sourceLabel boş`);
    if (!Array.isArray(sr.values) || sr.values.length !== ds.periods.length) {
      e.push(`${at}: values uzunluğu dönem sayısına eşit olmalı`);
      continue;
    }
    if (!Array.isArray(sr.provenance) || sr.provenance.length !== ds.periods.length) {
      e.push(`${at}: provenance uzunluğu dönem sayısına eşit olmalı`);
      continue;
    }
    let filled = 0;
    sr.values.forEach((v, i) => {
      const p = ds.periods[i];
      if (v === null) return;
      if (typeof v !== "number" || !Number.isFinite(v)) {
        e.push(`${at} ${p}: değer sayı ya da null olmalı`);
        return;
      }
      filled++;
      if (INTEGER_UNITS.includes(ds.unit) && (!Number.isInteger(v) || v < 0)) e.push(`${at} ${p}: '${ds.unit}' birimi negatif olmayan tam sayı ister`);
      const pr = sr.provenance[i];
      if (!pr || !isStr(pr.file) || !files[pr.file] || !isStr(pr.sheet) || !isStr(pr.cell) || !CELL_RE.test(pr.cell) || !isStr(pr.label))
        e.push(`${at} ${p}: dolu değerin kaynağı eksik (file/sheet/cell/label)`);
    });
    if (filled === 0) e.push(`${at}: hiç dolu değer yok`);
  }
  return e;
}

export function assertValid(ds: unknown, where = "veri kümesi"): VeriDataset {
  const errs = validateDataset(ds);
  if (errs.length) throw new Error(`${where} geçersiz:\n- ${errs.join("\n- ")}`);
  return ds as VeriDataset;
}

// ---- türetilmiş görünümler (tablo, CSV, metin alternatifi) ---------------------------------------

export function lastIndex(sr: Pick<VeriSeries, "values">): number {
  for (let i = sr.values.length - 1; i >= 0; i--) if (sr.values[i] !== null) return i;
  return -1;
}

export interface LatestValue {
  id: string;
  label: string;
  period: string;
  value: number;
  text: string;
}

/** Her serinin son dolu değeri (seri sırasıyla; sıralama yapılmaz). */
export function latestValues(ds: VeriDataset): LatestValue[] {
  return ds.series
    .map((sr) => {
      const i = lastIndex(sr);
      return i < 0 ? null : { id: sr.id, label: sr.label, period: ds.periods[i], value: sr.values[i] as number, text: fmtValue(ds, sr.values[i]) };
    })
    .filter((x): x is LatestValue => x !== null);
}

export function lastPeriod(ds: VeriDataset): string {
  const idx = Math.max(...ds.series.map(lastIndex));
  return ds.periods[idx];
}

export interface TableRow {
  period: string;
  label: string;
  cells: string[];
  values: (number | null)[];
}

/** Sayfadaki tablo: en yeni dönem üstte. */
export function tableRows(ds: VeriDataset): TableRow[] {
  return ds.periods
    .map((p, i) => ({ period: p, label: periodLabel(p, ds.periodType), values: ds.series.map((s) => s.values[i]), cells: ds.series.map((s) => fmtValue(ds, s.values[i])) }))
    .reverse();
}

function csvCell(v: string): string {
  return /[",\n;]/.test(v) ? `"${v.replace(/"/g, '""')}"` : v;
}

/** CSV (RFC 4180, virgül ayraç, ham sayı; eksik = boş). Dönemler artan sırada. */
export function toCsv(ds: VeriDataset): string {
  const head = ["donem", ...ds.series.map((s) => s.label)];
  const rows = ds.periods.map((p, i) => [p, ...ds.series.map((s) => (s.values[i] === null ? "" : String(s.values[i])))]);
  return [head, ...rows].map((r) => r.map(csvCell).join(",")).join("\r\n") + "\r\n";
}

export function unitPhrase(ds: VeriDataset): string {
  return ds.unit;
}

/** Ekran okuyucu ve arama motoru için metin alternatifi (yalnız betimleme). */
export function textAlternative(ds: VeriDataset): string {
  const lp = lastPeriod(ds);
  const vals = latestValues(ds).map((v) => (v.period === lp ? `${v.label} ${v.text}` : `${v.label} ${v.text} (${periodLabel(v.period, ds.periodType)})`));
  return (
    `${ds.title}. ${ds.measure}, ${ds.unit}; ${periodLabel(ds.periods[0], ds.periodType)} – ${periodLabel(lp, ds.periodType)} arası ` +
    `${ds.periods.length} dönem. Son veri (${periodLabel(lp, ds.periodType)}): ${vals.join(", ")}. Kaynak: ${ds.source.name}.`
  );
}

export function sourceLine(ds: VeriDataset): string {
  return `Kaynak: ${ds.source.short}, ${ds.source.publication} · Birim: ${ds.unit} · Son veri: ${periodLabel(lastPeriod(ds), ds.periodType)} · Kapsam: ${ds.coverage}`;
}

export const MIN_INDEXABLE_POINTS = 8;

/** Dizin kararı: örnek veri asla; en az 8 dolu nokta ve 4 dönem gerekir. */
export function isIndexableDataset(ds: VeriDataset): boolean {
  if (ds.sample) return false;
  const filled = ds.series.reduce((n, s) => n + s.values.filter((v) => v !== null).length, 0);
  return filled >= MIN_INDEXABLE_POINTS && ds.periods.length >= 4;
}

/** Site haritası girdileri: /veri dizini + yalnız indekslenebilir veri sayfaları (örnek veri asla). */
export function veriSitemap(siteUrl: string, all: VeriDataset[]): { url: string; lastModified: Date; changeFrequency: "weekly" | "monthly"; priority: number }[] {
  const idx = all.filter(isIndexableDataset);
  if (!idx.length) return [];
  const newest = idx.map((d) => d.updatedAt).sort().at(-1) as string;
  return [
    { url: `${siteUrl}/veri`, lastModified: new Date(newest), changeFrequency: "weekly", priority: 0.7 },
    ...idx.map((d) => ({ url: `${siteUrl}/veri/${d.slug}`, lastModified: new Date(d.updatedAt), changeFrequency: "monthly" as const, priority: 0.7 })),
  ];
}

/**
 * Veri metinleri yalnız betimleyicidir: tarafsız dil kurallarına (neutral-rules.json) EK olarak, değişimi ya da sırayı
 * yorumlayan ifadeler de yasaktır ("geriledi", "öne geçti", "en çok", "rekor"…). Kalıplar `normalize` edilmiş metne
 * (küçük harf, aksansız) uygulanır; test: veri.test.mjs.
 */
export const COMMENTARY_PATTERNS: readonly string[] = [
  String.raw`\bgeril(e|i)`,
  String.raw`\bone gec`,
  String.raw`\bgeride kal`,
  String.raw`\bgerisinde`,
  String.raw`\blider`,
  String.raw`\brekor`,
  String.raw`\bzirve`,
  String.raw`\bdibe\b`,
  String.raw`\ben (cok|az|yuksek|dusuk|buyuk|kucuk|fazla|hizli)\b`,
  String.raw`\b(artti|azaldi|dustu|yukseldi|toparlandi|cakildi|coktu|eridi|kuculdu|buyudu|surdu)\b`,
  String.raw`\b(artiyor|azaliyor|dusuyor|yukseliyor|eriyor|kuculuyor|buyuyor|surduruyor)\b`,
  String.raw`\b(artis|azalis|dusus|yukselis|daralma|genisleme) (gosterdi|kaydetti|yasadi|surdu)`,
  String.raw`\b(iyi|kotu|basarili|basarisiz|zayif|guclu) (performans|gorunum|seyir)`,
  String.raw`\b(olumlu|olumsuz)\b`,
];

/** Üretilen tüm görünür metinler (tarafsız dil testi bunları tarar). */
export function datasetTexts(ds: VeriDataset): string[] {
  return [
    ds.title,
    ds.kicker,
    ds.measure,
    ds.coverage,
    ds.description,
    ds.source.terms,
    ...ds.methodology,
    ...ds.breaks.map((b) => b.note),
    ...ds.series.map((s) => s.label),
    textAlternative(ds),
    sourceLine(ds),
  ];
}

// ---- grafik sahnesi --------------------------------------------------------------------------

export type Theme = "dark" | "light";
export type ColorToken = "bg" | "panel" | "fg" | "muted" | "faint" | "grid" | "axis" | "accent" | "warn" | "watermark" | "s0" | "s1" | "s2" | "s3" | "s4" | "s5";

/**
 * Paletler. Seri renkleri Okabe–Ito ailesinden türetildi (renk körlüğünde ayırt edilebilir) ve her seri ayrıca
 * farklı bir uç işaret şekli ve doğrudan etiketle tanınır; renklere "iyi/kötü" anlamı yüklenmez (kırmızı/yeşil yok).
 * Koyu zemin sitenin --background (#0a0a0a) rengi; açık zemin sitenin açık temasıyla aynı.
 */
export const PALETTES: Record<Theme, Record<ColorToken, string>> = {
  dark: {
    bg: "#0a0a0a", panel: "#111111", fg: "#f0ede8", muted: "#a8a39b", faint: "#6f6b65", grid: "#232323", axis: "#4a4744",
    accent: "#e8a030", warn: "#fbbf24", watermark: "#2a2620",
    s0: "#e69f00", s1: "#56b4e9", s2: "#d58cbc", s3: "#f0e442", s4: "#2fbf8f", s5: "#c9cdd4",
  },
  light: {
    bg: "#f3f5f8", panel: "#ffffff", fg: "#0e1726", muted: "#4b566b", faint: "#7a8496", grid: "#dfe4ea", axis: "#9aa4b4",
    accent: "#b45309", warn: "#92400e", watermark: "#e4e8ee",
    s0: "#b86e00", s1: "#1f6fae", s2: "#a2477f", s3: "#7d6f00", s4: "#00785a", s5: "#4b566b",
  },
};

export type MarkerShape = "circle" | "square" | "diamond" | "triangle" | "triangleDown" | "hexagon";
export const MARKERS: MarkerShape[] = ["circle", "square", "diamond", "triangle", "triangleDown", "hexagon"];

export type Font = "display" | "body" | "bodyBold";
export interface Span {
  text: string;
  fill: ColorToken;
}
export type SceneItem =
  | { k: "rect"; x: number; y: number; w: number; h: number; fill: ColorToken; rx?: number }
  | { k: "line"; x1: number; y1: number; x2: number; y2: number; stroke: ColorToken; sw: number; dash?: [number, number] }
  | { k: "path"; pts: [number, number][]; stroke: ColorToken; sw: number }
  | { k: "circle"; x: number; y: number; r: number; fill: ColorToken; stroke?: ColorToken; sw?: number }
  | { k: "poly"; pts: [number, number][]; fill: ColorToken; stroke?: ColorToken; sw?: number }
  | { k: "text"; x: number; y: number; size: number; font: Font; anchor: "start" | "middle" | "end"; spans: Span[]; role?: string };

export interface SceneSeriesMeta {
  id: string;
  label: string;
  color: ColorToken;
  shape: MarkerShape;
  values: (number | null)[];
}

export interface Scene {
  w: number;
  h: number;
  theme: Theme;
  palette: Record<ColorToken, string>;
  items: SceneItem[];
  meta: {
    slug: string;
    size: SizeKey;
    variant: VariantKey;
    sample: boolean;
    plot: { x0: number; x1: number; y0: number; y1: number };
    yDomain: [number, number];
    xs: number[];
    periods: string[];
    periodLabels: string[];
    series: SceneSeriesMeta[];
    /** Grafikte yazılı son değerler (parite testi bunları tablo ile karşılaştırır) */
    valueLabels: { seriesId: string; period: string; value: number; text: string }[];
  };
}

export type SizeKey = "1600x900" | "1080x1350";
export type VariantKey = "koyu-etiket" | "acik-etiket" | "koyu-lejant";

interface Layout {
  w: number;
  h: number;
  pad: number;
  brand: number;
  kicker: number;
  title: number;
  sub: number;
  legend: number;
  legendCols: number;
  tick: number;
  endLabel: number;
  footer: number;
  line: number;
  marker: number;
  gutter: number;
}

export const LAYOUTS: Record<SizeKey, Layout> = {
  "1600x900": { w: 1600, h: 900, pad: 64, brand: 40, kicker: 20, title: 52, sub: 25, legend: 22, legendCols: 6, tick: 20, endLabel: 23, footer: 18, line: 4.5, marker: 8, gutter: 250 },
  "1080x1350": { w: 1080, h: 1350, pad: 56, brand: 38, kicker: 19, title: 50, sub: 24, legend: 24, legendCols: 2, tick: 20, endLabel: 23, footer: 18, line: 4.5, marker: 8, gutter: 228 },
};

export const VARIANTS: Record<VariantKey, { theme: Theme; labels: "end" | "legend"; note: string }> = {
  "koyu-etiket": { theme: "dark", labels: "end", note: "Koyu zemin, çizgi sonunda ad + değer etiketi" },
  "acik-etiket": { theme: "light", labels: "end", note: "Açık zemin, çizgi sonunda ad + değer etiketi" },
  "koyu-lejant": { theme: "dark", labels: "legend", note: "Koyu zemin, son değerler üstteki açıklamada; çizgi sonunda yalnız işaret" },
};
export const DEFAULT_VARIANT: VariantKey = "koyu-etiket";
export const CARD_SIZES: SizeKey[] = ["1600x900", "1080x1350"];
export const CARD_NOTICE = "Yatırım tavsiyesi değildir.";
export const SAMPLE_MARK = "ÖRNEK VERİ";

/** Sitede ve depoda kartın yolu (yalnız varsayılan varyant yayımlanır). */
export function cardPath(slug: string, size: SizeKey): string {
  return `/veri-kart/${slug}-${size}.png`;
}

const r2 = (v: number) => Math.round(v * 100) / 100;

/** Karakter sayısına göre sözcük kaydırma (ölçüm gerektirmez; iki çizici de aynı satırları çizer). */
export function wrapByChars(text: string, maxChars: number): string[] {
  const words = text.split(/\s+/).filter(Boolean);
  const lines: string[] = [];
  let cur = "";
  for (const w of words) {
    if (!cur) cur = w;
    else if ((cur + " " + w).length <= maxChars) cur += " " + w;
    else {
      lines.push(cur);
      cur = w;
    }
  }
  if (cur) lines.push(cur);
  return lines;
}

export function niceStep(range: number, target: number): number {
  const raw = range / Math.max(1, target);
  const mag = 10 ** Math.floor(Math.log10(raw));
  const n = raw / mag;
  const f = n <= 1 ? 1 : n <= 2 ? 2 : n <= 2.5 ? 2.5 : n <= 5 ? 5 : 10;
  return f * mag;
}

function markerPts(shape: MarkerShape, x: number, y: number, r: number): [number, number][] {
  const poly = (n: number, rot: number, rr = r) =>
    Array.from({ length: n }, (_, i) => {
      const a = rot + (i * 2 * Math.PI) / n;
      return [r2(x + rr * Math.cos(a)), r2(y + rr * Math.sin(a))] as [number, number];
    });
  switch (shape) {
    case "square":
      return poly(4, Math.PI / 4, r * 1.25);
    case "diamond":
      return poly(4, 0, r * 1.3);
    case "triangle":
      return poly(3, -Math.PI / 2, r * 1.35);
    case "triangleDown":
      return poly(3, Math.PI / 2, r * 1.35);
    case "hexagon":
      return poly(6, 0, r * 1.12);
    default:
      return poly(24, 0);
  }
}

function marker(shape: MarkerShape, x: number, y: number, r: number, fill: ColorToken, stroke: ColorToken, sw: number): SceneItem {
  if (shape === "circle") return { k: "circle", x: r2(x), y: r2(y), r, fill, stroke, sw };
  return { k: "poly", pts: markerPts(shape, x, y, r), fill, stroke, sw };
}

const trUpper = (s: string) => s.toLocaleUpperCase("tr-TR");

/** Uç etiketlerini çakışmayacak şekilde dikeyde yerleştirir (sıra korunur, sınırlar içinde). */
export function spreadLabels(ys: number[], gap: number, top: number, bottom: number): number[] {
  const order = ys.map((y, i) => ({ y, i })).sort((a, b) => a.y - b.y || a.i - b.i);
  const pos = order.map((o) => Math.min(Math.max(o.y, top), bottom));
  for (let k = 1; k < pos.length; k++) pos[k] = Math.max(pos[k], pos[k - 1] + gap);
  if (pos.length && pos[pos.length - 1] > bottom) {
    pos[pos.length - 1] = bottom;
    for (let k = pos.length - 2; k >= 0; k--) pos[k] = Math.min(pos[k], pos[k + 1] - gap);
  }
  const out = new Array<number>(ys.length);
  order.forEach((o, k) => (out[o.i] = r2(pos[k])));
  return out;
}

export interface SceneOptions {
  /** Kartın alt satırındaki alan adı (SITE_URL'den; bkz. displayDomain) */
  domain: string;
}

/** "https://ornek.com.tr/" → "ornek.com.tr" */
export function displayDomain(siteUrl: string): string {
  return siteUrl.replace(/^https?:\/\//, "").replace(/\/+$/, "");
}

/**
 * Grafiğin tek tanımı: geometri + metin + renk jetonları. Sayfadaki SVG ve PNG kartı bu çıktıdan çizilir.
 * Seri sırası veri kümesindeki sıradır (alfabetik); değerlere göre sıralama yapılmaz.
 */
export function buildScene(ds: VeriDataset, size: SizeKey, variant: VariantKey, opts: SceneOptions): Scene {
  const L = LAYOUTS[size];
  const V = VARIANTS[variant];
  const { w, h, pad } = L;
  const items: SceneItem[] = [];
  const T = (x: number, y: number, size_: number, font: Font, anchor: "start" | "middle" | "end", spans: Span[], role?: string) =>
    items.push({ k: "text", x: r2(x), y: r2(y), size: size_, font, anchor, spans, ...(role ? { role } : {}) });
  const t = ds.periodType;
  const n = ds.periods.length;
  const lp = lastPeriod(ds);

  items.push({ k: "rect", x: 0, y: 0, w, h, fill: "bg" });

  // üst satır: marka + bölüm etiketi
  const brandY = pad + L.brand * 0.78;
  T(pad, brandY, L.brand, "display", "start", [{ text: "Es", fill: "accent" }, { text: "ham", fill: "fg" }], "brand");
  if (ds.sample) T(w - pad, brandY - 6, L.kicker + 4, "bodyBold", "end", [{ text: `${SAMPLE_MARK} · gerçek değerler değildir`, fill: "warn" }], "sample");
  else T(w - pad, brandY - 6, L.kicker, "bodyBold", "end", [{ text: `VERİ · ${trUpper(ds.kicker)}`, fill: "accent" }], "kicker");

  // başlık (karakter sayısıyla kaydırılır) + alt başlık
  const titleChars = Math.floor((w - 2 * pad) / (L.title * 0.5));
  const titleLines = wrapByChars(ds.title, titleChars);
  let y = brandY + L.brand * 0.55 + L.title * 1.05;
  titleLines.forEach((ln, i) => T(pad, y + i * L.title * 1.12, L.title, "display", "start", [{ text: ln, fill: "fg" }], "title"));
  y += (titleLines.length - 1) * L.title * 1.12;
  y += L.sub * 1.65;
  const sub = `${t === "quarter" ? "Çeyreklik" : t === "month" ? "Aylık" : "Yıllık"}, dönem sonu · ${ds.unit} · ${periodLabel(ds.periods[0], t)} – ${periodLabel(lp, t)}`;
  T(pad, y, L.sub, "body", "start", [{ text: sub, fill: "muted" }], "subtitle");

  // açıklama (lejant): sabit yuvalar, ölçüm yok
  const latest = latestValues(ds);
  const latestById = new Map(latest.map((v) => [v.id, v]));
  const series: SceneSeriesMeta[] = ds.series.map((s, i) => ({ id: s.id, label: s.label, color: `s${i % 6}` as ColorToken, shape: MARKERS[i % MARKERS.length], values: s.values }));
  const cols = L.legendCols;
  const rows = Math.ceil(series.length / cols);
  const rowH = L.legend * 1.75;
  const legendTop = y + L.legend * 1.2;
  const slotW = (w - 2 * pad) / cols;
  series.forEach((s, i) => {
    const cx = pad + (i % cols) * slotW;
    const cy = legendTop + Math.floor(i / cols) * rowH + rowH / 2;
    items.push(marker(s.shape, cx + L.marker, cy, L.marker, s.color, "bg", 0));
    const spans: Span[] = [{ text: s.label, fill: "fg" }];
    const lv = latestById.get(s.id);
    if (V.labels === "legend" && lv) spans.push({ text: `  ${lv.text}`, fill: s.color });
    T(cx + L.marker * 2 + 12, cy + L.legend * 0.36, L.legend, V.labels === "legend" ? "bodyBold" : "body", "start", spans, "legend");
  });

  // alt bilgi (aşağıdan yukarı)
  const footChars = Math.floor((w - 2 * pad) / (L.footer * 0.53));
  const srcLines = wrapByChars(sourceLine(ds), footChars);
  const bottomY = h - pad * 0.72;
  T(pad, bottomY, L.footer + 1, "bodyBold", "start", [{ text: opts.domain, fill: "fg" }], "domain");
  T(w - pad, bottomY, L.footer, "body", "end", [{ text: CARD_NOTICE, fill: "muted" }], "notice");
  const srcTop = bottomY - L.footer * 1.75 - (srcLines.length - 1) * L.footer * 1.4;
  srcLines.forEach((ln, i) => T(pad, srcTop + i * L.footer * 1.4, L.footer, "body", "start", [{ text: ln, fill: "muted" }], "source"));
  const ruleY = srcTop - L.footer * 1.6;
  items.push({ k: "line", x1: pad, y1: r2(ruleY), x2: w - pad, y2: r2(ruleY), stroke: "grid", sw: 1.5 });

  // çizim alanı
  const allVals = ds.series.flatMap((s) => s.values.filter((v): v is number => v !== null));
  const vMax = Math.max(...allVals);
  const vMin = Math.min(0, ...allVals);
  const step = niceStep(vMax - vMin, 5);
  const yMax = Math.ceil(vMax / step) * step;
  const yMin = Math.floor(vMin / step) * step;
  const ticks: number[] = [];
  for (let v = yMin; v <= yMax + step / 2; v += step) ticks.push(r2(v));
  const tickChars = Math.max(...ticks.map((v) => fmtNumber(v, ds.decimals ?? 0).length));
  const x0 = pad + tickChars * L.tick * 0.62 + 18;
  const x1 = w - pad - (V.labels === "end" ? L.gutter : 28);
  const plotTop = legendTop + rows * rowH + L.tick * 1.6;
  const xLabelY = ruleY - L.tick * 1.3;
  const plotBottom = xLabelY - L.tick - 14;
  const X = (i: number) => (n === 1 ? (x0 + x1) / 2 : x0 + (i * (x1 - x0)) / (n - 1));
  const Y = (v: number) => plotBottom - ((v - yMin) / (yMax - yMin)) * (plotBottom - plotTop);

  for (const v of ticks) {
    const yy = r2(Y(v));
    items.push({ k: "line", x1: r2(x0), y1: yy, x2: r2(x1), y2: yy, stroke: v === 0 ? "axis" : "grid", sw: v === 0 ? 2 : 1.25 });
    T(x0 - 14, yy + L.tick * 0.35, L.tick, "body", "end", [{ text: fmtNumber(v, ds.decimals ?? 0), fill: "faint" }], "ytick");
  }
  // x ekseni: her dönem için küçük çentik, yıl başlarında yıl etiketi (sığmazsa seyreltilir)
  const yearIdx = ds.periods.map((p, i) => (isYearStart(p, t) ? i : -1)).filter((i) => i >= 0);
  const pxPerYear = yearIdx.length > 1 ? X(yearIdx[1]) - X(yearIdx[0]) : x1 - x0;
  const every = Math.max(1, Math.ceil((L.tick * 3.4) / pxPerYear));
  ds.periods.forEach((p, i) => {
    const xx = r2(X(i));
    const major = isYearStart(p, t);
    items.push({ k: "line", x1: xx, y1: r2(plotBottom), x2: xx, y2: r2(plotBottom + (major ? 10 : 5)), stroke: "axis", sw: major ? 2 : 1.25 });
  });
  yearIdx.forEach((i, k) => {
    if (k % every !== 0) return;
    T(X(i), xLabelY, L.tick, "body", "middle", [{ text: periodYear(ds.periods[i]), fill: "faint" }], "xtick");
  });

  if (ds.sample) T((x0 + x1) / 2, (plotTop + plotBottom) / 2 + 40, size === "1600x900" ? 120 : 104, "display", "middle", [{ text: SAMPLE_MARK, fill: "watermark" }], "watermark");

  // seriler: null noktalarda çizgi kesilir; tek başına kalan nokta işaretle gösterilir
  series.forEach((s) => {
    let seg: [number, number][] = [];
    const flush = () => {
      if (seg.length > 1) items.push({ k: "path", pts: seg, stroke: s.color, sw: L.line });
      else if (seg.length === 1) items.push({ k: "circle", x: seg[0][0], y: seg[0][1], r: L.line, fill: s.color });
      seg = [];
    };
    s.values.forEach((v, i) => {
      if (v === null) flush();
      else seg.push([r2(X(i)), r2(Y(v))]);
    });
    flush();
  });

  // uç işaretleri + (varyanta göre) uç etiketleri
  const valueLabels: Scene["meta"]["valueLabels"] = [];
  const ends = series.map((s) => {
    const i = lastIndex(s);
    return { s, i, x: X(i), y: Y(s.values[i] as number), v: s.values[i] as number };
  });
  ends.forEach((e) => items.push(marker(e.s.shape, e.x, e.y, L.marker, e.s.color, "bg", 2.5)));
  if (V.labels === "end") {
    const ly = spreadLabels(ends.map((e) => e.y), L.endLabel * 1.22, plotTop + L.endLabel * 0.5, plotBottom);
    ends.forEach((e, k) => {
      const lx = x1 + 22;
      if (Math.abs(ly[k] - e.y) > 1.5 || e.i !== n - 1) items.push({ k: "line", x1: r2(e.x + L.marker + 3), y1: r2(e.y), x2: r2(lx - 6), y2: ly[k], stroke: e.s.color, sw: 1.5 });
      const text = fmtValue(ds, e.v);
      const extra = e.i !== n - 1 ? ` (${periodLabel(ds.periods[e.i], t)})` : "";
      T(lx, ly[k] + L.endLabel * 0.36, L.endLabel, "bodyBold", "start", [{ text: `${e.s.label} `, fill: e.s.color }, { text: text + extra, fill: "fg" }], "endlabel");
      valueLabels.push({ seriesId: e.s.id, period: ds.periods[e.i], value: e.v, text });
    });
  } else {
    ends.forEach((e) => valueLabels.push({ seriesId: e.s.id, period: ds.periods[e.i], value: e.v, text: fmtValue(ds, e.v) }));
  }

  return {
    w,
    h,
    theme: V.theme,
    palette: PALETTES[V.theme],
    items,
    meta: {
      slug: ds.slug,
      size,
      variant,
      sample: ds.sample,
      plot: { x0: r2(x0), x1: r2(x1), y0: r2(plotTop), y1: r2(plotBottom) },
      yDomain: [yMin, yMax],
      xs: ds.periods.map((_, i) => r2(X(i))),
      periods: ds.periods,
      periodLabels: ds.periods.map((p) => periodLabel(p, t)),
      series,
      valueLabels,
    },
  };
}

/** Sahnedeki tüm metinler (tarafsız dil ve parite testleri için). */
export function sceneTexts(scene: Scene): string[] {
  return scene.items.flatMap((it) => (it.k === "text" ? [it.spans.map((s) => s.text).join("")] : []));
}

/** Kart PNG'sine gömülen özet bu metnin sha256'sıdır (bot aynı baytları özetler). */
export function sceneJson(scene: Scene): string {
  return JSON.stringify(scene);
}
