"use client";

import React, { useState, useMemo } from "react";
import {
  TrendingUp,
  TrendingDown,
  Sliders,
  RotateCcw,
  ShieldCheck,
  Zap,
  Layers,
  ChevronRight,
  Info,
  DollarSign,
  BarChart3,
  Scale,
} from "lucide-react";

interface DcfData {
  ticker: string;
  sirket: string;
  para_birimi: string;
  finansal_para_birimi: string;
  /** USD raporlayanlarda TL çevirimi için botun kullandığı canlı USD/TRY; yoksa TL değer gösterilmez. */
  usd_try?: number | null;
  guncel_fiyat: number;
  hisse_adedi: number;
  baz_fcf: number;
  baz_fcf_fmt: string;
  varsayimlar: {
    wacc_aosm: number;
    buyume_orani: number;
    uc_buyume_orani: number;
    tahmin_yili: number;
  };
  projeksiyonlar: Array<{
    yil: number;
    fcf: number;
    pv_fcf: number;
    buyume: number;
  }>;
  indirgenmis_nakit_akislari_toplami: number;
  uc_deger: number;
  indirgenmis_uc_deger: number;
  firma_degeri_ev: number;
  nakit_ve_benzerleri: number;
  toplam_borc: number;
  net_borc: number;
  ozsermaye_degeri: number;
  hisse_basina_adil_deger: number;
  hisse_basina_adil_deger_try: number;
  getiri_potansiyeli_yuzde: number;
  degerlendirme: string;
  duyarlilik_matrisi: {
    wacc_rates: number[];
    terminal_rates: number[];
    rows: Array<{
      wacc: number;
      values: number[];
    }>;
  };
  senaryolar: {
    bear: { ad: string; wacc: number; buyume: number; adil_deger_try: number; potansiyel_yuzde: number };
    base: { ad: string; wacc: number; buyume: number; adil_deger_try: number; potansiyel_yuzde: number };
    bull: { ad: string; wacc: number; buyume: number; adil_deger_try: number; potansiyel_yuzde: number };
  };
}

interface DcfTerminalCardProps {
  dcf: DcfData;
}

export function DcfTerminalCard({ dcf }: DcfTerminalCardProps) {
  // USD raporlayan şirkette gerçek USD/TRY yoksa sabit kurla TL adil değer üretmeyiz.
  if (dcf.finansal_para_birimi === "USD" && !(typeof dcf.usd_try === "number" && dcf.usd_try > 0)) {
    return (
      <div className="rounded-2xl border border-zinc-800 bg-zinc-950/80 p-6 text-xs text-zinc-400">
        Veri yok: bu şirketin DCF değerlemesi USD cinsindendir ve TL çevirimi için doğrulanmış USD/TRY kuru
        bulunmuyor; eski veya sabit kurla hesaplanmış değer gösterilmez.
      </div>
    );
  }
  return <DcfTerminalCardInner dcf={dcf} />;
}

