import { notFound } from "next/navigation";
import type { Metadata } from "next";
import {
  getReportsByCategory,
  CATEGORIES,
  type CategorySlug,
  type Accent,
  accentClasses,
} from "@/lib/content";
import { CategoryReports } from "@/components/CategoryReports";

type Params = { category: string };

function isCategory(value: string): value is CategorySlug {
  return value in CATEGORIES;
}

export async function generateStaticParams(): Promise<Params[]> {
  return (Object.keys(CATEGORIES) as CategorySlug[]).map((category) => ({
    category,
  }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<Params>;
}): Promise<Metadata> {
  const { category } = await params;
  if (!isCategory(category)) return { title: "Kategori bulunamadı" };
  const meta = CATEGORIES[category];
  return { title: meta.label, description: meta.description };
}

// ─── CategoryHeader — SVG dekorasyonlu hero başlık ───────────────────────────

function CategoryHeader({
  category,
  label,
  description,
  accent,
}: {
  category: CategorySlug;
  label: string;
  description: string;
  accent: Accent;
}) {
  const ac = accentClasses(accent);

  return (
    <header className={`relative mb-14 overflow-hidden rounded-2xl border border-zinc-800 ${ac.borderTop} bg-zinc-950 px-8 py-12`}>
      {/* SVG Dekorasyon — kategori bazlı */}
      <CategoryDecoration category={category} accent={accent} />

      {/* Glow elipsi */}
      <GlowBlob accent={accent} />

      {/* İçerik */}
      <div className="relative z-10 max-w-2xl">
        <span className={`inline-block mb-4 text-xs font-bold tracking-widest uppercase ${ac.text}`}>
          {label}
        </span>
        <h1 className="text-4xl md:text-5xl font-outfit font-bold tracking-tight text-white mb-4 leading-tight">
          {label}
        </h1>
        <p className="text-lg text-zinc-400 leading-relaxed">{description}</p>
      </div>
    </header>
  );
}

// ─── Glow blob ───────────────────────────────────────────────────────────────

const glowColors: Record<Accent, string> = {
  cyan: "bg-cyan-500/20",
  blue: "bg-blue-500/20",
  emerald: "bg-emerald-500/20",
  amber: "bg-amber-500/20",
  violet: "bg-violet-500/20",
  orange: "bg-orange-500/20",
  pink: "bg-pink-500/20",
};

function GlowBlob({ accent }: { accent: Accent }) {
  return (
    <div
      className={`pointer-events-none absolute -right-24 -top-24 h-64 w-64 rounded-full blur-3xl ${glowColors[accent]}`}
      aria-hidden="true"
    />
  );
}

// ─── SVG Dekorasyonlar — kategori bazlı, dış bağımlılık yok ─────────────────

const svgColors: Record<Accent, string> = {
  cyan: "#22d3ee",
  blue: "#60a5fa",
  emerald: "#34d399",
  amber: "#fbbf24",
  violet: "#a78bfa",
  orange: "#fb923c",
  pink: "#f472b6",
};

function CategoryDecoration({
  category,
  accent,
}: {
  category: CategorySlug;
  accent: Accent;
}) {
  const color = svgColors[accent];

  if (category === "bist") {
    // Diagonal grid çizgileri + sol altta küçük cyan elips
    return (
      <svg
        className="pointer-events-none absolute inset-0 h-full w-full"
        aria-hidden="true"
      >
        <defs>
          <pattern
            id="bist-grid"
            x="0"
            y="0"
            width="40"
            height="40"
            patternUnits="userSpaceOnUse"
            patternTransform="rotate(45)"
          >
            <line x1="0" y1="0" x2="0" y2="40" stroke={color} strokeWidth="0.4" strokeOpacity="0.18" />
          </pattern>
        </defs>
        <rect width="100%" height="100%" fill="url(#bist-grid)" />
        <ellipse cx="8%" cy="85%" rx="120" ry="60" fill={color} fillOpacity="0.07" />
      </svg>
    );
  }

  if (category === "global") {
    // Meridyen yayları (dünya hissi)
    return (
      <svg
        className="pointer-events-none absolute inset-0 h-full w-full"
        aria-hidden="true"
      >
        <ellipse cx="92%" cy="50%" rx="260" ry="160" stroke={color} strokeWidth="0.6" strokeOpacity="0.14" fill="none" />
        <ellipse cx="92%" cy="50%" rx="180" ry="160" stroke={color} strokeWidth="0.5" strokeOpacity="0.10" fill="none" />
        <ellipse cx="92%" cy="50%" rx="100" ry="160" stroke={color} strokeWidth="0.4" strokeOpacity="0.08" fill="none" />
        <line x1="60%" y1="0" x2="60%" y2="100%" stroke={color} strokeWidth="0.4" strokeOpacity="0.10" />
        <line x1="0" y1="50%" x2="100%" y2="50%" stroke={color} strokeWidth="0.4" strokeOpacity="0.10" />
      </svg>
    );
  }

  if (category === "ipo") {
    // Belge köşe katlama + emerald glow
    return (
      <svg
        className="pointer-events-none absolute right-8 top-6 h-40 w-32 opacity-10"
        viewBox="0 0 128 160"
        aria-hidden="true"
      >
        <path
          d="M0 0 L96 0 L128 32 L128 160 L0 160 Z"
          stroke={color}
          strokeWidth="1.5"
          fill="none"
        />
        <path d="M96 0 L96 32 L128 32" stroke={color} strokeWidth="1.5" fill="none" />
        <line x1="16" y1="60" x2="112" y2="60" stroke={color} strokeWidth="1" strokeOpacity="0.6" />
        <line x1="16" y1="80" x2="112" y2="80" stroke={color} strokeWidth="1" strokeOpacity="0.4" />
        <line x1="16" y1="100" x2="80" y2="100" stroke={color} strokeWidth="1" strokeOpacity="0.3" />
      </svg>
    );
  }

  if (category === "viop") {
    // Sinüs dalgası
    return (
      <svg
        className="pointer-events-none absolute inset-x-0 bottom-0 h-24 w-full"
        viewBox="0 0 1200 96"
        preserveAspectRatio="none"
        aria-hidden="true"
      >
        <path
          d="M0 48 C150 0, 300 96, 450 48 C600 0, 750 96, 900 48 C1050 0, 1200 96, 1200 48"
          stroke={color}
          strokeWidth="1.5"
          strokeOpacity="0.18"
          fill="none"
        />
        <path
          d="M0 64 C150 16, 300 112, 450 64 C600 16, 750 112, 900 64 C1050 16, 1200 112, 1200 64"
          stroke={color}
          strokeWidth="1"
          strokeOpacity="0.10"
          fill="none"
        />
      </svg>
    );
  }

  if (category === "gundem") {
    // Radar/sonar halkası
    return (
      <svg
        className="pointer-events-none absolute right-6 top-1/2 -translate-y-1/2 h-48 w-48 opacity-15"
        viewBox="0 0 192 192"
        aria-hidden="true"
      >
        <circle cx="96" cy="96" r="80" stroke={color} strokeWidth="1" fill="none" strokeOpacity="0.8" />
        <circle cx="96" cy="96" r="56" stroke={color} strokeWidth="1" fill="none" strokeOpacity="0.5" />
        <circle cx="96" cy="96" r="32" stroke={color} strokeWidth="1" fill="none" strokeOpacity="0.3" />
        <circle cx="96" cy="96" r="8" fill={color} fillOpacity="0.6" />
        <line x1="96" y1="16" x2="96" y2="176" stroke={color} strokeWidth="0.5" strokeOpacity="0.3" />
        <line x1="16" y1="96" x2="176" y2="96" stroke={color} strokeWidth="0.5" strokeOpacity="0.3" />
        {/* Tarama ışını */}
        <line x1="96" y1="96" x2="168" y2="40" stroke={color} strokeWidth="1.5" strokeOpacity="0.5" />
      </svg>
    );
  }

  return null;
}

// ─── Page ────────────────────────────────────────────────────────────────────

export default async function CategoryPage({
  params,
}: {
  params: Promise<Params>;
}) {
  const { category } = await params;
  if (!isCategory(category)) notFound();

  const meta = CATEGORIES[category];
  const reports = getReportsByCategory(category);

  return (
    <div className="container mx-auto px-6 py-12">
      <CategoryHeader
        category={category}
        label={meta.label}
        description={meta.description}
        accent={meta.accent}
      />

      <CategoryReports reports={reports} />
    </div>
  );
}
