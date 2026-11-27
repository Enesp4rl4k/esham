import { NOTE_GENERIC, NOTE_KAP } from "@/lib/neutral";

/**
 * Yasal uyarı. SPK açısından her rapor sayfasında ve site genelinde görünür olmalı.
 * Kısa not metinleri tek kaynaktan gelir (lib/neutral-rules.json → bot da aynı metni kullanır).
 * "compact" varyantı kart altları/footer için, tam varyant rapor sonu için.
 */
export const KAP_NOTICE = NOTE_KAP;
export const GENERIC_NOTICE = NOTE_GENERIC;

export function SummaryNotice({ kap }: { kap: boolean }) {
  return (
    <p
      role="note"
      className="mb-8 rounded-xl border border-amber-900/30 bg-amber-950/10 px-4 py-3 text-sm text-amber-200/90 leading-relaxed"
    >
      {kap ? NOTE_KAP : NOTE_GENERIC}
    </p>
  );
}

export function Disclaimer({ compact = false }: { compact?: boolean }) {
  if (compact) {
    return <p className="text-xs text-zinc-400 leading-relaxed">{NOTE_GENERIC}</p>;
  }
  return (
    <div className="rounded-2xl border border-amber-900/30 bg-amber-950/10 p-5">
      <p className="text-sm font-medium text-amber-400 mb-2">Yasal Uyarı</p>
      <p className="text-sm text-zinc-400 leading-relaxed">
        {NOTE_GENERIC} Burada yer alan bilgiler yalnızca genel bilgilendirme amaçlıdır.{" "}
        <strong className="text-zinc-300">Yatırım Danışmanlığı kapsamında değildir</strong>{" "}
        ve alım-satım tavsiyesi olarak yorumlanamaz. Yatırım danışmanlığı; aracı kurumlar,
        portföy yönetim şirketleri ve müşteri arasında imzalanacak sözleşme çerçevesinde
        sunulur. Burada yer alan bilgiler kişisel mali durumunuza uygun olmayabilir. Sadece
        bu bilgilere dayanarak verilecek kararlar beklentilerinizi karşılamayabilir.
      </p>
    </div>
  );
}
