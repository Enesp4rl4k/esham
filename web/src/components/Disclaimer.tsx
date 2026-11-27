/**
 * Yasal uyarı. SPK açısından her rapor sayfasında ve site genelinde görünür olmalı.
 * "compact" varyantı kart altları/footer için, tam varyant rapor sonu için.
 * `SummaryNotice` rapor başlığının hemen altında gösterilen kısa uyarıdır.
 */
export const KAP_NOTICE =
  "Bu sayfa, kamuya açık bir KAP bildiriminin otomatik özetidir; yatırım tavsiyesi değildir.";
export const GENERIC_NOTICE =
  "Bu sayfa, kamuya açık verilerin otomatik özetidir; yatırım tavsiyesi değildir.";

export function SummaryNotice({ kap }: { kap: boolean }) {
  return (
    <p
      role="note"
      className="mb-8 rounded-xl border border-amber-900/30 bg-amber-950/10 px-4 py-3 text-sm text-amber-200/90 leading-relaxed"
    >
      {kap ? KAP_NOTICE : GENERIC_NOTICE}{" "}
      {kap && <span className="text-zinc-400">Bilginin aslı için KAP&apos;taki bildirime bakınız.</span>}
    </p>
  );
}

export function Disclaimer({ compact = false }: { compact?: boolean }) {
  if (compact) {
    return (
      <p className="text-xs text-zinc-400 leading-relaxed">
        Bu içerik yapay zeka tarafından üretilmiştir ve yatırım tavsiyesi niteliği
        taşımaz. Yatırım kararlarınızı yetkili bir danışmana danışarak veriniz.
      </p>
    );
  }
  return (
    <div className="rounded-2xl border border-amber-900/30 bg-amber-950/10 p-5">
      <p className="text-sm font-medium text-amber-400 mb-2">Yasal Uyarı</p>
      <p className="text-sm text-zinc-400 leading-relaxed">
        Burada yer alan bilgiler yalnızca genel bilgilendirme amaçlıdır ve kamuya açık
        kaynaklardaki (KAP bildirimleri, borsa verileri) bilgiler özetlenerek otomatik
        üretilmiştir.{" "}
        <strong className="text-zinc-300">Yatırım Danışmanlığı kapsamında değildir</strong>{" "}
        ve alım-satım tavsiyesi olarak yorumlanamaz. Yatırım danışmanlığı; aracı kurumlar,
        portföy yönetim şirketleri ve müşteri arasında imzalanacak sözleşme çerçevesinde
        sunulur. Burada yer alan bilgiler kişisel mali durumunuza uygun olmayabilir. Sadece
        bu bilgilere dayanarak verilecek kararlar beklentilerinizi karşılamayabilir.
      </p>
    </div>
  );
}
