import Link from "next/link";
import { fmtDate, fmtDateTime, fmtInt, fmtNum, type BuybackItem, type DividendItem, type EventDoc } from "@/lib/kap-events";

/**
 * Hisse sayfası: bu hissenin KAP kâr payı ve geri alım bildirimleri. Veri dosyası hiç yoksa (null) bölüm çizilmez;
 * "bildirim yok" yalnızca taranmış bir pencere için, pencere ve tarama tarihiyle söylenir.
 */
export function StockCorporateActionsCard({
  ticker,
  dividends,
  buybacks,
}: {
  ticker: string;
  dividends: EventDoc<DividendItem> | null;
  buybacks: EventDoc<BuybackItem> | null;
}) {
  if (!dividends && !buybacks) return null;
  const div = dividends?.items.find((i) => i.ticker === ticker) ?? null;
  const noDiv = dividends?.noDividend?.find((i) => i.ticker === ticker) ?? null;
  const bbs = (buybacks?.items ?? []).filter((i) => i.ticker === ticker);
  const bb = bbs[0] ?? null;
  const cov = (d: EventDoc<unknown> | null) =>
    d ? `${fmtDate(d.scan.windowFrom)} – ${fmtDate(d.scan.windowTo)} penceresi, tarama ${fmtDateTime(d.fetchedAt)}${d.scan.pending ? `, ${d.scan.pending} bildirim henüz işlenmedi` : ""}` : "";
  return (
    <div className="rounded-2xl border border-zinc-800 bg-zinc-950/80 p-6 space-y-4">
      <h3 className="text-sm font-bold text-white">Kâr payı ve pay geri alımı (KAP bildirimleri)</h3>
      {dividends && (
        <div className="text-xs text-zinc-300 leading-relaxed">
          <p className="text-zinc-400 mb-1">Kâr payı</p>
          {div ? (
            div.installments.map((x, k) => (
              <p key={k}>
                Brüt {fmtNum(x.grossPerShare, 4)} TL, net {fmtNum(x.netPerShare, 4)} TL / pay (stopaj %{fmtNum(x.withholdingPct, 0)}); hak kullanım{" "}
                {fmtDate(x.exDate)}{x.exDateFinal ? "" : " (teklif edilen)"}, ödeme {fmtDate(x.paymentDate)}.{" "}
                <a href={div.sourceUrl} target="_blank" rel="noopener noreferrer" className="underline hover:text-white">KAP #{div.disclosureIndex}</a>{" "}
                (yayın {fmtDate(div.asOf)}).
              </p>
            ))
          ) : noDiv ? (
            <p>
              En yeni bildirimde nakit kâr payı dağıtılmayacağı belirtiliyor.{" "}
              <a href={noDiv.sourceUrl} target="_blank" rel="noopener noreferrer" className="underline hover:text-white">KAP #{noDiv.disclosureIndex}</a> (yayın {fmtDate(noDiv.asOf)}).
            </p>
          ) : (
            <p className="text-zinc-400">Taranan pencerede bu hisse için kâr payı bildirimi bulunamadı ({cov(dividends)}).</p>
          )}
        </div>
      )}
      {buybacks && (
        <div className="text-xs text-zinc-300 leading-relaxed">
          <p className="text-zinc-400 mb-1">Pay geri alımı</p>
          {bb ? (
            <p>
              Son bildirim: {fmtDate(bb.firstTradeDate)}{bb.firstTradeDate !== bb.lastTradeDate ? ` – ${fmtDate(bb.lastTradeDate)}` : ""} arası {fmtInt(bb.totalNominal)} adet,
              hesaplanan ort. fiyat {fmtNum(bb.avgPrice, 2)} TL.{" "}
              {bb.programCumulativeNominal !== null && bb.maxNominal !== null && <>Program: {fmtInt(bb.programCumulativeNominal)} / {fmtInt(bb.maxNominal)} adet. </>}
              <a href={bb.sourceUrl} target="_blank" rel="noopener noreferrer" className="underline hover:text-white">KAP #{bb.disclosureIndex}</a> (yayın {fmtDate(bb.asOf)}); pencerede {bbs.length} bildirim.{" "}
              <Link href="/piyasa/geri-alimlar" className="underline hover:text-white">Tümü</Link>
            </p>
          ) : (
            <p className="text-zinc-400">Taranan pencerede bu hisse için geri alım bildirimi bulunamadı ({cov(buybacks)}).</p>
          )}
        </div>
      )}
    </div>
  );
}
