import Link from "next/link";
import Image from "next/image";
import { notFound } from "next/navigation";
import type { Metadata } from "next";
import { ArrowLeft, Sparkles } from "lucide-react";
import {
  getAllReports,
  getReport,
  categoryLabel,
  formatDate,
  readingMinutes,
  accentClasses,
  CATEGORIES,
  getReportImageUrl,
} from "@/lib/content";
import { Markdown } from "@/components/Markdown";
import { Disclaimer } from "@/components/Disclaimer";
import { RelatedReports } from "@/components/RelatedReports";
import { ShareButtons } from "@/components/ShareButtons";
import { ReadingProgress } from "@/components/ReadingProgress";

const SITE_URL = "https://esham.pages.dev";

type Params = { slug: string };

// `output: export` altında Next.js, generateStaticParams() SIFIR rota dönerse
// build'i tamamen başarısız sayar ("missing generateStaticParams()" hatası).
// content/reports boşsa (bot henüz hiç çalışmadıysa, ya da içerik silinirse) site
// hiç deploy edilemez hale gelmesin diye tek bir sentinel param garanti ederiz.
const EMPTY_SENTINEL = "__henuz-rapor-yok__";

// Next 15+ konvansiyonu: params bir Promise.
export async function generateStaticParams(): Promise<Params[]> {
  const reports = getAllReports();
  if (reports.length === 0) return [{ slug: EMPTY_SENTINEL }];
  return reports.map((r) => ({ slug: r.slug }));
}

const SITE_BASE = "https://esham.pages.dev";

export async function generateMetadata({
  params,
}: {
  params: Promise<Params>;
}): Promise<Metadata> {
  const { slug } = await params;
  if (slug === EMPTY_SENTINEL) return { title: "Henüz rapor yok" };
  const report = getReport(slug);
  if (!report) return { title: "Rapor bulunamadı" };

  // Görsel URL'i her zaman mutlak yap — hem OG hem Twitter card çalışsın.
  const rawImage = getReportImageUrl(report);
  const absoluteImage = rawImage.startsWith("http")
    ? rawImage
    : `${SITE_BASE}${rawImage}`;

  const ogImage = {
    url: absoluteImage,
    width: 1200,
    height: 600,
    alt: report.title,
  };

  return {
    title: report.title,
    description: report.summary,
    openGraph: {
      title: report.title,
      description: report.summary,
      type: "article",
      publishedTime: report.publishedAt,
      url: `${SITE_BASE}/rapor/${report.slug}`,
      images: [ogImage],
    },
    twitter: {
      card: "summary_large_image",
      title: report.title,
      description: report.summary,
      images: [absoluteImage],
    },
  };
}

export default async function ReportPage({
  params,
}: {
  params: Promise<Params>;
}) {
  const { slug } = await params;
  if (slug === EMPTY_SENTINEL) {
    return (
      <div className="container mx-auto px-6 py-32 text-center">
        <p className="text-zinc-400">
          Henüz yayınlanmış bir rapor yok. Bot ilk bülteni ürettiğinde burada
          görünecek.
        </p>
      </div>
    );
  }
  const report = getReport(slug);
  if (!report) notFound();

  const accent = accentClasses(CATEGORIES[report.category].accent);
  const imageUrl = getReportImageUrl(report);

  return (
    <>
    <ReadingProgress />
    <article className="container mx-auto px-6 py-16 max-w-3xl">
      <Link
        href={`/kategori/${report.category}`}
        className="inline-flex items-center gap-2 text-sm text-zinc-500 hover:text-white transition-colors mb-8"
      >
        <ArrowLeft className="w-4 h-4" /> {categoryLabel(report.category)}
      </Link>

      {/* Rapor Görseli (Hero) */}
      <div className="w-full aspect-[2/1] rounded-2xl overflow-hidden mb-10 relative bg-zinc-900 border border-zinc-800">
        <Image
          src={imageUrl}
          alt={report.title}
          fill
          priority
          sizes="(max-width: 768px) 100vw, (max-width: 1024px) 85vw, 768px"
          className="object-cover"
        />
        <div className={`absolute inset-0 bg-gradient-to-tr ${accent.gradient} mix-blend-overlay opacity-60`} />
      </div>

      <div className="mb-6">
        <span className={`text-sm font-medium ${accent.text}`}>
          {categoryLabel(report.category)}
        </span>
        <span className="text-zinc-600 mx-2">•</span>
        <span className="text-sm text-zinc-500">
          {formatDate(report.publishedAt)} · {readingMinutes(report.body)} dk okuma
        </span>
      </div>

      <h1 className="text-4xl md:text-5xl font-outfit font-bold tracking-tight mb-6 leading-tight">
        {report.title}
      </h1>

      {report.summary && report.summary.trim().toLowerCase() !== report.title.trim().toLowerCase() && (
        <p className="text-xl text-zinc-400 leading-relaxed mb-8">{report.summary}</p>
      )}

      <div className="flex flex-wrap items-center justify-between gap-4 border-y border-zinc-800 py-4 mb-10">
        <div className="flex flex-wrap items-center gap-3 text-xs text-zinc-500">
          {report.aiGenerated && (
            <span className="inline-flex items-center gap-1.5 text-cyan-400">
              <Sparkles className="w-3.5 h-3.5" /> Yapay zeka ile üretildi
            </span>
          )}
          {report.sources.length > 0 && (
            <span>
              Kaynaklar:{" "}
              <span className="text-zinc-400">{report.sources.join(", ")}</span>
            </span>
          )}
        </div>
        <ShareButtons
          title={report.title}
          url={`${SITE_URL}/rapor/${report.slug}`}
        />
      </div>

      <Markdown>
        {report.body.replace(
          new RegExp(`^#{1,3}\\s+${report.title.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}\\s*\\n+`, 'i'),
          ''
        )}
      </Markdown>

      {report.tags.length > 0 && (
        <div className="flex flex-wrap gap-2 mt-10">
          {report.tags.map((tag) => (
            <span
              key={tag}
              className="px-3 py-1 rounded-full bg-zinc-900 border border-zinc-800 text-xs text-zinc-400"
            >
              #{tag}
            </span>
          ))}
        </div>
      )}

      <div className="mt-12">
        <Disclaimer />
      </div>

      <RelatedReports currentSlug={report.slug} category={report.category} />
    </article>
    </>
  );
}
