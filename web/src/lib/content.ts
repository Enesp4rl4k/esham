import fs from "node:fs";
import path from "node:path";

/**
 * Esham içerik katmanı — server-only (node:fs kullanır).
 *
 * Saf yardımcı fonksiyonlar ve tipler content-utils.ts'te tutulur;
 * client component'lar oradan import eder. Bu dosya yalnızca sunucu
 * tarafında çalışan veri okuma fonksiyonlarını içerir.
 */

// Tüm saf fonksiyonlar ve tipler content-utils.ts'ten re-export edilir.
export type {
  CategorySlug,
  Report,
  CategoryMeta,
  Accent,
  IpoMeta,
} from "./content-utils";

export {
  CATEGORIES,
  categoryLabel,
  accentClasses,
  readingMinutes,
  formatDate,
  getReportImageUrl,
} from "./content-utils";

import type { CategorySlug, IpoMeta, Report } from "./content-utils";
import { CATEGORIES } from "./content-utils";

const REPORTS_DIR = path.join(process.cwd(), "content", "reports");

function isCategory(value: unknown): value is CategorySlug {
  return typeof value === "string" && value in CATEGORIES;
}

/**
 * `ipo` yapısını toleranslıca ayrıştırır. Alanlar tek tek doğrulanır — bozuk/
 * eksik bir alan tüm raporu düşürmesin; `ipo` hiç yoksa `undefined` döner.
 */
function parseIpoMeta(raw: unknown): IpoMeta | undefined {
  if (!raw || typeof raw !== "object") return undefined;
  const m = raw as Record<string, unknown>;
  if (typeof m.company !== "string" || typeof m.ticker !== "string") return undefined;

  const str = (v: unknown): string | undefined =>
    typeof v === "string" && v.trim() ? v : undefined;
  const list = (v: unknown): string[] | undefined =>
    Array.isArray(v) && v.length ? v.map(String).filter(Boolean) : undefined;
  const obj = (v: unknown): Record<string, string> | undefined => {
    if (!v || typeof v !== "object" || Array.isArray(v)) return undefined;
    const entries = Object.entries(v as Record<string, unknown>)
      .filter(([, val]) => val !== null && val !== undefined && String(val).trim())
      .map(([k, val]) => [k, String(val)] as const);
    return entries.length ? Object.fromEntries(entries) : undefined;
  };

  const meta: IpoMeta = { company: m.company, ticker: m.ticker };
  const discountPct = typeof m.discountPct === "number" ? m.discountPct : undefined;
  const disclosureDate = str(m.disclosureDate);
  const price = str(m.price);
  const discountRate = str(m.discountRate);
  const offerSize = str(m.offerSize);
  const netMargin = str(m.netMargin);
  const verdict = str(m.verdict);
  const confidence = str(m.confidence);
  const valuation = obj(m.valuation);
  const fundUsage = list(m.fundUsage);
  const risks = list(m.risks);

  if (disclosureDate) meta.disclosureDate = disclosureDate;
  if (price) meta.price = price;
  if (discountRate) meta.discountRate = discountRate;
  if (discountPct !== undefined) meta.discountPct = discountPct;
  if (offerSize) meta.offerSize = offerSize;
  if (netMargin) meta.netMargin = netMargin;
  if (valuation) meta.valuation = valuation;
  if (fundUsage) meta.fundUsage = fundUsage;
  if (risks) meta.risks = risks;
  if (verdict) meta.verdict = verdict;
  if (confidence) meta.confidence = confidence;
  return meta;
}

