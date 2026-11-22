import { Calculator } from "lucide-react";
import type { QuarterPoint } from "./RatioTrendCharts";

export interface StockRatiosData {
  ticker: string;
  sector: string;
  financial: boolean;
  as_of: string;
  /** Bu dosyanın botça son başarılı üretildiği an (ISO); fiyat/çarpanların tarihi */
  updated_at?: string;
  basis: "TTM" | "yillik";
  currency: string;
  ratios: Record<string, number | null>;
  ttm: Record<string, number | null>;
  sector_median: Record<string, number>;
  quality: string[];
  /** Finansal tabloların kaynağı; eski JSON'larda yok → Yahoo */
  data_source?: "KAP" | "Yahoo";
  quarterly_history?: QuarterPoint[];
  price?: number | null;
  fx_to_try?: number | null;
  annual?: Record<string, number | string | null>[];
  quarterly?: Record<string, number | string | null>[];
}

type Unit = "x" | "%" | "gün";
// better: "low" → düşük iyi (çarpan, borç), "high" → yüksek iyi (marj, getiri), undefined → renksiz
type Row = { key: string; label: string; unit: Unit; better?: "low" | "high"; hint: string };

const GROUPS: { title: string; rows: Row[]; skipForFinancial?: boolean }[] = [
  {
    title: "Değerleme",
    rows: [
      { key: "pe", label: "F/K", unit: "x", better: "low", hint: "Piyasa değeri / son 12 ay net kâr" },
      { key: "pb", label: "PD/DD", unit: "x", better: "low", hint: "Piyasa değeri / özkaynak" },
      { key: "ev_ebitda", label: "FD/FAVÖK", unit: "x", better: "low", hint: "Firma değeri / son 12 ay FAVÖK" },
      { key: "ev_sales", label: "FD/Satışlar", unit: "x", hint: "Firma değeri / son 12 ay hasılat" },
      { key: "dividend_yield", label: "Temettü Verimi", unit: "%", better: "high", hint: "Son 12 ay brüt temettü / fiyat" },
      { key: "fcf_yield", label: "SNA Verimi", unit: "%", better: "high", hint: "Serbest nakit akışı / piyasa değeri" },
    ],
  },
  {
    title: "Karlılık",
    rows: [
      { key: "gross_margin", label: "Brüt Marj", unit: "%", better: "high", hint: "Brüt kâr / hasılat", },
      { key: "ebitda_margin", label: "FAVÖK Marjı", unit: "%", better: "high", hint: "FAVÖK / hasılat" },
      { key: "net_margin", label: "Net Marj", unit: "%", better: "high", hint: "Net kâr / hasılat" },
      { key: "roe", label: "ROE", unit: "%", better: "high", hint: "Net kâr / özkaynak" },
      { key: "roa", label: "ROA", unit: "%", better: "high", hint: "Net kâr / toplam aktif" },
      { key: "roic", label: "ROIC", unit: "%", better: "high", hint: "FVÖK×(1−%25 vergi) / yatırılan sermaye" },
    ],
  },
  {
    title: "Borçluluk & Likidite",
    skipForFinancial: true,
    rows: [
      { key: "net_debt_ebitda", label: "Net Borç/FAVÖK", unit: "x", better: "low", hint: "(Borç − nakit) / FAVÖK" },
      { key: "debt_to_equity", label: "Borç/Özkaynak", unit: "x", better: "low", hint: "Toplam finansal borç / özkaynak" },
      { key: "interest_coverage", label: "Faiz Karşılama", unit: "x", better: "high", hint: "FVÖK / faiz gideri" },
      { key: "current_ratio", label: "Cari Oran", unit: "x", better: "high", hint: "Dönen varlık / kısa vadeli yükümlülük" },
      { key: "quick_ratio", label: "Asit-Test", unit: "x", better: "high", hint: "(Dönen varlık − stok) / KV yükümlülük" },
    ],
  },
  {
    title: "Verimlilik",
    skipForFinancial: true,
    rows: [
      { key: "dso_days", label: "Alacak Tahsil Süresi", unit: "gün", hint: "Alacaklar / hasılat × 365" },
      { key: "dio_days", label: "Stok Devir Süresi", unit: "gün", hint: "Stok / satış maliyeti × 365" },
      { key: "dpo_days", label: "Borç Ödeme Süresi", unit: "gün", hint: "Ticari borç / satış maliyeti × 365" },
      { key: "cash_cycle_days", label: "Nakit Döngüsü", unit: "gün", hint: "Tahsil + stok − ödeme süresi" },
      { key: "asset_turnover", label: "Aktif Devir Hızı", unit: "x", hint: "Hasılat / toplam aktif" },
    ],
  },
];

const QUALITY_NOTES: Record<string, string> = {
  bilanco_eski: "Son bilanço 200 günden eski.",
  ttm_yok_yillik_kullanildi: "Çeyreklik veri yetersiz; son yıllık bilanço kullanıldı.",
  ceyreklik_toplam_yillikle_uyusmuyor: "Çeyreklik toplam yıllık rakamla uyuşmuyor; veriyi doğrulayın.",
  carpan_uc_deger: "Bazı çarpanlar olağandışı düşük; veriyi KAP bilançosuyla doğrulayın.",
  temettu_verimi_uc: "Temettü verimi olağandışı yüksek; temettü verisi hatalı veya tek seferlik olabilir.",
  roe_uc_deger: "ROE olağandışı uç değerde (özkaynak çok küçük veya negatife yakın).",
  pe_yahoo_farkli: "F/K, Yahoo Finance'in kendi değerinden belirgin farklı; kâr tanımı farkı veya veri hatası olabilir.",
  favok_yaklasik_ebit: "FAVÖK, amortisman verisi olmadığından FVÖK ile yaklaşıklanmıştır.",
  kap_yetersiz_donem: "KAP verisi yetersiz (4 çeyrekten az); Yahoo Finance kullanıldı.",
  kap_eski: "KAP verisi Yahoo'dan eski; Yahoo Finance kullanıldı.",
  kap_eksik_kalem: "KAP bilançosunda hasılat/net kâr eksik; Yahoo Finance kullanıldı.",
  kap_hasilat_farki_buyuk: "KAP ile Yahoo hasılatı arasında büyük fark var (eşleme şüphesi); Yahoo Finance kullanıldı.",
  enflasyon_muhasebesi_tms29_karsilastirma_dikkat:
    "Tablolar TMS 29 (enflasyon muhasebesi) etkisi taşıyabilir; geçmiş dönem kıyasları dikkatle yorumlanmalıdır.",
};

