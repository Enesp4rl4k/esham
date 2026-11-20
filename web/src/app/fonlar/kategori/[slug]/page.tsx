import { SITE_URL } from "@/lib/config";
import { seoDescription, seoTitle } from "@/lib/seo";
import Link from "next/link";
import { notFound } from "next/navigation";
import type { Metadata } from "next";
import { ArrowLeft } from "lucide-react";
import { MIN_CATEGORY_FUNDS, categoryGroups, fmtMoney, fmtPct, fmtSigned, sortBy, topBy } from "@/lib/funds";
import { loadFundUniverse } from "@/lib/funds-data";
import { FundDisclaimer } from "@/components/FundDisclaimer";

type Params = { slug: string };

export const dynamicParams = false;

const groups = () => {
  const u = loadFundUniverse();
  return u ? categoryGroups(u.funds) : [];
};

export async function generateStaticParams(): Promise<Params[]> {
  return groups().map((c) => ({ slug: c.slug }));
}

export async function generateMetadata({ params }: { params: Promise<Params> }): Promise<Metadata> {
  const { slug } = await params;
  const c = groups().find((g) => g.slug === slug);
  if (!c) return { title: "Fon Kategorisi", robots: { index: false } };
  const title = seoTitle(`${c.name} Fonları: Getiri ve Risk Sıralaması`);
  return {
    title,
    description: seoDescription(`TEFAS'ta işlem gören ${c.funds.length} ${c.name.toLocaleLowerCase("tr")} fonunu 1 yıllık getiri, reel getiri, oynaklık ve büyüklüğe göre karşılaştırın.`),
    alternates: { canonical: `${SITE_URL}/fonlar/kategori/${c.slug}` },
    // Kalite kapısı: az fonlu kategori ince içeriktir → dizine alınmaz
    robots: c.funds.length < MIN_CATEGORY_FUNDS ? { index: false, follow: true } : undefined,
  };
}

export default async function CategoryPage({ params }: { params: Promise<Params> }) {
  const { slug } = await params;
  const u = loadFundUniverse();
  const c = groups().find((g) => g.slug === slug);
  if (!u || !c) notFound();

  const median = u.category_median_1y[c.name];
  const best = topBy(c.funds, "r1y", 1)[0];
  const worst = sortBy(c.funds.filter((f) => f.r1y !== null), "r1y", 1)[0];
  const rows = sortBy(c.funds, "r1y", -1);

  return (
    <div className="container mx-auto px-6 py-10">
      <nav aria-label="Konum" className="mb-4 text-sm">
        <Link href="/fonlar" className="inline-flex items-center gap-1 text-zinc-400 hover:text-white min-h-[44px]">
          <ArrowLeft className="w-4 h-4" /> Tüm fonlar
        </Link>
      </nav>
      <header className="mb-6 max-w-3xl">
        <h1 className="text-3xl md:text-4xl font-display font-bold mb-3">{c.name} fonları</h1>
        <p className="text-sm text-zinc-300 leading-relaxed">
          Esham&apos;ın izlediği en büyük fonlar arasında {c.funds.length} {c.name.toLocaleLowerCase("tr")} fonu var.
          {median !== undefined && ` Bu fonların medyan 1 yıllık getirisi ${fmtPct(median)}.`}
          {best && worst && best.code !== worst.code && ` Son 1 yılda en yüksek getiriyi ${best.code} (${fmtPct(best.r1y)}), en düşük getiriyi ${worst.code} (${fmtPct(worst.r1y)}) sağladı.`}{" "}
          Sıralama geçmiş getiriye göredir ve fon önerisi değildir; getiri, risk ve ücret birlikte değerlendirilmelidir.
        </p>
      </header>

      <div className="overflow-x-auto rounded-2xl border border-zinc-800 mb-8">
        <table className="w-full text-sm">
          <caption className="sr-only">{c.name} fonlarının 1 yıllık getiriye göre sıralaması</caption>
          <thead className="bg-zinc-900/80 text-zinc-400">
            <tr>
              <th scope="col" className="text-left px-3 py-2.5 font-medium">#</th>
              <th scope="col" className="text-left px-3 py-2.5 font-medium">Fon</th>
              <th scope="col" className="text-right px-3 py-2.5 font-medium">1 Yıl</th>
              <th scope="col" className="text-right px-3 py-2.5 font-medium">Reel 1Y</th>
              <th scope="col" className="text-right px-3 py-2.5 font-medium">Oynaklık</th>
              <th scope="col" className="text-right px-3 py-2.5 font-medium">Büyüklük</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-800/70">
            {rows.map((f, i) => (
              <tr key={f.code} className="hover:bg-zinc-900/50">
                <td className="px-3 py-2 text-zinc-400 tabular-nums">{i + 1}</td>
                <td className="px-3 py-2 min-w-[14rem]">
                  <Link href={`/fon/${f.code}`} className="font-mono font-bold text-white hover:text-amber-300">{f.code}</Link>
                  <span className="block text-xs text-zinc-400 line-clamp-1">{f.name}</span>
                </td>
                <td className="px-3 py-2 text-right font-mono tabular-nums">{fmtSigned(f.r1y)}</td>
                <td className="px-3 py-2 text-right font-mono tabular-nums text-zinc-200">{fmtPct(f.real_1y)}</td>
                <td className="px-3 py-2 text-right font-mono tabular-nums text-zinc-200">{fmtPct(f.vol)}</td>
                <td className="px-3 py-2 text-right font-mono tabular-nums text-zinc-200">{fmtMoney(f.aum)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <FundDisclaimer updatedAt={u.updated_at} />
    </div>
  );
}
