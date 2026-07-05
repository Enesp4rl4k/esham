import fs from "node:fs";
import path from "node:path";

/**
 * Esham içerik katmanı.
 *
 * Bot (Python) tarafı `web/content/reports/*.json` altına yapılandırılmış rapor
 * dosyaları yazar; bu modül onları okuyup tipli nesnelere çevirir. Böylece bot ile
 * web arasındaki tek sözleşme bu JSON şemasıdır. Hacim büyüyünce bu modülün gövdesi
 * Postgres/Supabase okumasına çevrilebilir, sayfalar hiç değişmez.
 */

export type CategorySlug = "bist" | "global" | "ipo" | "viop" | "gundem";

export interface Report {
  slug: string;
  title: string;
  category: CategorySlug;
  summary: string;
  /** Markdown gövde. */
  body: string;
  /** ISO 8601 tarih. */
  publishedAt: string;
  author: string;
  aiGenerated: boolean;
  /** Verinin dayandığı kaynaklar (KAP, Yahoo Finance vb.). Şeffaflık için gösterilir. */
  sources: string[];
  tags: string[];
}

export interface CategoryMeta {
  label: string;
  description: string;
  /** Tailwind renk anahtarı — accentClasses ile statik sınıflara çevrilir. */
  accent: Accent;
}

export type Accent = "cyan" | "blue" | "emerald" | "amber" | "violet";

export const CATEGORIES: Record<CategorySlug, CategoryMeta> = {
  bist: {
    label: "BIST & Sektör",
    description:
      "Borsa İstanbul endeks beklentileri, sektör rotasyonları ve yabancı takas hareketleri.",
    accent: "cyan",
  },
  global: {
    label: "Küresel Makro",
    description:
      "ABD enflasyonundan Çin PMI'ına, küresel ekonominin nabzı ve BIST'e yansımaları.",
    accent: "blue",
  },
  ipo: {
    label: "Halka Arz & KAP",
    description:
      "KAP izahnameleri ve fiyat tespit raporları; iskonto oranları ve riskler mercek altında.",
    accent: "emerald",
  },
  viop: {
    label: "VİOP & Türev",
    description:
      "Vadeli ve opsiyon piyasası, açık pozisyon, teminat parametreleri ve margin-call stresi.",
    accent: "violet",
  },
  gundem: {
    label: "Gündem",
    description: "Piyasaları etkileyen anlık siyasi ve ekonomik gelişmeler.",
    accent: "amber",
  },
};

export function categoryLabel(slug: CategorySlug): string {
  return CATEGORIES[slug]?.label ?? slug;
}

/**
 * Accent rengini statik Tailwind sınıflarına çevirir. Dinamik sınıf isimleri
 * (bg-${x}) Tailwind JIT tarafından derlenmediği için burada tam sınıflar tutulur.
 */
export function accentClasses(accent: Accent) {
  // Not: Tailwind JIT kaynakta statik sınıf metni arar; bu yüzden group-hover gibi
  // varyantlar tam metin olarak burada tutulur (dinamik birleştirme derlenmez).
  const map: Record<
    Accent,
    { text: string; groupHoverText: string; badge: string; gradient: string; dot: string }
  > = {
    cyan: {
      text: "text-cyan-400",
      groupHoverText: "group-hover:text-cyan-400",
      badge: "text-cyan-400 border-cyan-900/50",
      gradient: "from-cyan-900/40 to-transparent",
      dot: "bg-cyan-500",
    },
    blue: {
      text: "text-blue-400",
      groupHoverText: "group-hover:text-blue-400",
      badge: "text-blue-400 border-blue-900/50",
      gradient: "from-blue-900/40 to-transparent",
      dot: "bg-blue-500",
    },
    emerald: {
      text: "text-emerald-400",
      groupHoverText: "group-hover:text-emerald-400",
      badge: "text-emerald-400 border-emerald-900/50",
      gradient: "from-emerald-900/40 to-transparent",
      dot: "bg-emerald-500",
    },
    amber: {
      text: "text-amber-400",
      groupHoverText: "group-hover:text-amber-400",
      badge: "text-amber-400 border-amber-900/50",
      gradient: "from-amber-900/40 to-transparent",
      dot: "bg-amber-500",
    },
    violet: {
      text: "text-violet-400",
      groupHoverText: "group-hover:text-violet-400",
      badge: "text-violet-400 border-violet-900/50",
      gradient: "from-violet-900/40 to-transparent",
      dot: "bg-violet-500",
    },
  };
  return map[accent] ?? map.cyan;
}

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
  };
}

let cache: Report[] | null = null;

export function getAllReports(): Report[] {
  if (cache && process.env.NODE_ENV === "production") return cache;

  let files: string[] = [];
  try {
    files = fs.readdirSync(REPORTS_DIR).filter((f) => f.endsWith(".json"));
  } catch {
    // İçerik klasörü henüz oluşmamışsa boş liste döneriz — build kırılmaz.
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

export function readingMinutes(body: string): number {
  const words = body.trim().split(/\s+/).length;
  return Math.max(1, Math.round(words / 200));
}

export function formatDate(iso: string): string {
  try {
    return new Intl.DateTimeFormat("tr-TR", {
      day: "numeric",
      month: "long",
      year: "numeric",
    }).format(new Date(iso));
  } catch {
    return iso;
  }
}

/**
 * Raporun başlığına ve kategorisine göre dinamik, yapay zeka destekli bir görsel URL'si üretir.
 * Pollinations AI kullanılarak ücretsiz, on-the-fly görsel oluşturulur.
 */
const CATEGORY_PROMPTS: Record<string, string> = {
  insider:
    "Abstract 3D render of elegant financial curves, dark navy blue background, minimalist design, gold accents, smooth light reflections, octane render, premium financial visualization, clean and high-end",
  ipo:
    "Abstract 3D render of ascending geometric bars and rings, dark blue and platinum theme, clean minimal design, volumetric lighting, premium corporate graphic",
  bist:
    "Minimalist abstract 3D render of smooth financial trend lines, dark midnight blue background, ice blue and white glowing curves, clean design, premium market visualization, 8k",
  viop:
    "Abstract 3D render of digital grid and trading waves, dark theme, sharp lines, glowing blue and red accents, minimalist composition, octane render",
  global:
    "Abstract 3D render of interconnected globe network lines, dark blue background, minimalist tech design, glowing nodes, elegant, high-end",
};

const DEFAULT_PROMPT =
  "Abstract 3D render of elegant financial waves, dark midnight blue background, minimal design, glowing curves, octane render, clean, premium market visualization";

export function getReportImageUrl(report: Report, width = 800, height = 400): string {
  let seed = 0;
  for (let i = 0; i < report.slug.length; i++) {
    seed = report.slug.charCodeAt(i) + ((seed << 5) - seed);
  }
  seed = Math.abs(seed) % 10000;

  const baseScene = CATEGORY_PROMPTS[report.category] || DEFAULT_PROMPT;
  const prompt = encodeURIComponent(
    `${baseScene}. Context: ${report.title}`
  );

  return `https://image.pollinations.ai/prompt/${prompt}?width=${width}&height=${height}&nologo=true&seed=${seed}`;
}

