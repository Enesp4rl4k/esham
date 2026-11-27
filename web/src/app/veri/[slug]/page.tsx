import { SITE_URL } from "@/lib/config";
import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { DataChart } from "@/components/DataChart";
import { Disclaimer } from "@/components/Disclaimer";
import { seoDescription, seoTitle } from "@/lib/seo";
import {
  DEFAULT_VARIANT,
  SAMPLE_MARK,
  buildScene,
  displayDomain,
  isIndexableDataset,
  lastPeriod,
  periodLabel,
  periodLong,
  tableRows,
  textAlternative,
  type VeriDataset,
} from "@/lib/veri";
import { getDataset, loadDatasets, publishedCards } from "@/lib/veri-data";

type Params = { slug: string };

export const dynamicParams = false;

export function generateStaticParams(): Params[] {
  const all = loadDatasets();
  return all.length ? all.map((d) => ({ slug: d.slug })) : [{ slug: "yok" }];
}

export async function generateMetadata({ params }: { params: Promise<Params> }): Promise<Metadata> {
  const { slug } = await params;
  const ds = getDataset(slug);
  if (!ds) return { title: "Veri bulunamadı", robots: { index: false, follow: true } };
  const title = seoTitle(ds.sample ? `${SAMPLE_MARK}: ${ds.title}` : ds.title);
  const description = seoDescription(ds.description);
  const url = `${SITE_URL}/veri/${ds.slug}`;
  const cards = publishedCards(ds.slug);
  const images = cards.map((c) => ({ url: c.url, width: c.width, height: c.height, alt: `${ds.title} — grafik` }));
  return {
    title,
    description,
    alternates: { canonical: url },
    robots: isIndexableDataset(ds) ? undefined : { index: false, follow: true },
    openGraph: { title, description, url, siteName: "Esham", locale: "tr_TR", type: "article", images },
    twitter: { card: "summary_large_image", title, description, images: images.slice(0, 1).map((i) => i.url) },
  };
}

function Meta({ ds }: { ds: VeriDataset }) {
  const lp = lastPeriod(ds);
  return (
    <dl className="grid gap-x-6 gap-y-2 sm:grid-cols-2 lg:grid-cols-4 rounded-xl border border-zinc-800 bg-zinc-950/60 p-4 text-sm mb-8">
      <div>
        <dt className="text-xs text-zinc-400">Kaynak</dt>
        <dd className="text-zinc-200">
          <a href={ds.source.url} target="_blank" rel="noopener noreferrer" className="underline hover:text-white">
            {ds.source.name}
          </a>
          , {ds.source.publication}
        </dd>
      </div>
      <div>
        <dt className="text-xs text-zinc-400">Son veri</dt>
        <dd className="text-zinc-200">{periodLong(lp, ds.periodType)}</dd>
      </div>
      <div>
        <dt className="text-xs text-zinc-400">Birim</dt>
        <dd className="text-zinc-200">{ds.unit}</dd>
      </div>
      <div>
        <dt className="text-xs text-zinc-400">Kapsam</dt>
        <dd className="text-zinc-200">{ds.coverage}</dd>
      </div>
    </dl>
  );
}