function parseReport(raw: unknown, file: string): Report | null {
  if (!raw || typeof raw !== "object") return null;
  const r = raw as Record<string, unknown>;
  if (typeof r.slug !== "string" || typeof r.title !== "string") {
    console.warn(`[content] Geçersiz rapor atlandı (slug/title eksik): ${file}`);
    return null;
  }
  if (!isCategory(r.category)) {
    console.warn(`[content] Bilinmeyen kategori "${String(r.category)}": ${file}`);
    return null;
  }
  return {
    slug: r.slug,
    title: r.title,
    category: r.category,
    summary: typeof r.summary === "string" ? r.summary : "",
    body: typeof r.body === "string" ? r.body : "",
    publishedAt:
      typeof r.publishedAt === "string" ? r.publishedAt : new Date(0).toISOString(),
    author: typeof r.author === "string" ? r.author : "Esham AI",
    aiGenerated: r.aiGenerated !== false,
    sources: Array.isArray(r.sources) ? r.sources.map(String) : [],
    tags: Array.isArray(r.tags) ? r.tags.map(String) : [],
    image: typeof r.image === "string" ? r.image : undefined,
    ipo: parseIpoMeta(r.ipo),
  };
}

let cache: Report[] | null = null;

export function getAllReports(): Report[] {
  if (cache && process.env.NODE_ENV === "production") return cache;

  let files: string[] = [];
  try {
    files = fs.readdirSync(REPORTS_DIR).filter((f) => f.endsWith(".json"));
  } catch {
    return [];
  }

  const reports: Report[] = [];
  for (const file of files) {
    try {
      const raw = JSON.parse(fs.readFileSync(path.join(REPORTS_DIR, file), "utf-8"));
      const report = parseReport(raw, file);
      if (report) reports.push(report);
    } catch (err) {
      console.warn(`[content] Rapor okunamadı: ${file}`, err);
    }
  }

  reports.sort(
    (a, b) => new Date(b.publishedAt).getTime() - new Date(a.publishedAt).getTime(),
  );
  cache = reports;
  return reports;
}

export function getReport(slug: string): Report | null {
  return getAllReports().find((r) => r.slug === slug) ?? null;
}

export function getReportsByCategory(category: CategorySlug): Report[] {
  return getAllReports().filter((r) => r.category === category);
}

export function getReportsByTicker(ticker: string): Report[] {
  const t = ticker.toUpperCase().replace(/\.IS$/, "");
  return getAllReports().filter((r) => {
    if (r.tags.some((tag) => tag.toUpperCase() === t || tag.toUpperCase() === `$${t}`)) {
      return true;
    }
    if (r.sources.some((s) => s.toUpperCase() === t || s.toUpperCase() === `$${t}`)) {
      return true;
    }
    if (r.ipo?.ticker.toUpperCase() === t) {
      return true;
    }
    const regex = new RegExp(`\\b\\$?${t}\\b`, "i");
    return regex.test(r.title);
  });
}

export function getAllTickers(): string[] {
  const set = new Set<string>();
  const DEFAULT_BIST30 = [
    "THYAO", "ASELS", "GARAN", "EREGL", "KCHOL", "TUPRS", "BIMAS", "AKBNK",
    "ISCTR", "SISE", "SAHOL", "YKBNK", "PGSUS", "FROTO", "TOASO", "ENKAI",
    "PETKM", "KOZAL", "GUBRF", "TCELL", "TTKOM", "EKGYO", "HEKTS", "SASA"
  ];
  DEFAULT_BIST30.forEach((t) => set.add(t));

  for (const r of getAllReports()) {
    if (r.ipo?.ticker) {
      const clean = r.ipo.ticker.replace(/^\$/, "").toUpperCase();
      if (/^[A-Z]{3,6}$/.test(clean)) set.add(clean);
    }
    for (const tag of r.tags) {
      const clean = tag.replace(/^\$/, "").toUpperCase();
      if (/^[A-Z]{3,6}$/.test(clean)) set.add(clean);
    }
    for (const src of r.sources) {
      const clean = src.replace(/^\$/, "").toUpperCase();
      if (/^[A-Z]{3,6}$/.test(clean)) set.add(clean);
    }
  }
  return Array.from(set);
}
