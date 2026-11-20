"use client";

import { useState } from "react";

type P = Record<string, number | string | null>;

interface Row {
  key: string;
  label: string;
  flow?: boolean; // akım kalemi → YoY sütunu
  bold?: boolean;
  cost?: boolean; // gider kalemi: artış "iyi" değil → YoY nötr renk
  derive?: (p: P) => number | null;
}

const n = (v: unknown): number | null => (typeof v === "number" && Number.isFinite(v) ? v : null);

const SECTIONS: { title: string; rows: Row[] }[] = [
  {
    title: "Gelir Tablosu",
    rows: [
      { key: "revenue", label: "Hasılat", flow: true, bold: true },
      { key: "cogs", label: "Satışların Maliyeti", flow: true, cost: true },
      { key: "gross_profit", label: "Brüt Kâr", flow: true, bold: true },
      { key: "ebitda", label: "FAVÖK", flow: true },
      { key: "ebit", label: "Faaliyet Kârı (FVÖK)", flow: true },
      { key: "interest_expense", label: "Faiz Gideri", flow: true, cost: true },
      { key: "net_income", label: "Net Kâr", flow: true, bold: true },
    ],
  },
  {
    title: "Bilanço",
    rows: [
      { key: "cash", label: "Nakit ve Benzerleri" },
      { key: "receivables", label: "Ticari Alacaklar" },
      { key: "inventory", label: "Stoklar" },
      { key: "current_assets", label: "Dönen Varlıklar" },
      { key: "total_assets", label: "Toplam Varlıklar", bold: true },
      { key: "payables", label: "Ticari Borçlar" },
      { key: "current_liabilities", label: "Kısa Vadeli Yükümlülükler" },
      { key: "total_debt", label: "Finansal Borç" },
      { key: "total_liabilities", label: "Toplam Yükümlülükler" },
      { key: "equity", label: "Özkaynaklar", bold: true },
    ],
  },
  {
    title: "Nakit Akış Tablosu",
    rows: [
      { key: "cfo", label: "İşletme Faaliyetlerinden Nakit", flow: true, bold: true },
      { key: "capex", label: "Yatırım Harcamaları (CAPEX)", flow: true, cost: true },
      {
        key: "fcf",
        label: "Serbest Nakit Akışı",
        flow: true,
        bold: true,
        derive: (p) => (n(p.cfo) !== null && n(p.capex) !== null ? (n(p.cfo) as number) - Math.abs(n(p.capex) as number) : null),
      },
      { key: "dividends_paid", label: "Ödenen Temettü", flow: true },
    ],
  },
];

