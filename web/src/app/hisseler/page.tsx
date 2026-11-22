import { SITE_URL } from "@/lib/config";
import { Suspense } from "react";
import type { Metadata } from "next";
import Link from "next/link";
import { StockScreener } from "@/components/StockScreener";
import { emptyStateText, loadUniverse, staleSummary } from "@/lib/stocks";

export const metadata: Metadata = {
  title: "BIST Hisse Tarayıcı — F/K, PD/DD, ROE, Temettü",
  description:
    "Borsa İstanbul hisselerini F/K, PD/DD, FD/FAVÖK, ROE, net marj ve temettü verimine göre filtreleyin ve sıralayın. Oranlar bilançolardan hesaplanır.",
  alternates: { canonical: `${SITE_URL}/hisseler` },
};

export default function HisselerPage() {
  const u = loadUniverse();
  const sectors = u ? Array.from(new Set(u.stocks.map((s) => s.sector))).sort((a, b) => a.localeCompare(b, "tr")) : [];

  const notice = u ? emptyStateText(staleSummary(u.stocks)) : null;

  return (
    <div className="container mx-auto px-6 py-10">
      <header className="mb-8 max-w-2xl">
        <h1 className="text-3xl md:text-4xl font-display font-bold mb-3">Hisse Tarayıcı</h1>
        <p className="text-sm text-zinc-400 leading-relaxed">
          {u ? `${u.count} BIST hissesi` : "BIST hisseleri"} — her şirketin oranlarını son 12 aylık bilançodan hesaplıyoruz.
          Başlıklara tıklayarak sıralayın, hazır filtrelerle daraltın, hissenin adına tıklayıp detaylı analizine gidin.
        </p>
      </header>

      {notice && <p className="mb-4 text-sm text-amber-400" role="note" data-empty-state>{notice}</p>}
      {u ? (
        <Suspense fallback={<p className="text-sm text-zinc-400">Yükleniyor…</p>}>
          <StockScreener stocks={u.stocks} sectors={sectors} />
        </Suspense>
      ) : (
        <p className="text-sm text-zinc-400">Hisse verisi henüz üretilmedi.</p>
      )}

      <p className="mt-6 text-xs text-zinc-400 leading-relaxed max-w-3xl">
        Kaynak: KAP bilançoları (kapsanan şirketlerde) ve Yahoo Finance; her hisse sayfasında kullanılan kaynak yazar. Oranlar Esham tarafından hesaplanır. Zarar eden şirketlerde F/K gösterilmez.
        Bazı şirketlerin tabloları USD/EUR cinsindendir; çarpanlar kurla tutarlı hale getirilmiştir. Enflasyon muhasebesi
        (TMS 29) etkisi karşılaştırmaları bozabilir. Bu sayfa yatırım tavsiyesi değildir.{" "}
        <Link href="/" className="underline hover:text-white">
          Ana sayfa
        </Link>
      </p>
    </div>
  );
}
