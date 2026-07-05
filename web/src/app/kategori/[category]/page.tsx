import { notFound } from "next/navigation";
import type { Metadata } from "next";
import {
  getReportsByCategory,
  CATEGORIES,
  type CategorySlug,
} from "@/lib/content";
import { ReportCard } from "@/components/ReportCard";

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
    <div className="container mx-auto px-6 py-20">
      <header className="mb-12 max-w-2xl">
        <h1 className="text-4xl md:text-5xl font-outfit font-bold tracking-tight mb-4">
          {meta.label}
        </h1>
        <p className="text-lg text-zinc-400">{meta.description}</p>
      </header>

      {reports.length === 0 ? (
        <div className="rounded-2xl border border-zinc-800 bg-zinc-900/40 p-12 text-center">
          <p className="text-zinc-400">Bu kategoride henüz rapor yok.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-x-6 gap-y-12">
          {reports.map((report) => (
            <ReportCard key={report.slug} report={report} />
          ))}
        </div>
      )}
    </div>
  );
}
