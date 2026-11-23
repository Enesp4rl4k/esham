/**
 * KAP kâr payı / geri alım ve makro gösterge dosyaları (bot: `kap-events`, `macro` komutları).
 * Sunucu tarafı, build zamanında okunur. Dosya yoksa ya da kaynak/tarih alanları eksikse null döner:
 * çağıran sayfa bölümü ÇİZMEZ (kaynaksız/tarihsiz sayı yayınlanmaz).
 */
import fs from "fs";
import path from "path";

export interface ScanInfo {
  windowFrom: string;
  windowTo: string;
  universeSize: number;
  tickersWithDisclosure: number;
  disclosuresListed: number;
  parsed: number;
  pending: number;
  complete: boolean;
  lastCompleteScanAt: string | null;
  skipped: Record<string, number>;
  /** Henüz taranmamış (KAP istek bütçesi) bildirimler; eski dosyalarda yoktur. */
  pendingItems?: ScanRef[];
  /** Taranıp biçimi tanınmadığı için atlanan bildirimler. */
  skippedItems?: (ScanRef & { reason: string })[];
}

export interface ScanRef {
  ticker: string;
  disclosureIndex: string;
  sourceUrl: string;
}

export interface Installment {
  label: string;
  payGroup: string;
  grossPerShare: number;
  netPerShare: number;
  withholdingPct: number;
  exDate: string;
  exDateFinal: boolean;
  paymentDate: string;
  recordDate: string | null;
  /** Bot: hak kullanım tarihi verinin üretim gününden (Europe/Istanbul) önce mi. */
  exDatePast?: boolean;
  /** Bot: brüt/net tutarın kaynağına dair dürüst not (net asla varsayılan stopajla türetilmez). */
  amountNote?: string;
}

export interface DividendItem {
  ticker: string;
  name: string;
  disclosureIndex: string;
  sourceUrl: string;
  publishedAt: string;
  asOf: string;
  fetchedAt: string;
  status: "teklif" | "kesinlesti" | "dagitim_yok";
  decisionDate: string;
  agmDate: string | null;
  installments: Installment[];
}

export interface BuybackItem {
  ticker: string;
  name: string;
  disclosureIndex: string;
  sourceUrl: string;
  publishedAt: string;
  asOf: string;
  fetchedAt: string;
  nature: string | null;
  boardDecisionDate: string | null;
  programPeriod: string | null;
  maxNominal: number | null;
  fundTotalTry: number | null;
  trades: { date: string; nominal: number; price: number; capitalPct: number | null }[];
  totalNominal: number;
  amountTry: number;
  avgPrice: number;
  firstTradeDate: string;
  lastTradeDate: string;
  programCumulativeNominal: number | null;
}

export interface EventDoc<T> {
  source: string;
  sourceUrl: string;
  fetchedAt: string;
  asOf: string | null;
  items: T[];
  noDividend?: T[];
  scan: ScanInfo;
}

export interface MacroIndicator {
  id: string;
  label: string;
  value: number;
  unit: string;
  asOf: string;
  source: string;
  sourceUrl: string;
  fetchedAt: string;
  note: string;
  stale: boolean;
}

export interface MacroDoc {
  fetchedAt: string;
  indicators: MacroIndicator[];
  evdsEnabled: boolean;
  attribution: string;
}

function readJson(name: string): unknown {
  try {
    return JSON.parse(fs.readFileSync(path.join(process.cwd(), "public", "data", name), "utf-8"));
  } catch {
    return null;
  }
}

const hasStamp = (o: Record<string, unknown>) =>
  typeof o.sourceUrl === "string" && typeof o.asOf === "string" && typeof o.fetchedAt === "string";

function loadEvents<T>(name: string): EventDoc<T> | null {
  const d = readJson(name) as EventDoc<T> | null;
  if (!d || typeof d !== "object" || !d.scan || typeof d.fetchedAt !== "string" || typeof d.sourceUrl !== "string") return null;
  if (!Array.isArray(d.items)) return null;
  // Her satır kaynak bağlantısı + veri tarihi + çekiliş zamanı taşımalı; taşımayan satır çizilmez.
  const ok = (i: T) => hasStamp(i as unknown as Record<string, unknown>);
  return { ...d, items: d.items.filter(ok), noDividend: (d.noDividend ?? []).filter(ok) };
}

export const loadDividends = () => loadEvents<DividendItem>("kap-dividends.json");
export const loadBuybacks = () => loadEvents<BuybackItem>("kap-buybacks.json");

export function loadMacro(): MacroDoc | null {
  const d = readJson("macro-indicators.json") as MacroDoc | null;
  if (!d || typeof d.fetchedAt !== "string" || !Array.isArray(d.indicators)) return null;
  const items = d.indicators.filter((i) => hasStamp(i as unknown as Record<string, unknown>) && typeof i.value === "number");
  return items.length ? { ...d, indicators: items } : null;
}

const TR_MONTHS = ["Oca", "Şub", "Mar", "Nis", "May", "Haz", "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara"];

/** "2026-12-23" → "23 Ara 2026" (saat dilimi kayması olmadan). */
export function fmtDate(iso: string | null | undefined): string {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso ?? "");
  return m ? `${Number(m[3])} ${TR_MONTHS[Number(m[2]) - 1]} ${m[1]}` : "—";
}

export function fmtDateTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? "—" : d.toLocaleString("tr-TR", { timeZone: "Europe/Istanbul", dateStyle: "medium", timeStyle: "short" });
}

export const fmtNum = (n: number | null | undefined, digits = 2) =>
  typeof n === "number" ? n.toLocaleString("tr-TR", { minimumFractionDigits: digits, maximumFractionDigits: digits }) : "—";

export const fmtInt = (n: number | null | undefined) => (typeof n === "number" ? Math.round(n).toLocaleString("tr-TR") : "—");

/** Dosya çekilişi bu kadar günden eskiyse sayfada uyarı çıkar (bot hafta içi çalışır). */
export const STALE_AFTER_DAYS = 5;

export function ageDays(iso: string | null | undefined, now = Date.now()): number | null {
  const t = iso ? new Date(iso).getTime() : NaN;
  return Number.isNaN(t) ? null : Math.floor((now - t) / 86_400_000);
}

/** ISO zaman damgası → Europe/Istanbul takvim günü (YYYY-MM-DD); okunamazsa null. */
export function istanbulDay(iso: string | null | undefined): string | null {
  const t = iso ? new Date(iso) : null;
  if (!t || Number.isNaN(t.getTime())) return null;
  return new Intl.DateTimeFormat("en-CA", { timeZone: "Europe/Istanbul", year: "numeric", month: "2-digit", day: "2-digit" }).format(t);
}

/** Hak kullanım tarihi, verinin üretim gününden önceyse true (botun işareti varsa o; yoksa fetchedAt'ten hesaplanır). Üretim günü bilinmiyorsa false. */
export function isPastExDate(x: Pick<Installment, "exDate" | "exDatePast">, fetchedAt: string): boolean {
  if (typeof x.exDatePast === "boolean") return x.exDatePast;
  const day = istanbulDay(fetchedAt);
  return day !== null && x.exDate < day;
}
