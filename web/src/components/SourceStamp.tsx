import { STALE_AFTER_DAYS, ageDays, fmtDate, fmtDateTime, type ScanInfo } from "@/lib/kap-events";

/**
 * Bölüm damgası: kaynak, veri tarihi, çekiliş zamanı, tarama kapsamı, eskilik uyarısı.
 * Kural: kaynaksız ve tarihsiz sayı gösterilmez; eksik/eski durum gizlenmez.
 */
export function SourceStamp({
  source,
  sourceUrl,
  asOf,
  fetchedAt,
  scan,
  unitLabel = "bildirim",
}: {
  source: string;
  sourceUrl: string;
  asOf: string | null;
  fetchedAt: string;
  scan?: ScanInfo;
  unitLabel?: string;
}) {
  const age = ageDays(fetchedAt);
  const stale = age !== null && age > STALE_AFTER_DAYS;
  return (
    <div className="rounded-xl border border-zinc-800 bg-zinc-950/60 p-4 text-xs text-zinc-400 leading-relaxed space-y-1.5 mb-6">
      <p>
        <strong className="text-zinc-200">Kaynak:</strong>{" "}
        <a href={sourceUrl} target="_blank" rel="noopener noreferrer" className="underline hover:text-white">
          {source}
        </a>
        . <strong className="text-zinc-200">En yeni bildirim tarihi:</strong> {fmtDate(asOf)}.{" "}
        <strong className="text-zinc-200">Son çekiliş:</strong> {fmtDateTime(fetchedAt)}.
      </p>
      {scan && (
        <p>
          <strong className="text-zinc-200">Kapsam:</strong> {scan.universeSize} hisseden {scan.tickersWithDisclosure}&apos;inde bu konuda bildirim
          var ({fmtDate(scan.windowFrom)} – {fmtDate(scan.windowTo)} penceresi, {scan.disclosuresListed} {unitLabel} listelendi, {scan.parsed} işlendi).
          {scan.pending > 0 ? (
            <> <span className="text-amber-400">{scan.pending} {unitLabel} henüz işlenmedi (KAP istek bütçesi; sonraki turda devam eder), liste eksik olabilir.</span></>
          ) : (
            <> Tarama tamam{scan.lastCompleteScanAt ? ` (son tam tarama: ${fmtDateTime(scan.lastCompleteScanAt)})` : ""}.</>
          )}
          {Object.keys(scan.skipped).length > 0 && (
            <> Biçimi tanınmadığı için atlanan: {Object.entries(scan.skipped).map(([k, v]) => `${v} × ${k}`).join("; ")}.</>
          )}
        </p>
      )}
      {stale && (
        <p className="text-amber-400">
          Bu veri {age} gün önce çekildi; güncelleme alınamadı. Gösterilen değerler kendi bildirim tarihleriyle son geçerli veridir.
        </p>
      )}
    </div>
  );
}
