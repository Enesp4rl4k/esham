import { SITE_URL } from "@/lib/config";
import { seoTitle, seoDescription } from "@/lib/seo";
import Link from "next/link";
import Image from "next/image";
import { notFound } from "next/navigation";
import type { Metadata } from "next";
import { ArrowLeft, Sparkles } from "lucide-react";
import {
  getAllReports,
  getReport,
  isIndexableReport,
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
    : `${SITE_URL}${rawImage}`;

  const ogImage = {
    url: absoluteImage,
    width: 1200,
    height: 600,
    alt: report.title,
  };

  return {
    title: seoTitle(report.title),
    description: seoDescription(report.summary),
    // İnce içerik kapısı: bağlantıyla erişilir ama indekse girmez.
    ...(isIndexableReport(report) ? {} : { robots: { index: false, follow: true } }),
    alternates: {
      canonical: `${SITE_URL}/rapor/${report.slug}`,
    },
    openGraph: {
      title: seoTitle(report.title),
      description: seoDescription(report.summary),
      type: "article",
      publishedTime: report.publishedAt,
      url: `${SITE_URL}/rapor/${report.slug}`,
      siteName: "Esham",
      locale: "tr_TR",
      images: [ogImage],
    },
    twitter: {
      card: "summary_large_image",
      title: seoTitle(report.title),
      description: seoDescription(report.summary),
      images: [absoluteImage],
      creator: "@eshamcomtr",
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

  const articleJsonLd = {
    "@context": "https://schema.org",
    "@type": "NewsArticle",
    headline: report.title,
    description: report.summary,
    image: [imageUrl.startsWith("http") ? imageUrl : `${SITE_URL}${imageUrl}`],
    datePublished: report.publishedAt,
    dateModified: report.publishedAt,
    author: {
      "@type": "Organization",
      name: "Esham Finansal İstihbarat",
      url: SITE_URL,
    },
    publisher: {
      "@type": "Organization",
      name: "Esham",
      logo: {
        "@type": "ImageObject",
        url: `${SITE_URL}/cards/default-bist.png`,
      },
    },
    mainEntityOfPage: {
      "@type": "WebPage",
      "@id": `${SITE_URL}/rapor/${report.slug}`,
    },
  };

  const breadcrumbJsonLd = {
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    itemListElement: [
      {
        "@type": "ListItem",
        position: 1,
        name: "Ana Sayfa",
        item: SITE_URL,
      },
      {
        "@type": "ListItem",
        position: 2,
        name: categoryLabel(report.category),
        item: `${SITE_URL}/kategori/${report.category}`,
      },
      {
        "@type": "ListItem",
        position: 3,
        name: report.title,
        item: `${SITE_URL}/rapor/${report.slug}`,
      },
    ],
  };

  return (
    <>
    <script
      type="application/ld+json"
      dangerouslySetInnerHTML={{ __html: JSON.stringify(articleJsonLd) }}
    />
    <script
      type="application/ld+json"
      dangerouslySetInnerHTML={{ __html: JSON.stringify(breadcrumbJsonLd) }}
    />
    <ReadingProgress />
    <article className="container mx-auto px-6 py-16 max-w-3xl">
      <Link
        href={`/kategori/${report.category}`}
        className="inline-flex items-center gap-2 text-sm text-zinc-400 hover:text-white transition-colors mb-8"
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
        <span className="text-zinc-400 mx-2">•</span>
        <span className="text-sm text-zinc-400">
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
        <div className="flex flex-wrap items-center gap-3 text-xs text-zinc-400">
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
