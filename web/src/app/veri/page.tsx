import { SITE_URL } from "@/lib/config";
import type { Metadata } from "next";
import Link from "next/link";
import { Disclaimer } from "@/components/Disclaimer";
import { SAMPLE_MARK, cardPath, isIndexableDataset, lastPeriod, periodLabel } from "@/lib/veri";
import { loadDatasets, publishedCards } from "@/lib/veri-data";

export const metadata: Metadata = {
  title: "Veri Grafikleri",
  description: "Kamuya açık resmî istatistiklerden zaman serisi grafikleri: her değer kaynağı, dosyası ve tarihiyle; tablo ve CSV ile.",
  alternates: { canonical: `${SITE_URL}/veri` },
};

export default function VeriIndex() {
  const all = loadDatasets();
  const visible = all.filter((d) => isIndexableDataset(d));
  const samples = all.filter((d) => !isIndexableDataset(d));
  return (
    <div className="container mx-auto px-4 sm:px-6 py-10 max-w-6xl">
      <p className="text-xs text-zinc-400 mb-6">
        <Link href="/" className="hover:text-white">Ana Sayfa</Link> / Veri
      </p>
      <h1 className="text-2xl md:text-4xl font-display font-bold mb-3">Veri Grafikleri</h1>
      <p className="text-sm text-zinc-300 leading-relaxed mb-8 max-w-3xl">
        Kamuya açık resmî istatistiklerden derlenen zaman serileri. Her grafik bir veri tablosu, CSV dosyası ve paylaşım görseliyle
        birlikte yayımlanır; her değerin kaynak dosyası ve hücresi saklanır. Eksik dönemler boş bırakılır. Yorum, sıralama ya da tahmin yoktur.
      </p>
      {all.length === 0 ? (
        <p className="rounded-xl border border-zinc-800 p-4 text-sm text-zinc-400">Henüz yayımlanmış veri grafiği yok.</p>
      ) : (
        <ul className="grid gap-5 sm:grid-cols-2">
          {[...visible, ...samples].map((d) => {
            const card = publishedCards(d.slug).find((c) => c.size === "1600x900");
            return (
              <li key={d.slug} className="rounded-2xl border border-zinc-800 bg-zinc-950/60 overflow-hidden hover:border-zinc-600 transition-colors">
                <Link href={`/veri/${d.slug}`} className="block">
                  {card && (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img src={cardPath(d.slug, "1600x900")} alt="" width={card.width} height={card.height} loading="lazy" className="w-full h-auto" />
                  )}
                  <div className="p-4">
                    <p className="text-xs uppercase tracking-wider text-amber-400 mb-1">
                      {d.sample ? SAMPLE_MARK : d.kicker}
                    </p>
                    <h2 className="text-lg font-display font-bold mb-1">{d.title}</h2>
                    <p className="text-xs text-zinc-400">
                      Kaynak: {d.source.short} · Birim: {d.unit} · Son veri: {periodLabel(lastPeriod(d), d.periodType)}
                    </p>
                  </div>
                </Link>
              </li>
            );
          })}
        </ul>
      )}
      <div className="mt-10">
        <Disclaimer />
      </div>
    </div>
  );
}
