/**
 * Saf yardımcı fonksiyonlar — node:fs kullanılmaz, client component'larda güvenle import edilebilir.
 * content.ts bu dosyayı re-export eder; server-only veri okuma fonksiyonları content.ts'te kalır.
 */

export type CategorySlug = "bist" | "global" | "ipo" | "viop" | "gundem" | "kripto" | "teknoloji";

/**
 * Halka arz için yapılandırılmış meta — bot `ReportDraft.ipo` alanından yazar
 * (`bot/esham/ai/ipo_analyzer.py::IpoAnalysis.to_meta` ile alan adları senkron).
 * Eski raporlarda bu alan yoktur; tüketiciler her zaman yedeğe (regex/boş) düşmelidir.
 */
export interface IpoMeta {
  company: string;
  ticker: string;
  /** KAP bildirim tarihi, `YYYY-MM-DD`. */
  disclosureDate?: string;
  price?: string;
  discountRate?: string;
  /** Sayısal iskonto (%22,5 → 22.5) — sıralama/renk için. */
  discountPct?: number;
  offerSize?: string;
  netMargin?: string;
  valuation?: Record<string, string>;
  fundUsage?: string[];
  risks?: string[];
  verdict?: string;
  confidence?: string;
}

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
  /** Bot tarafından üretilen marka kartı (aynı görsel tweet'te de kullanılır). */
  image?: string;
  /** Halka arz raporlarında yapılandırılmış meta (eski raporlarda yoktur). */
  ipo?: IpoMeta;
}

export interface CategoryMeta {
  label: string;
  description: string;
  /** Tailwind renk anahtarı — accentClasses ile statik sınıflara çevrilir. */
  accent: Accent;
}

export type Accent = "cyan" | "blue" | "emerald" | "amber" | "violet" | "orange" | "pink";

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
  kripto: {
    label: "Kripto",
    description:
      "Bitcoin, Ethereum ve majör kripto varlıklarda önemli fiyat hareketleri ve piyasa analizi.",
    accent: "orange",
  },
  teknoloji: {
    label: "Teknoloji & AI",
    description:
      "Yapay zeka, yarı iletken ve büyük tech gelişmelerinin piyasalara ve ekonomiye etkileri.",
    accent: "pink",
  },
};

export function categoryLabel(slug: CategorySlug): string {
  return CATEGORIES[slug]?.label ?? slug;
}

/**
 * Accent rengini statik Tailwind sınıflarına çevirir.
 */
export function accentClasses(accent: Accent) {
  const map: Record<
    Accent,
    {
      text: string;
      groupHoverText: string;
      badge: string;
      gradient: string;
      dot: string;
      /** Kartın üst kenarında 2px accent border — border-t-2 border-{color} */
      borderTop: string;
    }
  > = {
    cyan: {
      text: "text-cyan-400",
      groupHoverText: "group-hover:text-cyan-400",
      badge: "text-cyan-400 border-cyan-900/50",
      gradient: "from-cyan-900/60 to-transparent",
      dot: "bg-cyan-500",
      borderTop: "border-t-2 border-cyan-500",
    },
    blue: {
      text: "text-blue-400",
      groupHoverText: "group-hover:text-blue-400",
      badge: "text-blue-400 border-blue-900/50",
      gradient: "from-blue-900/60 to-transparent",
      dot: "bg-blue-500",
      borderTop: "border-t-2 border-blue-500",
    },
    emerald: {
      text: "text-emerald-400",
      groupHoverText: "group-hover:text-emerald-400",
      badge: "text-emerald-400 border-emerald-900/50",
      gradient: "from-emerald-900/60 to-transparent",
      dot: "bg-emerald-500",
      borderTop: "border-t-2 border-emerald-500",
    },
    amber: {
      text: "text-amber-400",
      groupHoverText: "group-hover:text-amber-400",
      badge: "text-amber-400 border-amber-900/50",
      gradient: "from-amber-900/60 to-transparent",
      dot: "bg-amber-500",
      borderTop: "border-t-2 border-amber-500",
    },
    violet: {
      text: "text-violet-400",
      groupHoverText: "group-hover:text-violet-400",
      badge: "text-violet-400 border-violet-900/50",
      gradient: "from-violet-900/60 to-transparent",
      dot: "bg-violet-500",
      borderTop: "border-t-2 border-violet-500",
    },
    orange: {
      text: "text-orange-400",
      groupHoverText: "group-hover:text-orange-400",
      badge: "text-orange-400 border-orange-900/50",
      gradient: "from-orange-900/60 to-transparent",
      dot: "bg-orange-500",
      borderTop: "border-t-2 border-orange-500",
    },
    pink: {
      text: "text-pink-400",
      groupHoverText: "group-hover:text-pink-400",
      badge: "text-pink-400 border-pink-900/50",
      gradient: "from-pink-900/60 to-transparent",
      dot: "bg-pink-500",
      borderTop: "border-t-2 border-pink-500",
    },
  };
  return map[accent] ?? map.cyan;
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
 * Raporun görsel URL'sini döner.
 */
export function getReportImageUrl(report: Report): string {
  if (report.image) return report.image;
  return `/cards/default-${report.category}.png`;
}
