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
} from "./content-utils";

export {
  CATEGORIES,
  categoryLabel,
  accentClasses,
  readingMinutes,
  formatDate,
  getReportImageUrl,
} from "./content-utils";

import type { CategorySlug, Report } from "./content-utils";
import { CATEGORIES } from "./content-utils";

const REPORTS_DIR = path.join(process.cwd(), "content", "reports");

function isCategory(value: unknown): value is CategorySlug {
  return typeof value === "string" && value in CATEGORIES;
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
