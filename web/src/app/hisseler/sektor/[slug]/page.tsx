import { SITE_URL } from "@/lib/config";
import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { loadUniverse } from "@/lib/stocks";
import { MIN_INDEXABLE, SCANS, comparePairs, sectorGroups, sectorStats } from "@/lib/programmatic";
import { DEFAULT_OG_IMAGE, seoDescription } from "@/lib/seo";
import { StockTable } from "@/components/StockTable";
import { emptyStateText, isStale, staleSummary } from "@/lib/stocks";

type Params = { slug: string };
const nf = new Intl.NumberFormat("tr-TR", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
const fx = (v: number | null) => (v === null ? "—" : `${nf.format(v)}x`);
const fp = (v: number | null) => (v === null ? "—" : `%${nf.format(v)}`);

export const dynamicParams = false;

export function generateStaticParams(): Params[] {
  const u = loadUniverse();
  return u ? sectorGroups(u).map((g) => ({ slug: g.slug })) : [{ slug: "yok" }];
}

function find(slug: string) {
  const u = loadUniverse();
  if (!u) return null;
  const groups = sectorGroups(u);
  const g = groups.find((x) => x.slug === slug);
  return g ? { u, g, groups } : null;
}

export async function generateMetadata({ params }: { params: Promise<Params> }): Promise<Metadata> {
  const { slug } = await params;
  const f = find(slug);
  if (!f) return { title: "Sektör bulunamadı" };
  const { g, u } = f;
  const st = sectorStats(g.stocks);
  const title = `${g.name} Hisseleri: F/K, PD/DD, ROE`;
  const description = seoDescription(
    `Borsa İstanbul ${g.name} sektöründeki ${g.stocks.length} hisse: medyan F/K ${fx(st.pe)}, medyan ROE ${fp(st.roe)}. Oranlar bilançodan hesaplanır, tarama zamanı ${u.updated_at.slice(0, 10)}.`,
  );
  const url = `${SITE_URL}/hisseler/sektor/${g.slug}`;
  return {
    title,
    description,
    alternates: { canonical: url },
    robots: g.stocks.length < MIN_INDEXABLE ? { index: false, follow: true } : undefined,
    openGraph: { title, description, url, siteName: "Esham", locale: "tr_TR", type: "website", images: [DEFAULT_OG_IMAGE] },
  };
}

export default async function SectorPage({ params }: { params: Promise<Params> }) {
  const { slug } = await params;
  const f = find(slug);
  if (!f) notFound();
  const { u, g, groups } = f;
  const st = sectorStats(g.stocks);
  const ok = g.stocks.filter((s) => !s.suspect && !isStale(s));
  const cheapest = [...ok].filter((s) => s.pe !== null && s.pe > 0).sort((a, b) => a.pe! - b.pe!)[0];
  const bestRoe = [...ok].filter((s) => s.roe !== null && Math.abs(s.roe) < 200).sort((a, b) => b.roe! - a.roe!)[0];
  const topYield = [...ok].filter((s) => (s.dividend_yield ?? 0) > 0).sort((a, b) => b.dividend_yield! - a.dividend_yield!)[0];
  const others = groups.filter((x) => x.slug !== g.slug && x.stocks.length >= MIN_INDEXABLE);
  const date = u.updated_at.slice(0, 10); // TARAMA zamanı, satırların veri tarihi değil
  const staleCount = st.staleCount;
  const pairs = comparePairs(u).filter((p) => p.a.sector === g.name);

  const jsonLd = {
    "@context": "https://schema.org",
    "@graph": [
      {
        "@type": "BreadcrumbList",
        itemListElement: [
          { "@type": "ListItem", position: 1, name: "Esham", item: SITE_URL },
          { "@type": "ListItem", position: 2, name: "Hisseler", item: `${SITE_URL}/hisseler` },
          { "@type": "ListItem", position: 3, name: g.name, item: `${SITE_URL}/hisseler/sektor/${g.slug}` },
        ],
      },
      {
        "@type": "ItemList",
        name: `${g.name} hisseleri`,
        itemListElement: g.stocks.map((s, i) => ({ "@type": "ListItem", position: i + 1, url: `${SITE_URL}/hisse/${s.ticker}`, name: s.name })),
      },
    ],
  };

  return (
    <div className="container mx-auto px-6 py-10">
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }} />
      <nav aria-label="Konum" className="text-sm text-zinc-400 mb-4">
        <Link href="/hisseler" className="hover:text-white">Hisseler</Link> <span aria-hidden>/</span> {g.name}
      </nav>
      <header className="mb-8 max-w-3xl">
        <h1 className="text-3xl md:text-4xl font-display font-bold mb-3">{g.name} Hisseleri</h1>
        <p className="text-base text-zinc-300 leading-relaxed">
          Borsa İstanbul&apos;da {g.name} sektöründe {g.stocks.length} hisse izliyoruz. Sektörün medyan F/K oranı {fx(st.pe)}, medyan PD/DD oranı {fx(st.pb)},
          medyan ROE&apos;si {fp(st.roe)} ve medyan temettü verimi {fp(st.dividend_yield)}. Aşağıdaki tablo piyasa değerine göre sıralıdır; tarama zamanı {date}; veriler son 12 aylık bilançodan hesaplanmıştır.
        </p>
      </header>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-8">
        {[
          ["Medyan F/K", fx(st.pe)],
          ["Medyan PD/DD", fx(st.pb)],
          ["Medyan ROE", fp(st.roe)],
          ["Medyan temettü", fp(st.dividend_yield)],
        ].map(([k, v]) => (
          <div key={k} className="rounded-xl border p-4" style={{ borderColor: "var(--border)", background: "var(--surface)" }}>
            <div className="text-xs text-zinc-400">{k}</div>
            <div className="text-xl font-bold tabular-nums">{v}</div>
          </div>
        ))}
      </div>

      {emptyStateText(staleSummary(g.stocks)) && (
        <p className="mb-3 text-sm text-amber-400" role="note" data-empty-state>{emptyStateText(staleSummary(g.stocks))}</p>
      )}
      {staleCount > 0 && (
        <p className="mb-3 text-sm text-amber-400" role="note">
          {staleCount} hisse için son turda veri alınamadı: satırlarında &quot;bayat&quot; yazar, sektör medyanına ve en düşük/en yüksek özetlerine dahil edilmez.
        </p>
      )}
      <StockTable rows={g.stocks} caption={`${g.name} sektörü hisseleri ve temel oranları`} />

      <section className="mt-10 max-w-3xl">
        <h2 className="text-xl font-display font-semibold mb-3">Sektörde öne çıkanlar</h2>
        <ul className="space-y-2 text-base text-zinc-300 leading-relaxed list-disc pl-5">
          {cheapest && (
            <li>
              En düşük F/K: <Link href={`/hisse/${cheapest.ticker}`} className="font-semibold text-white underline">{cheapest.ticker}</Link> ({fx(cheapest.pe)}), sektör medyanı {fx(st.pe)}.
            </li>
          )}
          {bestRoe && (
            <li>
              En yüksek ROE: <Link href={`/hisse/${bestRoe.ticker}`} className="font-semibold text-white underline">{bestRoe.ticker}</Link> ({fp(bestRoe.roe)}), sektör medyanı {fp(st.roe)}.
            </li>
          )}
          {topYield && (
            <li>
              En yüksek temettü verimi: <Link href={`/hisse/${topYield.ticker}`} className="font-semibold text-white underline">{topYield.ticker}</Link> ({fp(topYield.dividend_yield)}).
            </li>
          )}
        </ul>
        <h2 className="text-xl font-display font-semibold mt-8 mb-3">Nasıl okunur?</h2>
        <p className="text-base text-zinc-300 leading-relaxed">
          Aynı sektördeki şirketler benzer maliyet yapısına ve döngüye sahip olduğu için oranları sektör medyanıyla karşılaştırmak, tek başına bir sayıya bakmaktan daha anlamlıdır.
          F/K, PD/DD ve ROE tek başına bir sonuç vermez; geçici kâr artışları, enflasyon muhasebesi (TMS 29) ve döviz cinsinden tablolar karşılaştırmayı bozabilir.
          Veri tutarsızlığı bayrağı taşıyan hisseler medyan hesabına katılmaz. Bu sayfa yatırım tavsiyesi değildir.{" "}
          <Link href="/hisseler" className="underline">Tüm hisseleri filtreleyin</Link>.
        </p>
      </section>

      <section className="mt-10">
        <h2 className="text-xl font-display font-semibold mb-3">Hazır taramalar</h2>
        <div className="flex flex-wrap gap-2">
          {SCANS.map((sc) => (
            <Link key={sc.slug} href={`/hisseler/tarama/${sc.slug}`} className="inline-flex items-center min-h-11 px-3.5 rounded-lg text-sm font-semibold bg-zinc-900 border border-zinc-800 text-zinc-200 hover:text-white">
              {sc.title}
            </Link>
          ))}
        </div>
        {pairs.length > 0 && (
          <>
            <h2 className="text-xl font-display font-semibold mt-8 mb-3">Hisse karşılaştırmaları</h2>
            <div className="flex flex-wrap gap-2">
              {pairs.map((p) => (
                <Link key={p.slug} href={`/karsilastir/${p.slug}`} className="inline-flex items-center min-h-11 px-3.5 rounded-lg text-sm bg-zinc-900 border border-zinc-800 text-zinc-300 hover:text-white">
                  {p.a.ticker} - {p.b.ticker}
                </Link>
              ))}
            </div>
          </>
        )}
        {others.length > 0 && (
          <>
            <h2 className="text-xl font-display font-semibold mt-8 mb-3">Diğer sektörler</h2>
            <div className="flex flex-wrap gap-2">
              {others.map((o) => (
                <Link key={o.slug} href={`/hisseler/sektor/${o.slug}`} className="inline-flex items-center min-h-11 px-3.5 rounded-lg text-sm bg-zinc-900 border border-zinc-800 text-zinc-300 hover:text-white">
                  {o.name} <span className="ml-1.5 text-zinc-400">({o.stocks.length})</span>
                </Link>
              ))}
            </div>
          </>
        )}
      </section>
    </div>
  );
}