const nf = new Intl.NumberFormat("tr-TR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

function fmt(v: number | null | undefined, unit: Unit): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  if (unit === "gün") return `${Math.round(v)} gün`;
  return unit === "%" ? `%${nf.format(v)}` : `${nf.format(v)}x`;
}

/** Medyana göre konum: renk değil glif + ekran okuyucu metni (yeşil/kırmızı yalnızca fiyat yönü içindir). */
function position(v: number | null | undefined, median: number | undefined) {
  if (v === null || v === undefined || median === undefined) return null;
  if (Math.abs(v - median) < 1e-9) return { glyph: "=", text: "medyana eşit" };
  return v < median ? { glyph: "▼", text: "medyanın altında" } : { glyph: "▲", text: "medyanın üstünde" };
}

export function RatiosCard({ data }: { data: StockRatiosData }) {
  const asOf = new Date(data.as_of).toLocaleDateString("tr-TR", { year: "numeric", month: "long" });
  const lossMaking = data.ratios.pe === null && (data.ttm.net_income ?? 0) <= 0 && data.ttm.net_income !== null;

  return (
    <div className="rounded-2xl border border-zinc-800 bg-zinc-950/80 p-6 shadow-xl">
      <div className="flex flex-wrap items-center justify-between gap-2 pb-4 border-b border-zinc-800/80 mb-5">
        <div className="flex items-center gap-2">
          <span className="p-1.5 rounded-lg bg-zinc-800/80 text-zinc-200 border border-zinc-700">
            <Calculator className="w-4 h-4" />
          </span>
          <h3 className="text-sm font-bold text-white tracking-tight">Finansal Oranlar</h3>
        </div>
        <span className="text-xs font-mono text-zinc-400 bg-zinc-900 px-2 py-0.5 rounded border border-zinc-800">
          {data.basis === "TTM" ? "Son 12 ay" : "Yıllık"} · {asOf} · tablolar {data.currency}
        </span>
      </div>

      {data.updated_at && (
        <p className="mb-4 text-xs text-zinc-400">
          Fiyat ve çarpanlar {new Date(data.updated_at).toLocaleDateString("tr-TR")} tarihinde hesaplandı (fiyat: Yahoo Finance;
          finansal tablolar: {data.data_source === "KAP" ? "KAP" : "Yahoo Finance"}). Bir güncelleme alınamazsa son
          başarılı hesaplamanın tarihi burada kalır.
        </p>
      )}

      {lossMaking && (
        <p className="mb-4 text-sm text-zinc-200 rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-2">
          Son 12 ayda net zarar var; F/K anlamsız olduğundan gösterilmiyor.
        </p>
      )}

      <div className="grid gap-6 md:grid-cols-2">
        {GROUPS.filter((g) => !(data.financial && g.skipForFinancial)).map((g) => (
          <section key={g.title}>
            <h4 className="text-sm font-semibold text-zinc-200 mb-2">{g.title}</h4>
            <table className="w-full text-xs">
              <thead className="sr-only">
                <tr>
                  <th>Oran</th>
                  <th>Değer</th>
                  <th>Sektör medyanı</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-900">
                {g.rows
                  .filter((r) => !data.financial || r.key in data.ratios)
                  .map((r) => {
                    const v = data.ratios[r.key];
                    const med = data.sector_median[r.key];
                    return (
                      <tr key={r.key} title={r.hint}>
                        <td className="py-2 text-zinc-400">{r.label}</td>
                        <td className="py-2 text-right font-mono font-semibold tabular-nums text-zinc-100">
                          {fmt(v, r.unit)}
                        </td>
                        <td className="py-2 pl-3 text-right font-mono text-xs text-zinc-400 tabular-nums w-24">
                          {med !== undefined ? (
                            <>
                              {position(v, med) && (
                                <>
                                  <span aria-hidden="true" className="mr-1">{position(v, med)!.glyph}</span>
                                  <span className="sr-only">{position(v, med)!.text}, </span>
                                </>
                              )}
                              med. {fmt(med, r.unit)}
                            </>
                          ) : (
                            ""
                          )}
                        </td>
                      </tr>
                    );
                  })}
              </tbody>
            </table>
          </section>
        ))}
      </div>

      <ul className="mt-5 space-y-1 text-xs text-zinc-400 border-t border-zinc-800/80 pt-4">
        {data.quality.map((q) => QUALITY_NOTES[q] && <li key={q}>• {QUALITY_NOTES[q]}</li>)}
        <li>
          • Kaynak:{" "}
          {data.data_source === "KAP"
            ? "KAP bilançosu (resmî IFRS/XBRL); fiyat, piyasa değeri ve temettü Yahoo Finance."
            : "Yahoo Finance bilanço verisi, KAP ile teyit edilmemiştir."}{" "}
          Oranlar Esham tarafından hesaplanır. Yatırım tavsiyesi değildir.
        </li>
      </ul>
    </div>
  );
}
