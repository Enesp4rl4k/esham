/** Fon sayfalarında zorunlu uyarı: yatırım tavsiyesi değildir + veri kaynağı atfı. */
export function FundDisclaimer({ updatedAt }: { updatedAt?: string }) {
  return (
    <div className="rounded-2xl border border-amber-900/30 bg-amber-950/10 p-5" role="note">
      <p className="text-sm font-medium text-amber-400 mb-2">Yatırım tavsiyesi değildir</p>
      <p className="text-sm text-zinc-400 leading-relaxed">
        Bu sayfadaki bilgiler yalnızca genel bilgilendirme amaçlıdır; yatırım danışmanlığı, alım-satım önerisi ya da fon
        tavsiyesi değildir. Fon getirileri geçmiş performanstır ve gelecekteki getirinin garantisi değildir; fon birim
        değeri düşebilir. Yatırım kararlarınızı yetkili bir kuruluştan danışmanlık alarak verin.
      </p>
      <p className="text-xs text-zinc-400 leading-relaxed mt-3">
        Kaynak: TEFAS — Takasbank Fon Bilgilendirme Platformu (fon kurucularının bildirdiği fiyatlar). Getiriler dönem
        başı-dönem sonu fiyat değişimidir; kategori sırası, reel/dolar getirisi, oynaklık, maksimum düşüş ve Sharpe oranı
        Esham tarafından hesaplanır (
        <a href="/yontem" className="underline hover:text-white">
          yöntem
        </a>
        ). Veriler gecikmeli olabilir
        {updatedAt ? ` (son güncelleme: ${new Date(updatedAt).toLocaleDateString("tr-TR")})` : ""}; resmi değerler için
        tefas.gov.tr esastır.
      </p>
    </div>
  );
}
