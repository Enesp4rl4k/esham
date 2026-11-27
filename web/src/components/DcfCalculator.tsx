"use client";

import { useMemo, useState } from "react";
import { Calculator } from "lucide-react";
import { SCENARIOS, dcf, defaultAssumptions, defaultBase, sensitivity } from "@/lib/dcf";

interface Props {
  ticker: string;
  currency: string; // tabloların para birimi
  fxToTry: number | null; // 1 birim tablo para birimi = kaç TL
  price: number | null; // TL
  shares: number | null;
  netDebt: number | null; // tablo para biriminde
  fcf: number | null; // son 12 ay SNA = CFO − CAPEX
  netIncome: number | null;
}

const nf2 = new Intl.NumberFormat("tr-TR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const nf1 = new Intl.NumberFormat("tr-TR", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
const bn = (v: number) => `${nf1.format(v / 1e9)} Mr`;
const pct = (v: number) => `%${nf1.format(v * 100)}`;

function Slider({ id, label, value, min, max, step, onChange, hint }: {
  id: string; label: string; value: number; min: number; max: number; step: number; onChange: (v: number) => void; hint: string;
}) {
  return (
    <div>
      <div className="flex items-baseline justify-between mb-1">
        <label htmlFor={id} className="text-sm font-medium text-zinc-200">{label}</label>
        <output htmlFor={id} className="font-mono text-base font-bold text-white tabular-nums">%{nf1.format(value)}</output>
      </div>
      <input
        id={id}
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(parseFloat(e.target.value))}
        className="w-full accent-amber-400 h-2 cursor-pointer"
      />
      <p className="text-xs text-zinc-400 mt-1">{hint}</p>
    </div>
  );
}

const r1 = (v: number) => Math.round(v * 1000) / 10; // ondalık → yüzde, kayan nokta artığı olmadan