export default async function VeriPage({ params }: { params: Promise<Params> }) {
  const { slug } = await params;
  const ds = getDataset(slug);
  if (!ds) notFound();
  const domain = { domain: displayDomain(SITE_URL) };
  const wide = buildScene(ds, "1600x900", DEFAULT_VARIANT, domain);
  const tall = buildScene(ds, "1080x1350", DEFAULT_VARIANT, domain);
  const rows = tableRows(ds);
  const alt = textAlternative(ds);
  const cards = publishedCards(ds.slug);
  const fileList = Object.entries(ds.files);
  const firstFile = fileList[0]?.[1];
  const lastFile = fileList[fileList.length - 1]?.[1];

  return (
    <div className="container mx-auto px-4 sm:px-6 py-10 max-w-6xl">
      <p className="text-xs text-zinc-400 mb-6">
        <Link href="/" className="hover:text-white">Ana Sayfa</Link> / <Link href="/veri" className="hover:text-white">Veri</Link> / {ds.title}
      </p>
      {ds.sample && (
        <p role="note" className="mb-6 rounded-xl border border-amber-700/60 bg-amber-950/30 px-4 py-3 text-sm font-semibold text-amber-300">
          {SAMPLE_MARK}: Bu sayfadaki değerler gerçek değildir; yalnızca biçimi göstermek için üretilmiş sentetik bir örnektir.
        </p>
      )}
      <p className="text-xs uppercase tracking-wider text-amber-400 mb-2">Veri · {ds.kicker}</p>
      <h1 className="text-2xl md:text-4xl font-display font-bold mb-3">{ds.title}</h1>
      <p className="text-sm text-zinc-300 leading-relaxed mb-6 max-w-3xl">
        {ds.measure}, {ds.periodType === "quarter" ? "çeyreklik" : ds.periodType === "month" ? "aylık" : "yıllık"} ({periodLabel(ds.periods[0], ds.periodType)} –{" "}
        {periodLabel(lastPeriod(ds), ds.periodType)}). Değerler kaynağın yayımladığı biçimdedir; yorum, sıralama ya da tahmin içermez.
      </p>

      <Meta ds={ds} />

      <section aria-labelledby="grafik" className="mb-10">
        <h2 id="grafik" className="sr-only">Grafik</h2>
        <DataChart wide={wide} tall={tall} title={ds.title} desc={alt} decimals={ds.decimals ?? 0} />
        <p className="mt-3 text-sm text-zinc-300 leading-relaxed">
          <strong className="text-zinc-100">Metin alternatifi:</strong> {alt}
        </p>
        <div className="mt-4 flex flex-wrap gap-3 text-sm">
          <a href={`/veri/${ds.slug}/veri.csv`} download={`${ds.slug}.csv`} className="rounded-lg border border-zinc-700 px-3 py-1.5 hover:border-amber-400 hover:text-white">
            CSV indir
          </a>
          {cards.map((c) => (
            <a key={c.size} href={c.url} download className="rounded-lg border border-zinc-700 px-3 py-1.5 hover:border-amber-400 hover:text-white">
              Paylaşım görseli ({c.size.replace("x", "×")})
            </a>
          ))}
        </div>
      </section>

      <section aria-labelledby="tablo" className="mb-10">
        <h2 id="tablo" className="text-xl font-display font-bold mb-3">Veri tablosu</h2>
        <div className="overflow-x-auto rounded-xl border border-zinc-800">
          <table className="w-full text-sm">
            <caption className="text-left text-xs text-zinc-400 px-4 py-2">
              {ds.measure} ({ds.unit}), en yeni dönem üstte. Boş hücre (—): kaynakta değer yok.
            </caption>
            <thead className="bg-zinc-900/60 text-zinc-300">
              <tr>
                <th scope="col" className="text-left font-medium px-4 py-2 whitespace-nowrap">Dönem</th>
                {ds.series.map((s) => (
                  <th key={s.id} scope="col" className="text-right font-medium px-4 py-2 whitespace-nowrap">
                    {s.ticker ? (
                      <Link href={`/hisse/${s.ticker}`} className="hover:text-white underline-offset-2 hover:underline">
                        {s.label}
                      </Link>
                    ) : (
                      s.label
                    )}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.period} className="border-t border-zinc-800/70">
                  <th scope="row" className="text-left font-normal text-zinc-300 px-4 py-1.5 whitespace-nowrap">{r.label}</th>
                  {r.cells.map((c, i) => (
                    <td key={i} className="text-right font-mono px-4 py-1.5 text-zinc-100">{c}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section aria-labelledby="yontem" className="mb-10 max-w-3xl">
        <h2 id="yontem" className="text-xl font-display font-bold mb-3">Yöntem</h2>
        <ul className="list-disc pl-5 space-y-2 text-sm text-zinc-300 leading-relaxed">
          {ds.methodology.map((m, i) => (
            <li key={i}>{m}</li>
          ))}
        </ul>
        {ds.breaks.length > 0 && (
          <>
            <h3 className="text-base font-display font-bold mt-6 mb-2">Seri kırılmaları</h3>
            <ul className="list-disc pl-5 space-y-1 text-sm text-zinc-300">
              {ds.breaks.map((b) => (
                <li key={b.period}>
                  {periodLabel(b.period, ds.periodType)}: {b.note}
                </li>
              ))}
            </ul>
          </>
        )}
        <h3 className="text-base font-display font-bold mt-6 mb-2">Kaynak ve kullanım koşulları</h3>
        <p className="text-sm text-zinc-300 leading-relaxed">
          {ds.source.terms}{" "}
          <a href={ds.source.termsUrl} target="_blank" rel="noopener noreferrer" className="underline hover:text-white">
            Kullanım koşulları
          </a>
          . Her değerin kaynak dosyası, tablo sayfası ve hücresi veri dosyasında saklanır
          ({fileList.length} rapor{firstFile && lastFile ? `; ilk: ${firstFile.name}, son: ${lastFile.name}` : ""}).{" "}
          <a href={`/data/veri/${ds.slug}.json`} className="underline hover:text-white">
            Kaynak bilgili veri dosyası (JSON)
          </a>
          .
        </p>
        <p className="text-xs text-zinc-400 mt-3">Son güncelleme: {ds.updatedAt}</p>
      </section>

      <Disclaimer />
    </div>
  );
}