const nf1 = new Intl.NumberFormat("tr-TR", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
function fmtAmount(v: number | null): string {
  if (v === null) return "—";
  const a = Math.abs(v);
  const s = v < 0 ? "−" : "";
  if (a >= 1e9) return `${s}${nf1.format(a / 1e9)} Mr`;
  if (a >= 1e6) return `${s}${nf1.format(a / 1e6)} Mn`;
  return `${s}${new Intl.NumberFormat("tr-TR").format(Math.round(a))}`;
}
const periodLabel = (d: string, quarterly: boolean) => {
  const [y, m] = d.split("-").map(Number);
  return quarterly ? `${y} Ç${Math.ceil(m / 3)}` : String(y);
};
/** Önceki dönem ≤ 0 ise yüzde değişim anlamsız (işaret değişimi) → "—". */
function yoy(cur: number | null, prev: number | null): number | null {
  if (cur === null || prev === null || prev <= 0) return null;
  return (cur / prev - 1) * 100;
}

export function FinancialStatements({
  annual,
  quarterly,
  currency,
  asOf,
  source = "Yahoo",
}: {
  source?: "KAP" | "Yahoo";
  annual: P[];
  quarterly: P[];
  currency: string;
  asOf: string;
}) {
  const hasQ = quarterly.length > 0;
  const [mode, setMode] = useState<"annual" | "quarterly">(hasQ ? "quarterly" : "annual");
  const quarterlyMode = mode === "quarterly";
  const all = quarterlyMode ? quarterly : annual;
  const cols = all.slice(quarterlyMode ? -6 : -4);
  const lag = quarterlyMode ? 4 : 1;
  const unitNote = currency === "TRY" ? "TL" : `${currency} (tablolar bu para biriminde)`;

  const value = (r: Row, p: P) => (r.derive ? r.derive(p) : n(p[r.key]));

  return (
    <div className="rounded-2xl border border-zinc-800 bg-zinc-950/80 p-5 shadow-xl">
      <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
        <p className="text-xs text-zinc-400">
          Tutarlar {unitNote}; Mn = milyon, Mr = milyar. Son bilanço: {asOf}
        </p>
        <div className="flex gap-1" role="group" aria-label="Dönem türü">
          {(["quarterly", "annual"] as const).map((m) => (
            <button
              key={m}
              type="button"
              aria-pressed={mode === m}
              disabled={m === "quarterly" && !hasQ}
              onClick={() => setMode(m)}
              className={`px-3 py-1.5 rounded-lg text-xs border transition-colors disabled:opacity-40 ${
                mode === m ? "bg-amber-500/15 border-amber-500/50 text-amber-300" : "bg-zinc-900 border-zinc-800 text-zinc-400 hover:text-white"
              }`}
            >
              {m === "quarterly" ? "Çeyreklik" : "Yıllık"}
            </button>
          ))}
        </div>
      </div>

      <div className="space-y-8">
        {SECTIONS.map((sec) => {
          const rows = sec.rows.filter((r) => cols.some((p) => value(r, p) !== null));
          if (rows.length === 0) return null;
          // bu bölümde hiç verisi olmayan dönemleri (ör. Yahoo'da gelir tablosu eksik çeyrek) gizle
          const scols = cols.filter((p) => rows.some((r) => value(r, p) !== null));
          const showYoy = rows.some((r) => r.flow);
          return (
            <div key={sec.title} className="overflow-x-auto">
              <table className="w-full text-xs min-w-[560px]">
                <caption className="text-left text-sm font-semibold text-zinc-200 pb-2">{sec.title}</caption>
                <thead className="text-zinc-400">
                  <tr>
                    <th scope="col" className="text-left font-medium py-2 sticky left-0 bg-zinc-950">
                      Kalem
                    </th>
                    {scols.map((p) => (
                      <th key={String(p.date)} scope="col" className="text-right font-medium py-2 px-2 whitespace-nowrap">
                        {periodLabel(String(p.date), quarterlyMode)}
                      </th>
                    ))}
                    {showYoy && (
                      <th scope="col" className="text-right font-medium py-2 pl-3 whitespace-nowrap" title={quarterlyMode ? "Aynı çeyreğe göre (YoY)" : "Önceki yıla göre"}>
                        {quarterlyMode ? "YoY" : "Yıllık Δ"}
                      </th>
                    )}
                  </tr>
                </thead>
                <tbody className="divide-y divide-zinc-900 font-mono tabular-nums">
                  {rows.map((r) => {
                    const last = scols[scols.length - 1];
                    const lastIdx = all.indexOf(last);
                    const prev = lastIdx - lag >= 0 ? all[lastIdx - lag] : null;
                    const g = r.flow && prev ? yoy(value(r, last), value(r, prev)) : null;
                    return (
                      <tr key={r.key} className="hover:bg-zinc-900/40">
                        <th scope="row" className={`text-left py-2 pr-3 font-sans sticky left-0 bg-zinc-950 ${r.bold ? "font-semibold text-white" : "font-normal text-zinc-400"}`}>
                          {r.label}
                        </th>
                        {scols.map((p) => {
                          const v = value(r, p);
                          return (
                            <td key={String(p.date)} className={`py-2 px-2 text-right ${r.bold ? "text-white" : "text-zinc-300"} ${v !== null && v < 0 ? "text-rose-300" : ""}`}>
                              {fmtAmount(v)}
                            </td>
                          );
                        })}
                        {showYoy && (
                          <td className={`py-2 pl-3 text-right ${g === null ? "text-zinc-400" : r.cost ? "text-zinc-300" : g >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                            {g === null ? "—" : `${g >= 0 ? "+" : "−"}%${nf1.format(Math.abs(g))}`}
                          </td>
                        )}
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          );
        })}
      </div>
      <p className="mt-5 text-xs text-zinc-400 leading-relaxed">
        {source === "KAP" ? "Kaynak: KAP bilançosu (resmî IFRS/XBRL)." : "Kaynak: Yahoo Finance; KAP ile teyit edilmemiştir."} Çeyrek değerleri o çeyreğin tek başına rakamıdır. Tablolar TMS 29 (enflasyon
        muhasebesi) etkisi taşıyabilir, dönemler arası kıyaslarda dikkatli olun. Önceki dönem sıfır ya da negatifse değişim yüzdesi gösterilmez.
      </p>
    </div>
  );
}
