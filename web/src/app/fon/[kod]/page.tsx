import { SITE_URL } from "@/lib/config";
import { DEFAULT_OG_IMAGE, seoDescription, seoTitle } from "@/lib/seo";
import Link from "next/link";
import { notFound } from "next/navigation";
import type { Metadata } from "next";
import { ArrowLeft } from "lucide-react";
import { PERIODS, categoryGroups, describeFund, fmtInt, fmtMoney, fmtPct, fmtPrice, fmtSigned, riskLabel, topBy } from "@/lib/funds";
import { getFundCodes, loadFund, loadFundUniverse } from "@/lib/funds-data";
import { PriceChart, type ChartRange } from "@/components/PriceChart";
import { FundDisclaimer } from "@/components/FundDisclaimer";

type Params = { kod: string };

const FUND_RANGES: ChartRange[] = [
  { id: "3A", label: "3 Ay", days: 92 },
  { id: "6A", label: "6 Ay", days: 183 },
  { id: "1Y", label: "1 Yıl", days: 366 },
  { id: "3Y", label: "3 Yıl", days: 1096 },
  { id: "5Y", label: "5 Yıl", days: 99999 },
];
const FUND_CAPTION = "Günlük birim fiyat (TEFAS). Son 1 yıl günlük, daha eski dönem seyreltilmiş örnektir. Geçmiş performans gelecekteki getiriyi garanti etmez.";

export const dynamicParams = false;

export async function generateStaticParams(): Promise<Params[]> {
  return getFundCodes().map((kod) => ({ kod }));
}

export async function generateMetadata({ params }: { params: Promise<Params> }): Promise<Metadata> {
  const { kod } = await params;
  const code = kod.toUpperCase();
  const f = loadFund(code);
  if (!f) return { title: `${code} Fonu`, robots: { index: false } };
  const r1y = f.returns["1y"];
  const title = seoTitle(`${code} Fonu Getirisi, Risk ve Kategori Kıyası`);
  const description = seoDescription(
    `${code} (${f.name}) ${f.category.toLocaleLowerCase("tr")} fonu: fiyat grafiği${r1y !== null ? `, 1 yıllık getiri ${fmtPct(r1y)}` : ""}, reel getiri, oynaklık ve kategori sırası. Yatırım tavsiyesi değildir.`,
  );
  const url = `${SITE_URL}/fon/${code}`;
  return {
    title,
    description,
    alternates: { canonical: url },
    openGraph: { title, description, url, siteName: "Esham", locale: "tr_TR", type: "website", images: [DEFAULT_OG_IMAGE] },
  };
}

const returnTone = (v: number | null) => {
  if (v === null) return "text-zinc-400";
  return v >= 0 ? "text-emerald-400" : "text-red-400";
};
const cell = "px-3 py-2 text-right font-mono tabular-nums whitespace-nowrap";

