import Link from "next/link";
import type { Metadata } from "next";
import { SITE_URL } from "@/lib/config";
import { STALE_AFTER_DAYS, ageDays, fmtDate, fmtDateTime, fmtNum, loadMacro } from "@/lib/kap-events";

export const metadata: Metadata = {
  title: "Makro Göstergeler (TCMB verisi)",
  description: "TCMB politika faizi, USD/TRY değişimi ve (anahtarla) TÜFE ile reel efektif kur: her gösterge kaynağı, veri tarihi ve çekiliş zamanıyla.",
  alternates: { canonical: `${SITE_URL}/piyasa/makro-gostergeler` },
};

export default function MacroPage() {
  const doc = loadMacro();
  return (
    <div className="container mx-auto px-6 py-12 max-w-4xl">
      <p className="text-xs text-zinc-400 mb-6">
        <Link href="/" className="hover:text-white">Ana Sayfa</Link> / Piyasa / Makro Göstergeler
      </p>
      <h1 className="text-2xl md:text-3xl font-display font-bold mb-3">Makro Göstergeler</h1>
      <p className="text-sm text-zinc-300 leading-relaxed mb-6 max-w-3xl">
        Gözlenen değerler ve basit oranlar. <strong>Tahmin, skor ya da olasılık yoktur.</strong> Bir değer alınamazsa son geçerli değer kendi tarihiyle
        &quot;güncel değil&quot; işaretiyle gösterilir.
      </p>
      {!doc ? (
        <p className="rounded-xl border border-zinc-800 p-4 text-sm text-zinc-400">Bu bölüm için henüz doğrulanmış veri yok; veri gelene kadar bir şey gösterilmez.</p>
      ) : (
        <>
          <p className="text-xs text-zinc-400 mb-4">
            Son çekiliş: {fmtDateTime(doc.fetchedAt)}.
            {(ageDays(doc.fetchedAt) ?? 0) > STALE_AFTER_DAYS && <span className="text-amber-400"> Güncelleme alınamadı; değerler kendi tarihleriyle son geçerli veridir.</span>}
            {!doc.evdsEnabled && " TÜFE ve reel efektif kur göstergeleri TCMB EVDS anahtarı tanımlanana kadar kapalıdır."}
          </p>
          <div className="grid gap-3 sm:grid-cols-2">
            {doc.indicators.map((i) => (
              <div key={i.id} className="rounded-xl border border-zinc-800 bg-zinc-950/60 p-4">
                <h2 className="text-sm text-zinc-300">{i.label}</h2>
                <p className="text-2xl font-mono font-bold text-white mt-1">
                  {fmtNum(i.value, 2)} <span className="text-sm text-zinc-400">{i.unit}</span>
                </p>
                <p className="text-xs text-zinc-400 mt-2 leading-relaxed">
                  Veri tarihi: {fmtDate(i.asOf)}{i.stale && <span className="text-amber-400"> · güncel değil (son geçerli değer)</span>}.<br />
                  Çekiliş: {fmtDateTime(i.fetchedAt)}.<br />
                  Kaynak:{" "}
                  <a href={i.sourceUrl} target="_blank" rel="noopener noreferrer" className="underline hover:text-white">{i.source}</a>.
                </p>
                <p className="text-xs text-zinc-500 mt-2 leading-relaxed">{i.note}</p>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
