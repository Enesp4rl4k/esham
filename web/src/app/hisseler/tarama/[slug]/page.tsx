import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { loadUniverse } from "@/lib/stocks";
import { MIN_INDEXABLE, SCANS, runScan, sectorGroups } from "@/lib/programmatic";
import { DEFAULT_OG_IMAGE, seoDescription } from "@/lib/seo";
import { StockTable } from "@/components/StockTable";

type Params = { slug: string };
const BASE = "https://esham.pages.dev";

export const dynamicParams = false;

export function generateStaticParams(): Params[] {
  return SCANS.map((s) => ({ slug: s.slug }));
}

export async function generateMetadata({ params }: { params: Promise<Params> }): Promise<Metadata> {
  const { slug } = await params;
  const sc = SCANS.find((s) => s.slug === slug);
  const u = loadUniverse();
  if (!sc || !u) return { title: "Tarama bulunamadı" };
  const rows = runScan(u, sc);
  const title = `${sc.title}: BIST ${sc.hint} Listesi`;
  const description = seoDescription(`${sc.hint} koşulunu sağlayan ${rows.length} BIST hissesi, ${u.updated_at.slice(0, 10)} itibarıyla. F/K, PD/DD, ROE ve temettü ile birlikte listelenir.`);
  const url = `${BASE}/hisseler/tarama/${sc.slug}`;
  return {
    title,
    description,
    alternates: { canonical: url },
    robots: rows.length < MIN_INDEXABLE ? { index: false, follow: true } : undefined,
    openGraph: { title, description, url, siteName: "Esham", locale: "tr_TR", type: "website", images: [DEFAULT_OG_IMAGE] },
  };
}

export default async function ScanPage({ params }: { params: Promise<Params> }) {
  const { slug } = await params;
  const sc = SCANS.find((s) => s.slug === slug);
  const u = loadUniverse();
  if (!sc || !u) notFound();
  const rows = runScan(u, sc);
  const sectors = sectorGroups(u).filter((g) => g.stocks.length >= MIN_INDEXABLE);
  const date = u.updated_at.slice(0, 10);
  const bySector = new Map<string, number>();
  rows.forEach((s) => bySector.set(s.sector, (bySector.get(s.sector) ?? 0) + 1));
  const topSectors = [...bySector.entries()].sort((a, b) => b[1] - a[1]).slice(0, 3);

  const jsonLd = {
    "@context": "https://schema.org",
    "@graph": [
      {
        "@type": "BreadcrumbList",
        itemListElement: [
          { "@type": "ListItem", position: 1, name: "Esham", item: BASE },
          { "@type": "ListItem", position: 2, name: "Hisseler", item: `${BASE}/hisseler` },
          { "@type": "ListItem", position: 3, name: sc.title, item: `${BASE}/hisseler/tarama/${sc.slug}` },
        ],
      },
      { "@type": "ItemList", name: sc.title, itemListElement: rows.map((s, i) => ({ "@type": "ListItem", position: i + 1, url: `${BASE}/hisse/${s.ticker}`, name: s.name })) },
    ],
  };

  return (
    <div className="container mx-auto px-6 py-10">
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }} />
      <nav aria-label="Konum" className="text-sm text-zinc-400 mb-4">
        <Link href="/hisseler" className="hover:text-white">Hisseler</Link> <span aria-hidden>/</span> {sc.title}
      </nav>
      <header className="mb-8 max-w-3xl">
        <h1 className="text-3xl md:text-4xl font-display font-bold mb-3">{sc.h1}</h1>
        <p className="text-base text-zinc-300 leading-relaxed">
          Koşul: <strong className="text-white">{sc.hint}</strong>. {date} itibarıyla {rows.length} hisse bu koşulu sağlıyor
          {topSectors.length > 0 && <>; en çok {topSectors.map(([n, c]) => `${n} (${c})`).join(", ")} sektörlerinde</>}. Liste, ilgili orana göre sıralıdır; veri tutarsızlığı bayrağı taşıyan şirketler dışarıda bırakılır.
        </p>
      </header>

      {rows.length > 0 ? <StockTable rows={rows} caption={sc.title} /> : <p className="text-zinc-400">Şu an koşulu sağlayan hisse yok.</p>}

      <section className="mt-10 max-w-3xl">
        <h2 className="text-xl font-display font-semibold mb-3">Bu oran nasıl yorumlanır?</h2>
        <p className="text-base text-zinc-300 leading-relaxed">{sc.explain}</p>
        <p className="text-base text-zinc-300 leading-relaxed mt-3">
          Oranlar Yahoo Finance bilanço verisinden son 12 ay (TTM) üzerinden hesaplanır ve KAP ile teyit edilmemiştir. Bu liste yatırım tavsiyesi değildir.{" "}
          <Link href={`/hisseler?f=${sc.id}`} className="underline">Filtreyi tarayıcıda açıp başka koşullarla birleştirin</Link>.
        </p>
      </section>

      <section className="mt-10">
        <h2 className="text-xl font-display font-semibold mb-3">Diğer taramalar</h2>
        <div className="flex flex-wrap gap-2">
          {SCANS.filter((x) => x.slug !== sc.slug).map((x) => (
            <Link key={x.slug} href={`/hisseler/tarama/${x.slug}`} className="inline-flex items-center min-h-11 px-3.5 rounded-lg text-sm font-semibold bg-zinc-900 border border-zinc-800 text-zinc-200 hover:text-white">
              {x.title}
            </Link>
          ))}
        </div>
        <h2 className="text-xl font-display font-semibold mt-8 mb-3">Sektöre göre</h2>
        <div className="flex flex-wrap gap-2">
          {sectors.map((g) => (
            <Link key={g.slug} href={`/hisseler/sektor/${g.slug}`} className="inline-flex items-center min-h-11 px-3.5 rounded-lg text-sm bg-zinc-900 border border-zinc-800 text-zinc-300 hover:text-white">
              {g.name}
            </Link>
          ))}
        </div>
      </section>
    </div>
  );
}
