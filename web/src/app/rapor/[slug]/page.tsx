import Link from "next/link";
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

type Params = { slug: string };

// Next 15+ konvansiyonu: params bir Promise.
export async function generateStaticParams(): Promise<Params[]> {
  return getAllReports().map((r) => ({ slug: r.slug }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<Params>;
}): Promise<Metadata> {
  const { slug } = await params;
  const report = getReport(slug);
  if (!report) return { title: "Rapor bulunamadı" };
  const imageUrl = getReportImageUrl(report, 1200, 630);
  return {
    title: report.title,
    description: report.summary,
    openGraph: {
      title: report.title,
      description: report.summary,
      type: "article",
      publishedTime: report.publishedAt,
      images: [imageUrl],
    },
  };
}

export default async function ReportPage({
  params,
}: {
  params: Promise<Params>;
}) {
  const { slug } = await params;
  const report = getReport(slug);
  if (!report) notFound();

  const accent = accentClasses(CATEGORIES[report.category].accent);
  const imageUrl = getReportImageUrl(report, 1200, 600);

  return (
    <article className="container mx-auto px-6 py-16 max-w-3xl">
      <Link
        href={`/kategori/${report.category}`}
        className="inline-flex items-center gap-2 text-sm text-zinc-500 hover:text-white transition-colors mb-8"
      >
        <ArrowLeft className="w-4 h-4" /> {categoryLabel(report.category)}
      </Link>

      {/* Rapor Görseli (Hero) */}
      <div className="w-full aspect-[2/1] rounded-2xl overflow-hidden mb-10 relative bg-zinc-900 border border-zinc-800">
        <img 
          src={imageUrl} 
          alt={report.title} 
          className="absolute inset-0 w-full h-full object-cover" 
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

      <p className="text-xl text-zinc-400 leading-relaxed mb-8">{report.summary}</p>

      {report.aiGenerated && (
        <div className="flex flex-wrap items-center gap-3 text-xs text-zinc-500 border-y border-zinc-800 py-4 mb-10">
          <span className="inline-flex items-center gap-1.5 text-cyan-400">
            <Sparkles className="w-3.5 h-3.5" /> Yapay zeka ile üretildi
          </span>
          {report.sources.length > 0 && (
            <span>
              Kaynaklar:{" "}
              <span className="text-zinc-400">{report.sources.join(", ")}</span>
            </span>
          )}
        </div>
      )}

      <Markdown>{report.body}</Markdown>

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
    </article>
  );
}
