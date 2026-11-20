import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { SITE_URL } from "@/lib/config";
import { loadUniverse } from "@/lib/stocks";
import { comparePair, comparePairs, sectorStats, slugify } from "@/lib/programmatic";
import { DEFAULT_OG_IMAGE, seoDescription } from "@/lib/seo";

type Params = { pair: string };
const nf = new Intl.NumberFormat("tr-TR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
function fmt(v: number | null, unit: "x" | "%"): string {
  if (v === null) return "—";
  return unit === "%" ? `%${nf.format(v)}` : `${nf.format(v)}x`;
}

export const dynamicParams = false;

export function generateStaticParams(): Params[] {
  const u = loadUniverse();
  const pairs = u ? comparePairs(u) : [];
  return pairs.length ? pairs.map((p) => ({ pair: p.slug })) : [{ pair: "yok" }];
}

function find(pair: string) {
  const u = loadUniverse();
  if (!u) return null;
  const hit = comparePairs(u).find((p) => p.slug === pair);
  return hit ? { u, ...hit } : null;
}

export async function generateMetadata({ params }: { params: Promise<Params> }): Promise<Metadata> {
  const { pair } = await params;
  const f = find(pair);
  if (!f) return { title: "Karşılaştırma bulunamadı" };
  const title = `${f.a.ticker} - ${f.b.ticker} Karşılaştırması: F/K, ROE, Temettü`;
  const description = seoDescription(`${f.a.name} ve ${f.b.name} hisselerini F/K, PD/DD, ROE, net marj ve temettü verimiyle yan yana karşılaştırın. Veri ${f.u.updated_at.slice(0, 10)} itibarıyla.`);
  const url = `${SITE_URL}/karsilastir/${f.slug}`;
  return { title, description, alternates: { canonical: url }, openGraph: { title, description, url, siteName: "Esham", locale: "tr_TR", type: "website", images: [DEFAULT_OG_IMAGE] } };
}

export default async function ComparePage({ params }: Readonly<{ params: Promise<Params> }>) {
  const { pair } = await params;
  const f = find(pair);
  if (!f) notFound();
  const { a, b, u } = f;
  const rows = comparePair(a, b);
  const winsA = rows.filter((r) => r.winner === "a").length;
  const winsB = rows.filter((r) => r.winner === "b").length;
  const date = u.updated_at.slice(0, 10);
  const st = sectorStats(u.stocks.filter((x) => x.sector === a.sector));
  const same = comparePairs(u).filter((p) => p.slug !== f.slug && (p.a.ticker === a.ticker || p.b.ticker === a.ticker || p.a.ticker === b.ticker || p.b.ticker === b.ticker)).slice(0, 8);

  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    itemListElement: [
      { "@type": "ListItem", position: 1, name: "Esham", item: SITE_URL },
      { "@type": "ListItem", position: 2, name: a.sector, item: `${SITE_URL}/hisseler/sektor/${slugify(a.sector)}` },
      { "@type": "ListItem", position: 3, name: `${a.ticker} - ${b.ticker}`, item: `${SITE_URL}/karsilastir/${f.slug}` },
    ],
  };

  return (
    <div className="container mx-auto px-6 py-10 max-w-4xl">
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }} />
      <nav aria-label="Konum" className="text-sm text-zinc-400 mb-4">
        <Link href={`/hisseler/sektor/${slugify(a.sector)}`} className="hover:text-white">{a.sector}</Link> <span aria-hidden>/</span> {a.ticker} - {b.ticker}
      </nav>
      <h1 className="text-3xl md:text-4xl font-display font-bold mb-3">{a.ticker} - {b.ticker} Karşılaştırması</h1>
      <p className="text-base text-zinc-300 leading-relaxed mb-8">
        {a.name} ({a.ticker}) ve {b.name} ({b.ticker}) aynı sektörde ({a.sector}) işlem görüyor. Aşağıda {date} itibarıyla son 12 aylık bilançodan hesaplanan oranlar yan yana veriliyor;
        {rows.length} oranın {winsA} tanesinde {a.ticker}, {winsB} tanesinde {b.ticker} daha avantajlı görünüyor. Bu bir üstünlük sıralaması değil, hangi tarafın tek tek oranlarda öne çıktığının özetidir.
      </p>

      <div className="overflow-x-auto rounded-xl border border-zinc-800">
        <table className="w-full text-base">
          <caption className="sr-only">{a.ticker} ve {b.ticker} oran karşılaştırması</caption>
          <thead className="bg-zinc-900 text-zinc-400 text-sm">
            <tr>
              <th scope="col" className="text-left font-medium px-4 py-3">Oran</th>
              <th scope="col" className="text-right font-medium px-4 py-3"><Link href={`/hisse/${a.ticker}`} className="font-bold text-white hover:underline">{a.ticker}</Link></th>
              <th scope="col" className="text-right font-medium px-4 py-3"><Link href={`/hisse/${b.ticker}`} className="font-bold text-white hover:underline">{b.ticker}</Link></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-800/60 tabular-nums">
            {rows.map((r) => (
              <tr key={r.metric.key}>
                <th scope="row" className="text-left px-4 py-3 font-normal text-zinc-300">
                  {r.metric.label} <span className="text-xs text-zinc-400">({r.metric.better === "low" ? "düşük iyi" : "yüksek iyi"})</span>
                </th>
                {(["a", "b"] as const).map((side) => (
                  <td key={side} className={`px-4 py-3 text-right ${r.winner === side ? "font-bold text-white" : "text-zinc-300"}`}>
                    {fmt(r[side], r.metric.unit)}
                    {r.winner === side && <span className="sr-only"> (avantajlı)</span>}
                    {r.winner === side && <span aria-hidden className="ml-1.5 text-emerald-400">●</span>}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="text-sm text-zinc-400 mt-3">● işareti, ilgili oranda daha avantajlı tarafı gösterir. Avantaj yön varsayımına bağlıdır; düşük F/K ucuzluk, yüksek ROE verimlilik işareti olabilir ancak tek başına karar nedeni değildir.</p>

      <section className="mt-10">
        <h2 className="text-xl font-display font-semibold mb-3">Sektör bağlamı ve nasıl okunur?</h2>
        <p className="text-base text-zinc-300 leading-relaxed">
          {a.sector} sektöründe {st.count} hisse izleniyor; sektörün medyan F/K oranı {fmt(st.pe, "x")}, medyan ROE&apos;si {fmt(st.roe, "%")}, medyan temettü verimi {fmt(st.dividend_yield, "%")}.
          {" "}{a.ticker} için F/K {fmt(a.pe, "x")}, {b.ticker} için {fmt(b.pe, "x")}; ROE ise sırasıyla {fmt(a.roe, "%")} ve {fmt(b.roe, "%")}. İki şirketi sektör medyanıyla birlikte okumak, tek başına birbirleriyle kıyaslamaktan daha sağlıklıdır.
        </p>
        <p className="text-base text-zinc-300 leading-relaxed mt-3">
          Şirketlerin iş modeli, büyüklüğü ve borçlanma yapısı farklı olabilir; geçici kâr artışları, enflasyon muhasebesi (TMS 29) ve döviz cinsinden tablolar oranları bozabilir. Bu nedenle bu tablo bir alım-satım önerisi değil, iki şirketin güncel rakamlarını tek bakışta görmek için hazırlanmış bir özet olarak değerlendirilmelidir.
        </p>
      </section>

      <section className="mt-10">
        <h2 className="text-xl font-display font-semibold mb-3">Ayrıntılı analiz</h2>
        <div className="flex flex-wrap gap-2">
          {[a, b].map((s) => (
            <Link key={s.ticker} href={`/hisse/${s.ticker}`} className="inline-flex items-center min-h-11 px-3.5 rounded-lg text-sm font-semibold bg-zinc-900 border border-zinc-800 text-zinc-200 hover:text-white">
              {s.ticker} hisse analizi
            </Link>
          ))}
          <Link href={`/hisseler/sektor/${slugify(a.sector)}`} className="inline-flex items-center min-h-11 px-3.5 rounded-lg text-sm bg-zinc-900 border border-zinc-800 text-zinc-300 hover:text-white">
            {a.sector} sektörü
          </Link>
        </div>
        {same.length > 0 && (
          <>
            <h2 className="text-xl font-display font-semibold mt-8 mb-3">Diğer karşılaştırmalar</h2>
            <div className="flex flex-wrap gap-2">
              {same.map((p) => (
                <Link key={p.slug} href={`/karsilastir/${p.slug}`} className="inline-flex items-center min-h-11 px-3.5 rounded-lg text-sm bg-zinc-900 border border-zinc-800 text-zinc-300 hover:text-white">
                  {p.a.ticker} - {p.b.ticker}
                </Link>
              ))}
            </div>
          </>
        )}
      </section>
      <p className="text-sm text-zinc-400 mt-8 border-t border-zinc-800 pt-4">
        Veriler KAP bilançolarına (kapsanan şirketlerde) ve Yahoo Finance'e dayanır, kaynak her hisse sayfasında belirtilir; hesaplama kuralları için <Link href="/yontem" className="underline">Yöntem ve Kaynaklar</Link> sayfasına bakın. Yatırım tavsiyesi değildir.
      </p>
    </div>
  );
}