export function DcfCalculator({ ticker, currency, fxToTry, price, shares, netDebt, fcf, netIncome }: Props) {
  const def = defaultAssumptions(currency);
  const startBase = defaultBase(fcf, netIncome);
  const [baseKey, setBaseKey] = useState<"fcf" | "net_income">(startBase ?? "fcf");
  const [wacc, setWacc] = useState(r1(def.wacc));
  const [g1, setG1] = useState(r1(def.growth1));
  const [gT, setGT] = useState(r1(def.terminalGrowth));
  // Varsayılan çıktı YOK: hesaplama yalnız kullanıcı bir varsayımı değiştirdiğinde ya da açıkça
  // "Varsayımlarımla hesapla" dediğinde gösterilir (statik HTML'de önceden hesaplanmış değer basılmaz).
  const [touched, setTouched] = useState(false);
  const touch = <T,>(fn: (v: T) => void) => (v: T) => { setTouched(true); fn(v); };

  const fx = fxToTry ?? 1;
  const baseVal = baseKey === "fcf" ? fcf : netIncome;

  const inputs = useMemo(
    () =>
      baseVal !== null && shares && netDebt !== null
        ? { baseFcf: baseVal, growth1: g1 / 100, netDebt, shares }
        : null,
    [baseVal, shares, netDebt, g1],
  );
  const result = useMemo(() => (inputs ? dcf({ ...inputs, wacc: wacc / 100, terminalGrowth: gT / 100 }) : null), [inputs, wacc, gT]);
  const sens = useMemo(() => (inputs ? sensitivity(inputs, wacc / 100, gT / 100) : null), [inputs, wacc, gT]);

  if (!inputs || !shares || netDebt === null || fxToTry === null && currency !== "TRY") {
    return <Unavailable ticker={ticker} reason="Bu hisse için hisse adedi, net borç veya nakit akışı verisi eksik." />;
  }
  if (startBase === null) {
    return (
      <Unavailable
        ticker={ticker}
        reason="Son 12 ayda hem serbest nakit akışı hem net kâr negatif. DCF, pozitif bir nakit akışı üzerine kurulduğu için bu şirkette anlamlı sonuç vermez."
      />
    );
  }

  const apply = (s: keyof typeof SCENARIOS) => {
    const sc = SCENARIOS[s];
    setTouched(true);
    setWacc(Math.max(5, r1(def.wacc + sc.dWacc)));
    setG1(r1(def.growth1 + sc.dG1));
    setGT(Math.max(0, r1(def.terminalGrowth + sc.dGT)));
  };
  const reset = () => apply("base");

  const fairTry = result ? result.perShare * fx : null;
  const upside = fairTry !== null && price ? (fairTry / price - 1) * 100 : null;
  const invalid = !result;

  return (
    <div className="rounded-2xl border border-zinc-800 bg-zinc-950/80 p-5 md:p-6 shadow-xl">
      <div className="flex flex-wrap items-center justify-between gap-3 pb-4 border-b border-zinc-800/80 mb-5">
        <div className="flex items-center gap-2">
          <span className="p-1.5 rounded-lg bg-zinc-800/80 text-zinc-200 border border-zinc-700"><Calculator className="w-4 h-4" /></span>
          <h3 className="text-base font-bold text-white tracking-tight">DCF Değerleme · {ticker}</h3>
        </div>
        <div className="flex flex-wrap gap-1.5" role="group" aria-label="Senaryo">
          {(Object.keys(SCENARIOS) as (keyof typeof SCENARIOS)[]).map((k) => (
            <button key={k} type="button" onClick={() => apply(k)}
              className="px-3 py-1.5 rounded-lg text-sm border bg-zinc-900 border-zinc-800 text-zinc-300 hover:text-white hover:border-zinc-600 transition-colors">
              {SCENARIOS[k].label}
            </button>
          ))}
          <button type="button" onClick={reset} className="px-3 py-1.5 text-sm text-zinc-400 hover:text-white">Sıfırla</button>
        </div>
      </div>

      <div className="grid gap-8 lg:grid-cols-2">
        <div className="space-y-6">
          <fieldset>
            <legend className="text-sm font-medium text-zinc-200 mb-2">Baz nakit akışı (son 12 ay)</legend>
            <div className="grid grid-cols-2 gap-2">
              {([
                { key: "fcf", label: "Serbest nakit akışı", v: fcf, note: "İşletme nakit akışı − yatırım harcaması" },
                { key: "net_income", label: "Net kâr", v: netIncome, note: "Ana ortaklık payı" },
              ] as const).map((o) => (
                <button key={o.key} type="button" disabled={o.v === null || o.v <= 0} aria-pressed={baseKey === o.key} onClick={() => touch(setBaseKey)(o.key)}
                  className={`text-left p-3 rounded-xl border transition-colors disabled:opacity-40 disabled:cursor-not-allowed ${
                    baseKey === o.key ? "border-amber-500/60 bg-amber-500/10" : "border-zinc-800 bg-zinc-900 hover:border-zinc-600"}`}>
                  <span className="block text-sm font-medium text-white">{o.label}</span>
                  <span className="block font-mono text-sm text-zinc-300 tabular-nums mt-0.5">{o.v === null ? "—" : `${o.v < 0 ? "−" : ""}${bn(Math.abs(o.v) * fx)} ₺`}</span>
                  <span className="block text-xs text-zinc-400 mt-0.5">{o.v !== null && o.v <= 0 ? "Negatif: kullanılamaz" : o.note}</span>
                </button>
              ))}
            </div>
          </fieldset>

          <Slider id="dcf-wacc" label="İskonto oranı (reel)" value={wacc} min={5} max={30} step={0.5} onChange={touch(setWacc)}
            hint={`Nakit akışlarının bugünkü değere indirildiği reel oran. Varsayılan %${r1(def.wacc)} (${currency === "TRY" ? "TL" : currency}).`} />
          <Slider id="dcf-g1" label="1. yıl büyümesi (reel)" value={g1} min={-5} max={25} step={0.5} onChange={touch(setG1)}
            hint="Nakit akışının ilk yıl reel büyümesi; 5. yılda uç büyümeye doğrusal iner." />
          <Slider id="dcf-gt" label="Uç büyüme (reel)" value={gT} min={0} max={8} step={0.5} onChange={touch(setGT)}
            hint="5. yıldan sonra sonsuza dek varsayılan reel büyüme. İskonto oranından küçük olmalı." />
        </div>

        <div>
          {!touched ? (
            <div className="rounded-xl border border-zinc-800 bg-zinc-900/70 p-5 text-sm text-zinc-300 space-y-3">
              <p>
                Bu hesaplayıcı yalnızca <b>sizin girdiğiniz varsayımlarla</b> çalışır; Esham bir değer veya hedef
                göstermez. Başlamak için soldaki varsayımlardan birini değiştirin.
              </p>
              <button type="button" onClick={() => setTouched(true)}
                className="px-3 py-1.5 rounded-lg text-sm border bg-zinc-900 border-zinc-700 text-zinc-200 hover:text-white hover:border-zinc-500">
                Varsayımlarımla hesapla
              </button>
            </div>
          ) : invalid ? (
            <div className="rounded-xl border border-rose-500/30 bg-rose-500/10 p-5 text-sm text-rose-200">
              İskonto oranı uç büyümeden büyük olmalı. Kaydırıcıları ayarlayın.
            </div>
          ) : (
            <>
              <div className="rounded-xl border border-zinc-800 bg-zinc-900/70 p-5">
                <p className="text-sm text-zinc-300">Girdiğiniz varsayımlarla hisse başına model değeri</p>
                <p className="font-mono text-4xl font-bold text-white tabular-nums mt-1">{nf2.format(fairTry as number)} ₺</p>
                <div className="flex flex-wrap gap-x-6 gap-y-1 mt-3 text-sm">
                  <span className="text-zinc-300">Güncel fiyat: <b className="font-mono text-white tabular-nums">{price ? `${nf2.format(price)} ₺` : "—"}</b></span>
                  {upside !== null && (
                    <span className="text-zinc-300">
                      Model farkı: <b className="font-mono tabular-nums">{upside >= 0 ? "+" : "−"}%{nf1.format(Math.abs(upside))}</b>
                    </span>
                  )}
                </div>
              </div>

              <table className="w-full text-sm mt-5">
                <caption className="sr-only">Firma değerinden özkaynak değerine köprü</caption>
                <tbody className="divide-y divide-zinc-900 font-mono tabular-nums">
                  {([
                    ["5 yıllık nakit akışlarının bugünkü değeri", `${bn(result.pvFcf * fx)} ₺`],
                    ["Uç değerin bugünkü değeri", `${bn(result.pvTerminal * fx)} ₺`],
                    ["Firma değeri", `${bn(result.enterpriseValue * fx)} ₺`],
                    [netDebt >= 0 ? "(−) Net borç" : "(+) Net nakit", `${bn(Math.abs(netDebt) * fx)} ₺`],
                    ["Özkaynak değeri", `${bn(result.equityValue * fx)} ₺`],
                    ["Hisse adedi", `${nf1.format(shares / 1e6)} Mn`],
                  ] as const).map(([k, v], i) => (
                    <tr key={k} className={i === 2 || i === 4 ? "font-bold text-white" : "text-zinc-300"}>
                      <th scope="row" className="py-2 pr-3 text-left font-sans font-normal">{k}</th>
                      <td className="py-2 text-right">{v}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {result.terminalShare > 0.75 && (
                <p className="mt-3 text-sm text-zinc-200 rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-2">
                  Firma değerinin {pct(result.terminalShare)}&apos;i uç değerden geliyor; sonuç uzun vade varsayımlarına çok duyarlı.
                </p>
              )}
            </>
          )}
        </div>
      </div>

      {touched && result && (
        <div className="grid gap-8 lg:grid-cols-2 mt-8 pt-6 border-t border-zinc-800/80">
          <div className="overflow-x-auto">
            <table className="w-full text-sm min-w-[360px]">
              <caption className="text-left text-sm font-semibold text-zinc-200 pb-2">Nakit akışı projeksiyonu (reel, milyar ₺)</caption>
              <thead className="text-zinc-400">
                <tr>
                  <th scope="col" className="text-left font-medium py-2">Yıl</th>
                  <th scope="col" className="text-right font-medium py-2">Büyüme</th>
                  <th scope="col" className="text-right font-medium py-2">Nakit akışı</th>
                  <th scope="col" className="text-right font-medium py-2">Bugünkü değer</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-900 font-mono tabular-nums text-zinc-300">
                {result.projections.map((p) => (
                  <tr key={p.year}>
                    <th scope="row" className="py-2 text-left font-sans font-normal">{p.year}</th>
                    <td className="py-2 text-right">{pct(p.growth)}</td>
                    <td className="py-2 text-right">{nf1.format((p.fcf * fx) / 1e9)}</td>
                    <td className="py-2 text-right">{nf1.format((p.pv * fx) / 1e9)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {sens && (
            <div className="overflow-x-auto">
              <table className="w-full text-sm min-w-[360px]">
                <caption className="text-left text-sm font-semibold text-zinc-200 pb-2">
                  Duyarlılık: hisse başı değer (₺) — iskonto oranı × uç büyüme
                </caption>
                <thead className="text-zinc-400">
                  <tr>
                    <th scope="col" className="text-left font-medium py-2">İskonto \ Uç büy.</th>
                    {sens.growths.map((g) => (
                      <th key={g} scope="col" className="text-right font-medium py-2">{pct(g)}</th>
                    ))}
                  </tr>
                </thead>
                <tbody className="font-mono tabular-nums">
                  {sens.waccs.map((w, i) => (
                    <tr key={w} className="border-t border-zinc-900">
                      <th scope="row" className="py-2 text-left font-sans font-medium text-zinc-300">{pct(w)}</th>
                      {sens.values[i].map((v, j) => {
                        const t = v === null ? null : v * fx;
                        const center = i === 2 && j === 2;
                        const tone = t === null || !price ? "text-zinc-500" : t >= price ? "text-emerald-400" : "text-rose-300";
                        return (
                          <td key={j} className={`py-2 text-right ${tone} ${center ? "font-bold bg-zinc-900 rounded" : ""}`}>
                            {t === null ? (
                              "—"
                            ) : (
                              <>
                                {nf2.format(t)}
                                {price ? <span aria-hidden="true" className="ml-1 text-[0.75em]">{t >= price ? "▲" : "▼"}</span> : null}
                              </>
                            )}
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
              <p className="text-xs text-zinc-400 mt-2">▲ güncel fiyatın üstü, ▼ altı. Ortadaki hücre mevcut varsayımlar.</p>
            </div>
          )}
        </div>
      )}

      <ul className="mt-6 space-y-1 text-xs text-zinc-400 border-t border-zinc-800/80 pt-4 leading-relaxed">
        <li>• Model <b>reel</b> terimlerle çalışır: nakit akışı bugünkü alım gücüyle, iskonto oranı enflasyondan arındırılmış. Nominal TL varsayımı gerekmez.</li>
        <li>• Baz nakit akışı son 12 aylık bilançodan alınır; kira ödemeleri ve azınlık payları ayrıca modellenmez. Dönemsel dalgalanması yüksek şirketlerde sonuç yanıltıcı olabilir.</li>
        <li>• Basit bir eğitim modelidir; varsayımlar sizin. Yatırım tavsiyesi değildir.</li>
      </ul>
    </div>
  );
}

function Unavailable({ ticker, reason }: { ticker: string; reason: string }) {
  return (
    <div className="rounded-2xl border border-zinc-800 bg-zinc-950/80 p-6">
      <h3 className="text-base font-bold text-white mb-2">DCF Değerleme · {ticker}</h3>
      <p className="text-sm text-zinc-300">{reason}</p>
    </div>
  );
}
