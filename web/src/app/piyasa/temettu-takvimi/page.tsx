import Link from "next/link";
import type { Metadata } from "next";
import { SITE_URL } from "@/lib/config";
import { SourceStamp } from "@/components/SourceStamp";
import { fmtDate, fmtNum, loadDividends } from "@/lib/kap-events";

export const metadata: Metadata = {
  title: "Kâr Payı Takvimi (KAP bildirimlerinden)",
  description:
    "BIST şirketlerinin KAP'a bildirdiği nakit kâr payı teklifleri ve kesinleşen kararlar: hak kullanım, kayıt ve ödeme tarihleri, hisse başına brüt ve net tutar. Her satır kendi KAP bildirimine bağlanır.",
  alternates: { canonical: `${SITE_URL}/piyasa/temettu-takvimi` },
};

const STATUS: Record<string, string> = { teklif: "Teklif (genel kurul onayı bekliyor)", kesinlesti: "Kesinleşti (hak kullanım tarihi kesin)" };

export default function DividendCalendarPage() {
  const doc = loadDividends();
  return (
    <div className="container mx-auto px-6 py-12 max-w-5xl">
      <p className="text-xs text-zinc-400 mb-6">
        <Link href="/" className="hover:text-white">Ana Sayfa</Link> / Piyasa / Kâr Payı Takvimi
      </p>
      <h1 className="text-2xl md:text-3xl font-display font-bold mb-3">Kâr Payı Takvimi</h1>
      <p className="text-sm text-zinc-300 leading-relaxed mb-6 max-w-3xl">
        Şirketlerin KAP&apos;a bildirdiği nakit kâr payı dağıtım kararları. Tutarlar bildirimdeki 1 TL nominal değerli pay başına rakamlardır;
        her hissenin <strong>en yeni</strong> bildirimi gösterilir. Bu sayfada fiyat kullanılmadığı için <strong>temettü verimi hesaplanmaz</strong>.
        Yatırım tavsiyesi değildir; karar vermeden önce bildirimi okuyun.
      </p>

      {!doc ? (
        <p className="rounded-xl border border-zinc-800 p-4 text-sm text-zinc-400">
          Bu bölüm için henüz doğrulanmış KAP verisi yok; veri gelene kadar bir şey gösterilmez.
        </p>
      ) : (
        <>
          <SourceStamp source={doc.source} sourceUrl={doc.sourceUrl} asOf={doc.asOf} fetchedAt={doc.fetchedAt} scan={doc.scan} />
          {doc.items.length === 0 ? (
            <p className="rounded-xl border border-zinc-800 p-4 text-sm text-zinc-400">Taranan pencerede nakit kâr payı dağıtımı bildiren hisse yok.</p>
          ) : (
            <div className="overflow-x-auto rounded-xl border border-zinc-800">
              <table className="w-full text-left text-sm text-zinc-300">
                <thead className="text-zinc-400 text-xs">
                  <tr>
                    <th className="px-3 py-2">Hisse</th>
                    <th className="px-3 py-2">Durum</th>
                    <th className="px-3 py-2 text-right">Brüt (TL/pay)</th>
                    <th className="px-3 py-2 text-right">Net (TL/pay)</th>
                    <th className="px-3 py-2">Hak kullanım</th>
                    <th className="px-3 py-2">Ödeme</th>
                    <th className="px-3 py-2">Bildirim</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-zinc-800/70">
                  {doc.items.flatMap((it) =>
                    it.installments.map((x, k) => (
                      <tr key={`${it.disclosureIndex}-${k}`}>
                        <td className="px-3 py-2">
                          <Link href={`/hisse/${it.ticker}`} className="font-semibold text-white hover:underline">{it.ticker}</Link>
                          <span className="block text-xs text-zinc-400">{it.name}{it.installments.length > 1 ? ` · ${x.label}` : ""}</span>
                        </td>
                        <td className="px-3 py-2 text-xs">{STATUS[it.status] ?? it.status}</td>
                        <td className="px-3 py-2 text-right font-mono">{fmtNum(x.grossPerShare, 4)}</td>
                        <td className="px-3 py-2 text-right font-mono">
                          {fmtNum(x.netPerShare, 4)}
                          <span className="block text-xs text-zinc-400">stopaj %{fmtNum(x.withholdingPct, 0)}</span>
                        </td>
                        <td className="px-3 py-2 whitespace-nowrap">{fmtDate(x.exDate)}{!x.exDateFinal && <span className="block text-xs text-zinc-400">teklif edilen</span>}</td>
                        <td className="px-3 py-2 whitespace-nowrap">{fmtDate(x.paymentDate)}</td>
                        <td className="px-3 py-2 text-xs whitespace-nowrap">
                          <a href={it.sourceUrl} target="_blank" rel="noopener noreferrer" className="underline hover:text-white">KAP #{it.disclosureIndex}</a>
                          <span className="block text-zinc-400">yayın {fmtDate(it.asOf)}</span>
                        </td>
                      </tr>
                    )),
                  )}
                </tbody>
              </table>
            </div>
          )}
          {(doc.noDividend?.length ?? 0) > 0 && (
            <p className="text-xs text-zinc-400 mt-5 leading-relaxed">
              <strong className="text-zinc-200">En yeni bildirimde nakit kâr payı dağıtılmayacağı belirtilen hisseler:</strong>{" "}
              {doc.noDividend!.map((n, i) => (
                <span key={n.disclosureIndex}>
                  {i > 0 && ", "}
                  <a href={n.sourceUrl} target="_blank" rel="noopener noreferrer" className="underline hover:text-white">{n.ticker}</a>
                  {" "}({fmtDate(n.asOf)})
                </span>
              ))}
              .
            </p>
          )}
        </>
      )}
      <p className="text-xs text-zinc-500 mt-8">Veri: KAP (Kamuyu Aydınlatma Platformu) bildirimleri, kamuya açık sayfalar. Esham yalnızca bildirimdeki rakamları okur; tutarlılık denetimi (net = brüt × (1 − stopaj)) geçmeyen bildirim yayınlanmaz.</p>
    </div>
  );
}
