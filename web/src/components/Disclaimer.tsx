/**
 * Yasal uyarı. SPK açısından her rapor sayfasında ve site genelinde görünür olmalı.
 * "compact" varyantı kart altları/footer için, tam varyant rapor sonu için.
 */
export function Disclaimer({ compact = false }: { compact?: boolean }) {
  if (compact) {
    return (
      <p className="text-xs text-zinc-600 leading-relaxed">
        Bu içerik yapay zeka tarafından üretilmiştir ve yatırım tavsiyesi niteliği
        taşımaz. Yatırım kararlarınızı yetkili bir danışmana danışarak veriniz.
      </p>
    );
  }
  return (
    <div className="rounded-2xl border border-amber-900/30 bg-amber-950/10 p-5">
      <p className="text-sm font-medium text-amber-400 mb-2">Yasal Uyarı</p>
      <p className="text-sm text-zinc-400 leading-relaxed">
        Burada yer alan bilgiler yalnızca genel bilgilendirme amaçlıdır ve yapay zeka
        tarafından kamuya açık kaynaklar analiz edilerek otomatik üretilmiştir.{" "}
        <strong className="text-zinc-300">Yatırım Danışmanlığı kapsamında değildir</strong>{" "}
        ve alım-satım tavsiyesi olarak yorumlanamaz. Yatırım danışmanlığı; aracı kurumlar,
        portföy yönetim şirketleri ve müşteri arasında imzalanacak sözleşme çerçevesinde
        sunulur. Burada yer alan yorum ve görüşler kişisel mali durumunuza uygun
        olmayabilir. Sadece bu bilgilere dayanarak verilecek kararlar beklentilerinizi
        karşılamayabilir.
      </p>
    </div>
  );
}
