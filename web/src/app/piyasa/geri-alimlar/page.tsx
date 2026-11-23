import Link from "next/link";
import type { Metadata } from "next";
import { SITE_URL } from "@/lib/config";
import { SourceStamp } from "@/components/SourceStamp";
import { fmtDate, fmtInt, fmtNum, loadBuybacks, type BuybackItem } from "@/lib/kap-events";

export const metadata: Metadata = {
  title: "Pay Geri Alımları (KAP bildirimlerinden)",
  description:
    "Şirketlerin KAP'a bildirdiği pay geri alım işlemleri: işlem tarihi, adet, fiyat ve program limiti. Her satır kendi KAP bildirimine bağlanır.",
  alternates: { canonical: `${SITE_URL}/piyasa/geri-alimlar` },
};

export default function BuybacksPage() {
  const doc = loadBuybacks();
  // Her hisse için en yeni bildirim (liste zaten son işlem tarihine göre sıralı) + penceredeki bildirim sayısı
  const latest = new Map<string, { item: BuybackItem; n: number }>();
  for (const it of doc?.items ?? []) {
    const cur = latest.get(it.ticker);
    if (!cur) latest.set(it.ticker, { item: it, n: 1 });
    else cur.n += 1;
  }
  const rows = [...latest.values()];
  return (
    <div className="container mx-auto px-6 py-12 max-w-6xl">
      <p className="text-xs text-zinc-400 mb-6">
        <Link href="/" className="hover:text-white">Ana Sayfa</Link> / Piyasa / Pay Geri Alımları
      </p>
      <h1 className="text-2xl md:text-3xl font-display font-bold mb-3">Pay Geri Alımları</h1>
      <p className="text-sm text-zinc-300 leading-relaxed mb-6 max-w-3xl">
        Şirketlerin &quot;Payların Geri Alınmasına İlişkin Bildirim&quot;lerinden okunan işlemler. Adetler bildirimdeki nominal tutardır
        (1 TL nominal değerli payda adede eşit). Ortalama fiyat ve tutar, bildirimdeki işlem satırlarından <em>hesaplanır</em>
        (Σ adet × fiyat); program toplamı ve limit KAP&apos;ın kendi sütunlarındandır, bildirimde yoksa &quot;—&quot; yazar.
      </p>
      {!doc ? (
        <p className="rounded-xl border border-zinc-800 p-4 text-sm text-zinc-400">
          Bu bölüm için henüz doğrulanmış KAP verisi yok; veri gelene kadar bir şey gösterilmez.
        </p>
      ) : (
        <>
          <SourceStamp source={doc.source} sourceUrl={doc.sourceUrl} asOf={doc.asOf} fetchedAt={doc.fetchedAt} scan={doc.scan} />
          {rows.length === 0 ? (
            <p className="rounded-xl border border-zinc-800 p-4 text-sm text-zinc-400">Taranan pencerede işlenmiş geri alım bildirimi yok.</p>
          ) : (
            <div className="overflow-x-auto rounded-xl border border-zinc-800">
              <table className="w-full text-left text-sm text-zinc-300">
                <thead className="text-zinc-400 text-xs">
                  <tr>
                    <th className="px-3 py-2">Hisse</th>
                    <th className="px-3 py-2">Son işlem günü</th>
                    <th className="px-3 py-2 text-right">Adet (bildirim)</th>
                    <th className="px-3 py-2 text-right">Ort. fiyat (TL, hesaplanan)</th>
                    <th className="px-3 py-2 text-right">Tutar (TL, hesaplanan)</th>
                    <th className="px-3 py-2 text-right">Program toplamı / limit</th>
                    <th className="px-3 py-2">Bildirim</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-zinc-800/70">
                  {rows.map(({ item: it, n }) => (
                    <tr key={it.ticker}>
                      <td className="px-3 py-2">
                        <Link href={`/hisse/${it.ticker}`} className="font-semibold text-white hover:underline">{it.ticker}</Link>
                        <span className="block text-xs text-zinc-400">{it.name} · pencerede {n} bildirim</span>
                      </td>
                      <td className="px-3 py-2 whitespace-nowrap">{fmtDate(it.lastTradeDate)}</td>
                      <td className="px-3 py-2 text-right font-mono">{fmtInt(it.totalNominal)}</td>
                      <td className="px-3 py-2 text-right font-mono">{fmtNum(it.avgPrice, 2)}</td>
                      <td className="px-3 py-2 text-right font-mono">{fmtInt(it.amountTry)}</td>
                      <td className="px-3 py-2 text-right font-mono text-xs">
                        {it.programCumulativeNominal !== null ? fmtInt(it.programCumulativeNominal) : "—"} / {it.maxNominal !== null ? fmtInt(it.maxNominal) : "—"}
                        {it.fundTotalTry !== null && <span className="block text-zinc-400">fon {fmtInt(it.fundTotalTry)} TL</span>}
                      </td>
                      <td className="px-3 py-2 text-xs whitespace-nowrap">
                        <a href={it.sourceUrl} target="_blank" rel="noopener noreferrer" className="underline hover:text-white">KAP #{it.disclosureIndex}</a>
                        <span className="block text-zinc-400">yayın {fmtDate(it.asOf)}</span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
      <p className="text-xs text-zinc-500 mt-8">Veri: KAP bildirimleri. Bir bildirim birden çok işlem gününü kapsayabilir; satırdaki adet o bildirimdeki tüm işlem satırlarının toplamıdır. Yatırım tavsiyesi değildir.</p>
    </div>
  );
}