export default async function FundPage({ params }: Readonly<{ params: Promise<Params> }>) {
  const { kod } = await params;
  const code = kod.toUpperCase();
  const f = loadFund(code);
  if (!f) notFound();

  const u = loadFundUniverse();
  const peers = u ? topBy(u.funds.filter((x) => x.category === f.category && x.code !== f.code), "r1y", 5) : [];
  const catSlug = u ? categoryGroups(u.funds).find((c) => c.name === f.category)?.slug : undefined;
  const paragraphs = describeFund(f);
  const medianByPeriod = f.category_median_1y;

  const jsonLd = {
    "@context": "https://schema.org",
    "@graph": [
      {
        "@type": "BreadcrumbList",
        itemListElement: [
          { "@type": "ListItem", position: 1, name: "Fonlar", item: `${SITE_URL}/fonlar` },
          { "@type": "ListItem", position: 2, name: code, item: `${SITE_URL}/fon/${code}` },
        ],
      },
      {
        "@type": "FinancialProduct",
        name: `${code} — ${f.name}`,
        category: f.category,
        url: `${SITE_URL}/fon/${code}`,
        description: paragraphs[0],
      },
    ],
  };

  const stats: [string, string][] = [
    ["Birim fiyat", `${fmtPrice(f.price)} ₺`],
    ["Günlük değişim", fmtSigned(f.daily)],
    ["Portföy büyüklüğü", fmtMoney(f.aum)],
    ["Yatırımcı sayısı", fmtInt(f.investors)],
    ["Yönetim ücreti (yıllık)", fmtPct(f.fee)],
    ["TEFAS risk değeri", riskLabel(f.risk)],
  ];

  return (
    <div className="container mx-auto px-6 py-10 max-w-5xl">
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd).replace(/</g, "\\u003c") }} />
      <nav aria-label="Konum" className="mb-4 text-sm">
        <Link href="/fonlar" className="inline-flex items-center gap-1 text-zinc-400 hover:text-white min-h-[44px]">
          <ArrowLeft className="w-4 h-4" /> Fonlar
        </Link>
      </nav>

      <header className="mb-6">
        <p className="text-xs uppercase tracking-wider text-zinc-400 mb-1">
          {catSlug ? (
            <Link href={`/fonlar/kategori/${catSlug}`} className="hover:text-white underline-offset-2 hover:underline">
              {f.category} fonu
            </Link>
          ) : (
            `${f.category} fonu`
          )}
        </p>
        <h1 className="text-3xl md:text-4xl font-display font-bold">
          <span className="font-mono">{code}</span> <span className="text-zinc-300 text-xl md:text-2xl font-semibold block md:inline">{f.name}</span>
        </h1>
        {f.as_of && <p className="text-xs text-zinc-400 mt-2">Son fiyat tarihi: {new Date(f.as_of).toLocaleDateString("tr-TR", { day: "numeric", month: "long", year: "numeric" })}</p>}
      </header>

      <section aria-label="Özet" className="grid grid-cols-2 md:grid-cols-3 gap-3 mb-6">
        {stats.map(([k, v]) => (
          <div key={k} className="rounded-xl border border-zinc-800 bg-zinc-950/80 p-4">
            <p className="text-xs text-zinc-400">{k}</p>
            <p className="font-mono text-lg font-semibold text-white tabular-nums mt-1">{v}</p>
          </div>
        ))}
      </section>

      <section aria-label="Fiyat grafiği" className="mb-8">
        <PriceChart ticker={code} series={f.prices} ranges={FUND_RANGES} digits={6} caption={FUND_CAPTION} />
      </section>

      <section aria-labelledby="getiriler" className="mb-8">
        <h2 id="getiriler" className="text-xl font-display font-bold mb-3">Getiriler</h2>
        <div className="overflow-x-auto rounded-2xl border border-zinc-800">
          <table className="w-full text-sm">
            <caption className="sr-only">{code} dönemsel nominal getirileri</caption>
            <thead className="bg-zinc-900/80 text-zinc-400">
              <tr>
                <th scope="col" className="text-left px-3 py-2.5 font-medium">Dönem</th>
                <th scope="col" className="text-right px-3 py-2.5 font-medium">Getiri</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-800/70">
              {PERIODS.map((p) => {
                const key = p.key === "ytd" ? "ytd" : (p.key.slice(1) as "1m" | "3m" | "6m" | "1y" | "3y" | "5y");
                const v = f.returns[key];
                return (
                  <tr key={p.key}>
                    <th scope="row" className="text-left px-3 py-2 font-normal text-zinc-300">{p.label}</th>
                    <td className={`${cell} ${returnTone(v)}`}>{fmtSigned(v)}</td>
                  </tr>
                );
              })}
              {medianByPeriod !== null && medianByPeriod !== undefined && (
                <tr className="bg-zinc-900/40">
                  <th scope="row" className="text-left px-3 py-2 font-normal text-zinc-300">Kategori medyanı (1 Yıl)</th>
                  <td className={`${cell} text-zinc-200`}>{fmtPct(medianByPeriod)}</td>
                </tr>
              )}
              <tr>
                <th scope="row" className="text-left px-3 py-2 font-normal text-zinc-300">Reel getiri, 1 Yıl (TÜFE&apos;ye göre)</th>
                <td className={`${cell} text-zinc-200`}>{fmtPct(f.real_1y)}</td>
              </tr>
              <tr>
                <th scope="row" className="text-left px-3 py-2 font-normal text-zinc-300">Dolar bazında getiri, 1 Yıl</th>
                <td className={`${cell} text-zinc-200`}>{fmtPct(f.usd_1y)}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <section aria-labelledby="risk" className="mb-8">
        <h2 id="risk" className="text-xl font-display font-bold mb-3">Risk (son 1 yıl)</h2>
        <dl className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {[
            ["Yıllık oynaklık", fmtPct(f.metrics.volatility)],
            ["Maks. düşüş", fmtPct(f.metrics.max_drawdown)],
            ["Sharpe (mevduata göre)", f.metrics.sharpe === null ? "—" : new Intl.NumberFormat("tr-TR", { minimumFractionDigits: 2 }).format(f.metrics.sharpe)],
            ["Kategori sırası (1Y)", f.category_rank ? `${f.category_rank.rank} / ${f.category_rank.of}` : "—"],
          ].map(([k, v]) => (
            <div key={k} className="rounded-xl border border-zinc-800 bg-zinc-950/80 p-4">
              <dt className="text-xs text-zinc-400">{k}</dt>
              <dd className="font-mono text-lg font-semibold text-white tabular-nums mt-1">{v}</dd>
            </div>
          ))}
        </dl>
      </section>

      {f.allocation && f.allocation.length > 0 && (
        <section aria-labelledby="dagilim" className="mb-8">
          <h2 id="dagilim" className="text-xl font-display font-bold mb-3">Portföy dağılımı</h2>
          <ul className="space-y-2">
            {f.allocation.map((a) => (
              <li key={a.type} className="flex items-center gap-3 text-sm">
                <span className="w-56 text-zinc-300">{a.type}</span>
                <span className="flex-1 h-2 rounded bg-zinc-800 overflow-hidden"><span className="block h-full bg-amber-500" style={{ width: `${Math.min(100, a.pct)}%` }} /></span>
                <span className="font-mono tabular-nums text-zinc-200 w-16 text-right">{fmtPct(a.pct)}</span>
              </li>
            ))}
          </ul>
        </section>
      )}

      <section aria-labelledby="yorum" className="mb-8">
        <h2 id="yorum" className="text-xl font-display font-bold mb-3">{code} fonu verilerle</h2>
        <div className="space-y-3 text-sm text-zinc-300 leading-relaxed max-w-3xl">
          {paragraphs.map((p) => (
            <p key={p}>{p}</p>
          ))}
        </div>
      </section>

      {peers.length > 0 && (
        <section aria-labelledby="benzer" className="mb-8">
          <h2 id="benzer" className="text-xl font-display font-bold mb-1">Aynı kategoride 1 yıllık getirisi yüksek fonlar</h2>
          <p className="text-xs text-zinc-400 mb-3">Sıralama geçmiş getiriye göredir; öneri değildir.</p>
          <ul className="grid md:grid-cols-5 gap-3">
            {peers.map((p) => (
              <li key={p.code}>
                <Link href={`/fon/${p.code}`} className="block rounded-xl border border-zinc-800 bg-zinc-950/80 p-3 hover:border-zinc-600 min-h-[44px]">
                  <span className="font-mono font-bold text-white">{p.code}</span>
                  <span className="block font-mono text-xs text-zinc-300 tabular-nums mt-1">{fmtSigned(p.r1y)} (1Y)</span>
                </Link>
              </li>
            ))}
          </ul>
        </section>
      )}

      <FundDisclaimer updatedAt={f.updated_at} />
    </div>
  );
}