function DcfTerminalCardInner({ dcf }: DcfTerminalCardProps) {
  const isUsd = dcf.finansal_para_birimi === "USD";
  const fxMultiplier = isUsd ? (dcf.usd_try as number) : 1.0;

  // Initial defaults
  const defaultWacc = dcf.varsayimlar.wacc_aosm * 100;
  const defaultGrowth = dcf.varsayimlar.buyume_orani * 100;
  const defaultTg = dcf.varsayimlar.uc_buyume_orani * 100;

  const [wacc, setWacc] = useState<number>(defaultWacc);
  const [growthRate, setGrowthRate] = useState<number>(defaultGrowth);
  const [terminalGrowth, setTerminalGrowth] = useState<number>(defaultTg);
  const [activeScenario, setActiveScenario] = useState<"base" | "bear" | "bull" | "custom">("base");
  const [activeTab, setActiveTab] = useState<"model" | "sensitivity" | "bridge">("model");

  // Re-calculate model dynamically when sliders move
  const calculation = useMemo(() => {
    const wRate = wacc / 100;
    const gRate = growthRate / 100;
    let tgRate = terminalGrowth / 100;

    if (wRate <= tgRate) {
      tgRate = wRate - 0.02;
    }

    const projectionYears = 5;
    let pvFcfs = 0;
    let curFcf = dcf.baz_fcf;
    const projections = [];

    for (let y = 1; y <= projectionYears; y++) {
      const decayFactor = Math.max(0.5, 1.0 - (y - 1) * 0.1);
      const effectiveGrowth = Math.max(tgRate, gRate * decayFactor);
      curFcf *= 1 + effectiveGrowth;
      const pvStep = curFcf / Math.pow(1 + wRate, y);
      pvFcfs += pvStep;
      projections.push({
        year: y,
        fcf: curFcf,
        pvFcf: pvStep,
        growth: effectiveGrowth,
      });
    }

    const terminalVal = (curFcf * (1 + tgRate)) / (wRate - tgRate);
    const pvTerminalVal = terminalVal / Math.pow(1 + wRate, projectionYears);
    const enterpriseValue = pvFcfs + pvTerminalVal;
    const netDebt = dcf.toplam_borc - dcf.nakit_ve_benzerleri;
    const equityValue = enterpriseValue - netDebt;
    const fairValueShare = dcf.hisse_adedi > 0 ? equityValue / dcf.hisse_adedi : 0;
    const fairValueTry = fairValueShare * fxMultiplier;
    const upsidePct =
      dcf.guncel_fiyat > 0
        ? ((fairValueTry - dcf.guncel_fiyat) / dcf.guncel_fiyat) * 100
        : 0;

    // Generate dynamic 5x5 sensitivity matrix
    const wStep = isUsd ? 0.015 : 0.02;
    const tgStep = isUsd ? 0.008 : 0.015;
    const wList = [
      wRate - 2 * wStep,
      wRate - wStep,
      wRate,
      wRate + wStep,
      wRate + 2 * wStep,
    ];
    const tgList = [
      tgRate - 2 * tgStep,
      tgRate - tgStep,
      tgRate,
      tgRate + tgStep,
      tgRate + 2 * tgStep,
    ];

    const sensitivityRows = wList.map((wVal) => {
      const values = tgList.map((tgVal) => {
        let effTg = tgVal;
        if (wVal <= effTg) effTg = wVal - 0.015;
        let pF = 0;
        let cF = dcf.baz_fcf;
        for (let y = 1; y <= 5; y++) {
          const decay = Math.max(0.5, 1.0 - (y - 1) * 0.1);
          cF *= 1 + Math.max(effTg, gRate * decay);
          pF += cF / Math.pow(1 + wVal, y);
        }
        const tVal = (cF * (1 + effTg)) / (wVal - effTg);
        const pvTVal = tVal / Math.pow(1 + wVal, 5);
        const ev = pF + pvTVal;
        const eq = ev - netDebt;
        const fv = dcf.hisse_adedi > 0 ? eq / dcf.hisse_adedi : 0;
        return fv * fxMultiplier;
      });
      return { wacc: wVal, values };
    });

    return {
      pvFcfs,
      terminalVal,
      pvTerminalVal,
      enterpriseValue,
      netDebt,
      equityValue,
      fairValueTry,
      upsidePct,
      projections,
      sensitivity: {
        wList,
        tgList,
        rows: sensitivityRows,
      },
    };
  }, [wacc, growthRate, terminalGrowth, dcf, isUsd, fxMultiplier]);

  const handleScenarioSelect = (scenario: "bear" | "base" | "bull") => {
    setActiveScenario(scenario);
    if (scenario === "base") {
      setWacc(defaultWacc);
      setGrowthRate(defaultGrowth);
      setTerminalGrowth(defaultTg);
    } else if (scenario === "bear") {
      setWacc(Math.min(40, defaultWacc + 2.5));
      setGrowthRate(Math.max(5, defaultGrowth * 0.7));
      setTerminalGrowth(Math.max(2, defaultTg - 1.0));
    } else if (scenario === "bull") {
      setWacc(Math.max(8, defaultWacc - 2.5));
      setGrowthRate(defaultGrowth * 1.3);
      setTerminalGrowth(defaultTg + 1.0);
    }
  };

  const isUndervalued = calculation.upsidePct >= 0;
  const isStrong = calculation.upsidePct >= 30;

  const formatMoney = (val: number) => {
    const sign = val < 0 ? "-" : "";
    const abs = Math.abs(val);
    if (abs >= 1_000_000_000) {
      return `${sign}${(abs / 1_000_000_000).toFixed(2)} Milyar ${dcf.finansal_para_birimi}`;
    }
    if (abs >= 1_000_000) {
      return `${sign}${(abs / 1_000_000).toFixed(1)} Milyon ${dcf.finansal_para_birimi}`;
    }
    return `${sign}${abs.toLocaleString("tr-TR", { maximumFractionDigits: 0 })} ${dcf.finansal_para_birimi}`;
  };

  return (
    <div className="rounded-2xl border border-zinc-800 bg-zinc-950/80 p-6 md:p-8 backdrop-blur-sm relative overflow-hidden shadow-xl">
      {/* Background Glow */}
      <div
        className={`absolute -top-32 -right-32 w-80 h-80 rounded-full blur-[100px] pointer-events-none opacity-20 ${
          isStrong ? "bg-emerald-500" : isUndervalued ? "bg-cyan-500" : "bg-rose-500"
        }`}
      />

      {/* Top Header */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-6 pb-6 border-b border-zinc-800/80">
        <div>
          <div className="flex items-center gap-2.5 mb-2">
            <span className="p-1.5 rounded-lg bg-cyan-500/10 text-cyan-400 border border-cyan-500/20">
              <Scale className="w-4 h-4" />
            </span>
            <span className="text-xs font-mono font-bold tracking-wider uppercase text-cyan-400">
              İndirgenmiş Nakit Akışı (İNA / DCF) Değerleme Modeli
            </span>
            <span className="text-xs font-semibold tracking-wider uppercase px-2 py-0.5 rounded bg-zinc-800 text-zinc-400 border border-zinc-700">
              5 Yıllık Projeksiyon
            </span>
          </div>
          <h3 className="text-lg font-bold text-white tracking-tight">
            ${dcf.ticker} Adil Hisse Değeri & İskonto Analizi
          </h3>
          <p className="text-xs text-zinc-400 mt-1">
            Finansal Raporlama:{" "}
            <span className="text-zinc-200 font-mono font-medium">
              {dcf.finansal_para_birimi}
            </span>{" "}
            {isUsd && (
              <span className="text-zinc-400 text-xs">
                (USD/TRY: {fxMultiplier.toFixed(2)} ile dönüştürülmüştür)
              </span>
            )}
            {" • "}
            Baz Serbest Nakit Akımı (FCF):{" "}
            <span className="text-zinc-200 font-mono font-medium">{dcf.baz_fcf_fmt}</span>
          </p>
        </div>

        {/* Big Target Valuation Badge */}
        <div className="flex items-center gap-4 bg-zinc-900/90 border border-zinc-800 rounded-xl p-4 self-start lg:self-auto min-w-[260px]">
          <div>
            <span className="text-xs uppercase font-bold tracking-wider text-zinc-400 block">
              Model Hedef Değeri
            </span>
            <div className="flex items-baseline gap-2 mt-0.5">
              <span className="text-2xl md:text-3xl font-mono font-extrabold text-white">
                {calculation.fairValueTry.toFixed(2)} ₺
              </span>
              <span className="text-xs text-zinc-400 font-mono">
                / {dcf.guncel_fiyat.toFixed(2)} ₺
              </span>
            </div>
          </div>
          <div
            className={`ml-auto px-3 py-1.5 rounded-lg text-xs font-mono font-bold flex items-center gap-1.5 border ${
              isUndervalued
                ? "bg-emerald-500/15 text-emerald-400 border-emerald-500/30"
                : "bg-rose-500/15 text-rose-400 border-rose-500/30"
            }`}
          >
            {isUndervalued ? (
              <TrendingUp className="w-3.5 h-3.5" />
            ) : (
              <TrendingDown className="w-3.5 h-3.5" />
            )}
            {calculation.upsidePct >= 0 ? "+" : ""}
            {calculation.upsidePct.toFixed(1)}%
          </div>
        </div>
      </div>

      {/* Scenario Presets & Mode Tabs */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 py-4 border-b border-zinc-800/60">
        <div className="flex items-center gap-2">
          <span className="text-xs text-zinc-400 font-medium mr-1">Senaryo:</span>
          {(["bear", "base", "bull"] as const).map((sc) => (
            <button
              key={sc}
              onClick={() => handleScenarioSelect(sc)}
              className={`px-3 py-1 rounded-lg text-xs font-semibold transition-all ${
                activeScenario === sc
                  ? sc === "bull"
                    ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/40"
                    : sc === "bear"
                    ? "bg-rose-500/20 text-rose-300 border border-rose-500/40"
                    : "bg-cyan-500/20 text-cyan-300 border border-cyan-500/40"
                  : "bg-zinc-900 text-zinc-400 hover:text-white border border-zinc-800"
              }`}
            >
              {sc === "bear" ? "Ayı (Kötümser)" : sc === "base" ? "Baz Senaryo" : "Boğa (İyimser)"}
            </button>
          ))}
          {activeScenario === "custom" && (
            <span className="px-2.5 py-1 rounded text-xs font-mono bg-amber-500/15 text-amber-300 border border-amber-500/30">
              Özel Ayar
            </span>
          )}
        </div>

        {/* Tab switchers */}
        <div className="flex items-center gap-1 bg-zinc-900 p-1 rounded-lg border border-zinc-800 self-start sm:self-auto">
          <button
            onClick={() => setActiveTab("model")}
            className={`px-3 py-1 rounded-md text-xs font-medium transition-colors ${
              activeTab === "model" ? "bg-zinc-800 text-white" : "text-zinc-400 hover:text-white"
            }`}
          >
            Model Detayları
          </button>
          <button
            onClick={() => setActiveTab("sensitivity")}
            className={`px-3 py-1 rounded-md text-xs font-medium transition-colors ${
              activeTab === "sensitivity" ? "bg-zinc-800 text-white" : "text-zinc-400 hover:text-white"
            }`}
          >
            Duyarlılık Isı Haritası
          </button>
          <button
            onClick={() => setActiveTab("bridge")}
            className={`px-3 py-1 rounded-md text-xs font-medium transition-colors ${
              activeTab === "bridge" ? "bg-zinc-800 text-white" : "text-zinc-400 hover:text-white"
            }`}
          >
            Özsermaye Köprüsü
          </button>
        </div>
      </div>

      {/* Interactive Sliders Section */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 py-5 bg-zinc-900/30 rounded-xl p-4 my-5 border border-zinc-800/50 text-xs">
        {/* WACC Slider */}
        <div>
          <div className="flex justify-between items-center mb-1.5">
            <span className="font-semibold text-zinc-300 flex items-center gap-1">
              <Sliders className="w-3.5 h-3.5 text-cyan-400" />
              AOSM (İskonto Oranı - WACC):
            </span>
            <span className="font-mono font-bold text-cyan-400 bg-cyan-500/10 px-2 py-0.5 rounded border border-cyan-500/20">
              %{wacc.toFixed(1)}
            </span>
          </div>
          <input
            type="range"
            min={isUsd ? 8 : 15}
            max={isUsd ? 22 : 40}
            step="0.5"
            value={wacc}
            onChange={(e) => {
              setWacc(parseFloat(e.target.value));
              setActiveScenario("custom");
            }}
            className="w-full accent-cyan-400 h-1.5 bg-zinc-800 rounded-lg cursor-pointer"
          />
          <span className="text-xs text-zinc-400 block mt-1">
            {isUsd ? "Global/Gelişmekte olan USD iskonto bandı (%8-%22)" : "Türkiye faiz/enflasyon dengeli nominal WACC (%15-%40)"}
          </span>
        </div>

        {/* Growth Rate Slider */}
        <div>
          <div className="flex justify-between items-center mb-1.5">
            <span className="font-semibold text-zinc-300 flex items-center gap-1">
              <Zap className="w-3.5 h-3.5 text-amber-400" />
              İlk 5 Yıl Büyüme (g1):
            </span>
            <span className="font-mono font-bold text-amber-400 bg-amber-500/10 px-2 py-0.5 rounded border border-amber-500/20">
              %{growthRate.toFixed(1)}
            </span>
          </div>
          <input
            type="range"
            min={isUsd ? 2 : 10}
            max={isUsd ? 25 : 55}
            step="0.5"
            value={growthRate}
            onChange={(e) => {
              setGrowthRate(parseFloat(e.target.value));
              setActiveScenario("custom");
            }}
            className="w-full accent-amber-400 h-1.5 bg-zinc-800 rounded-lg cursor-pointer"
          />
          <span className="text-xs text-zinc-400 block mt-1">
            5 yıl boyunca kademeli normalleşen nakit akım büyümesi
          </span>
        </div>

        {/* Terminal Growth Slider */}
        <div>
          <div className="flex justify-between items-center mb-1.5">
            <span className="font-semibold text-zinc-300 flex items-center gap-1">
              <BarChart3 className="w-3.5 h-3.5 text-emerald-400" />
              Uç Büyüme Oranı (gt):
            </span>
            <span className="font-mono font-bold text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded border border-emerald-500/20">
              %{terminalGrowth.toFixed(1)}
            </span>
          </div>
          <input
            type="range"
            min={isUsd ? 1.5 : 4}
            max={isUsd ? 6 : 14}
            step="0.25"
            value={terminalGrowth}
            onChange={(e) => {
              setTerminalGrowth(parseFloat(e.target.value));
              setActiveScenario("custom");
            }}
            className="w-full accent-emerald-400 h-1.5 bg-zinc-800 rounded-lg cursor-pointer"
          />
          <span className="text-xs text-zinc-400 block mt-1">
            5. yıldan sonraki sonsuz vadeli sürdürülebilir büyüme oranı
          </span>
        </div>
      </div>

      {/* TAB 1: MODEL DETAILS & PROJECTION */}
      {activeTab === "model" && (
        <div className="space-y-6">
          {/* Key Metric Cards */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <div className="bg-zinc-900/60 border border-zinc-800/80 rounded-xl p-3.5">
              <span className="text-xs text-zinc-400 block mb-1">5 Yıllık PV(FCF)</span>
              <span className="text-sm font-mono font-bold text-zinc-200">
                {formatMoney(calculation.pvFcfs)}
              </span>
            </div>
            <div className="bg-zinc-900/60 border border-zinc-800/80 rounded-xl p-3.5">
              <span className="text-xs text-zinc-400 block mb-1">İndirgenmiş Uç Değer</span>
              <span className="text-sm font-mono font-bold text-zinc-200">
                {formatMoney(calculation.pvTerminalVal)}
              </span>
            </div>
            <div className="bg-zinc-900/60 border border-zinc-800/80 rounded-xl p-3.5">
              <span className="text-xs text-zinc-400 block mb-1">Firma Değeri (EV)</span>
              <span className="text-sm font-mono font-bold text-cyan-400">
                {formatMoney(calculation.enterpriseValue)}
              </span>
            </div>
            <div className="bg-zinc-900/60 border border-zinc-800/80 rounded-xl p-3.5">
              <span className="text-xs text-zinc-400 block mb-1">Özsermaye Değeri</span>
              <span className="text-sm font-mono font-bold text-emerald-400">
                {formatMoney(calculation.equityValue)}
              </span>
            </div>
          </div>

          {/* 5-Year Projected Cash Flow Bars */}
          <div>
            <h4 className="text-xs font-mono font-bold text-zinc-400 uppercase tracking-wider mb-3">
              5 Yıllık Nakit Akım Projeksiyonu & İndirgeme
            </h4>
            <div className="grid grid-cols-5 gap-2 text-center text-xs">
              {calculation.projections.map((p) => (
                <div
                  key={p.year}
                  className="bg-zinc-900/80 border border-zinc-800 rounded-xl p-3 flex flex-col justify-between"
                >
                  <span className="text-xs text-zinc-400 font-mono font-bold uppercase">
                    Yıl {p.year} (+%{(p.growth * 100).toFixed(0)})
                  </span>
                  <div className="my-2">
                    <span className="text-xs font-mono font-bold text-white block">
                      {formatMoney(p.fcf)}
                    </span>
                    <span className="text-xs font-mono text-zinc-400 block mt-0.5">
                      PV: {formatMoney(p.pvFcf)}
                    </span>
                  </div>
                  <div className="w-full bg-zinc-800 h-1.5 rounded-full overflow-hidden mt-1">
                    <div
                      className="bg-cyan-500 h-full rounded-full"
                      style={{ width: `${Math.min(100, Math.max(15, (p.pvFcf / calculation.pvFcfs) * 350))}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* TAB 2: 5x5 HEATMAP SENSITIVITY MATRIX */}
      {activeTab === "sensitivity" && (
        <div>
          <div className="flex items-center justify-between mb-3">
            <div>
              <h4 className="text-xs font-mono font-bold text-zinc-400 uppercase tracking-wider">
                WACC vs. Uç Büyüme (gt) Duyarlılık Matrisi (Hedef Fiyat ₺)
              </h4>
              <p className="text-xs text-zinc-400">
                Farklı iskonto ve kalıcı büyüme senaryolarında modelin ürettiği hedef hisse fiyatları
              </p>
            </div>
            <div className="flex items-center gap-3 text-xs font-mono">
              <span className="flex items-center gap-1 text-emerald-400">
                <span className="w-2.5 h-2.5 rounded bg-emerald-500/30 border border-emerald-500/50" /> Model değeri fiyatın üzerinde
              </span>
              <span className="flex items-center gap-1 text-rose-400">
                <span className="w-2.5 h-2.5 rounded bg-rose-500/30 border border-rose-500/50" /> Model değeri fiyatın altında
              </span>
            </div>
          </div>

          <div className="overflow-x-auto rounded-xl border border-zinc-800">
            <table className="w-full text-xs text-center border-collapse">
              <thead>
                <tr className="bg-zinc-900/90 text-zinc-400 font-mono text-xs border-b border-zinc-800">
                  <th className="p-3 text-left font-bold border-r border-zinc-800">WACC \ gt</th>
                  {calculation.sensitivity.tgList.map((tg, idx) => (
                    <th key={idx} className="p-3 font-semibold">
                      %{(tg * 100).toFixed(1)}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-800/70 font-mono text-xs">
                {calculation.sensitivity.rows.map((row, rIdx) => (
                  <tr key={rIdx} className="hover:bg-zinc-900/40 transition-colors">
                    <td className="p-3 text-left font-bold text-zinc-300 bg-zinc-900/40 border-r border-zinc-800">
                      %{(row.wacc * 100).toFixed(1)}
                    </td>
                    {row.values.map((val, cIdx) => {
                      const pot = ((val - dcf.guncel_fiyat) / dcf.guncel_fiyat) * 100;
                      let bgClass = "bg-zinc-900/40 text-zinc-300";
                      if (pot >= 30) {
                        bgClass = "bg-emerald-500/15 text-emerald-300 font-bold border border-emerald-500/20";
                      } else if (pot >= 0) {
                        bgClass = "bg-cyan-500/10 text-cyan-300 font-semibold";
                      } else if (pot >= -20) {
                        bgClass = "bg-zinc-900/60 text-zinc-400";
                      } else {
                        bgClass = "bg-rose-500/15 text-rose-300 font-semibold";
                      }

                      const isCurrentCenter = rIdx === 2 && cIdx === 2;

                      return (
                        <td key={cIdx} className={`p-3 relative ${bgClass}`}>
                          {val.toFixed(1)} ₺
                          {isCurrentCenter && (
                            <span className="absolute top-1 right-1 w-1.5 h-1.5 rounded-full bg-cyan-400 animate-pulse" />
                          )}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* TAB 3: EQUITY BRIDGE */}
      {activeTab === "bridge" && (
        <div className="space-y-4">
          <h4 className="text-xs font-mono font-bold text-zinc-400 uppercase tracking-wider mb-2">
            Firma Değerinden (EV) Özsermayeye Köprü
          </h4>
          <div className="flex flex-col md:flex-row items-center justify-between gap-3 bg-zinc-900/60 p-5 rounded-xl border border-zinc-800 text-xs font-mono">
            <div className="text-center md:text-left">
              <span className="text-xs text-zinc-400 block uppercase font-bold">Toplam Firma Değeri</span>
              <span className="text-base font-bold text-cyan-400">{formatMoney(calculation.enterpriseValue)}</span>
            </div>
            <span className="text-zinc-400 text-lg font-bold">+</span>
            <div className="text-center">
              <span className="text-xs text-zinc-400 block uppercase font-bold">Nakit & Benzerleri</span>
              <span className="text-base font-bold text-emerald-400">{formatMoney(dcf.nakit_ve_benzerleri)}</span>
            </div>
            <span className="text-zinc-400 text-lg font-bold">-</span>
            <div className="text-center">
              <span className="text-xs text-zinc-400 block uppercase font-bold">Toplam Finansal Borç</span>
              <span className="text-base font-bold text-rose-400">{formatMoney(dcf.toplam_borc)}</span>
            </div>
            <span className="text-zinc-400 text-lg font-bold">=</span>
            <div className="text-center md:text-right bg-zinc-800/50 p-3 rounded-lg border border-zinc-700/60">
              <span className="text-xs text-zinc-400 block uppercase font-bold">Net Özsermaye Değeri</span>
              <span className="text-base font-extrabold text-white">{formatMoney(calculation.equityValue)}</span>
            </div>
          </div>
          <div className="text-xs text-zinc-400 bg-zinc-900/40 p-4 rounded-xl border border-zinc-800/60 flex items-start gap-2">
            <Info className="w-4 h-4 text-zinc-400 shrink-0 mt-0.5" />
            <p>
              Net Borç köprüsü, şirketin sahip olduğu nakit varlıkları eklerken tüm finansal yükümlülüklerini düşerek hisse senedi sahiplerine kalan gerçek nakit yaratma potansiyelini izole eder. Dolaşımdaki toplam <strong>{dcf.hisse_adedi.toLocaleString("tr-TR")}</strong> adet hisseye bölünerek hisse başına <strong>{calculation.fairValueTry.toFixed(2)} TL</strong> adil değere ulaşılır.
            </p>
          </div>
        </div>
      )}

      {/* SPK Disclaimer */}
      <div className="mt-6 pt-4 border-t border-zinc-800/60 text-xs text-zinc-400 flex items-center justify-between">
        <span className="flex items-center gap-1.5">
          <ShieldCheck className="w-3.5 h-3.5 text-zinc-400" />
          İNA Değerleme Modeli kamuya açık konsolide finansallardan otomatik türetilmiştir. Yatırım tavsiyesi değildir.
        </span>
        <button
          onClick={() => handleScenarioSelect("base")}
          className="hover:text-zinc-300 text-zinc-400 flex items-center gap-1 transition-colors"
        >
          <RotateCcw className="w-3 h-3" /> Varsayılana Dön
        </button>
      </div>
    </div>
  );
}
