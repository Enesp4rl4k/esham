import React from "react";
import { Compass, Target, ArrowUp, ArrowDown, Activity, Layers } from "lucide-react";

interface KeyLevelsData {
  ticker: string;
  son_fiyat: number;
  gunluk_degisim_yuzde: number;
  pivot_noktasi: number;
  direncler: {
    r1: number;
    r2: number;
    direnc_20g: number;
    fib_618: number;
  };
  destekler: {
    s1: number;
    s2: number;
    destek_20g: number;
    fib_382: number;
  };
  hareketli_ortalamalar: {
    sma_20: number;
    sma_50: number;
  };
  rsi_14: number;
  rsi_bolgesi: string;
  "52h_zirve": number;
  "52h_dip": number;
  zirveye_uzaklik_yuzde: number;
}

interface KeyLevelsCardProps {
  data: KeyLevelsData;
}

export function KeyLevelsCard({ data }: KeyLevelsCardProps) {
  const isUp = data.gunluk_degisim_yuzde >= 0;
  const isAbovePivot = data.son_fiyat >= data.pivot_noktasi;

  // 52 Week Range percentage
  const range52 = data["52h_zirve"] - data["52h_dip"];
  const rangePos =
    range52 > 0 ? Math.min(100, Math.max(0, ((data.son_fiyat - data["52h_dip"]) / range52) * 100)) : 50;

  return (
    <div className="rounded-2xl border border-zinc-800 bg-zinc-950/80 p-6 backdrop-blur-sm shadow-xl">
      <div className="flex items-center justify-between pb-4 border-b border-zinc-800/80 mb-5">
        <div className="flex items-center gap-2">
          <span className="p-1.5 rounded-lg bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
            <Compass className="w-4 h-4" />
          </span>
          <h3 className="text-sm font-bold text-white tracking-tight">
            Key Levels & Teknik Eşikler
          </h3>
        </div>
        <span
          className={`text-[11px] font-mono font-bold px-2.5 py-0.5 rounded-full border ${
            isAbovePivot
              ? "bg-emerald-500/15 text-emerald-400 border-emerald-500/30"
              : "bg-rose-500/15 text-rose-400 border-rose-500/30"
          }`}
        >
          {isAbovePivot ? "Boğa (Pivot Üstü)" : "Ayı (Pivot Altı)"}
        </span>
      </div>

      {/* Pivot & Support/Resistance Grid */}
      <div className="space-y-4 text-xs font-mono">
        {/* Pivot Highlight */}
        <div className="flex items-center justify-between bg-zinc-900/80 p-3 rounded-xl border border-zinc-800">
          <div className="flex items-center gap-2">
            <Target className="w-4 h-4 text-cyan-400" />
            <span className="text-zinc-300 font-semibold">Günlük Pivot Noktası</span>
          </div>
          <span className="text-sm font-bold text-cyan-400">
            {data.pivot_noktasi.toFixed(2)} ₺
          </span>
        </div>

        {/* Dirençler (R1, R2, Fib 61.8) */}
        <div className="bg-rose-500/5 border border-rose-500/15 rounded-xl p-3">
          <div className="flex items-center justify-between text-rose-400 mb-2">
            <span className="flex items-center gap-1 font-semibold text-[11px] uppercase">
              <ArrowUp className="w-3 h-3" /> Kritik Direnç Eşikleri
            </span>
            <span className="text-[10px] text-zinc-500">Satış / Kâr Realizasyonu</span>
          </div>
          <div className="grid grid-cols-3 gap-2 text-center">
            <div className="bg-zinc-900/70 p-2 rounded-lg border border-zinc-800">
              <span className="text-[10px] text-zinc-500 block">R1 Direnç</span>
              <span className="font-bold text-zinc-200">{data.direncler.r1.toFixed(2)} ₺</span>
            </div>
            <div className="bg-zinc-900/70 p-2 rounded-lg border border-zinc-800">
              <span className="text-[10px] text-zinc-500 block">R2 Direnç</span>
              <span className="font-bold text-zinc-200">{data.direncler.r2.toFixed(2)} ₺</span>
            </div>
            <div className="bg-zinc-900/70 p-2 rounded-lg border border-zinc-800">
              <span className="text-[10px] text-zinc-500 block">Fib %61.8</span>
              <span className="font-bold text-zinc-200">{data.direncler.fib_618.toFixed(2)} ₺</span>
            </div>
          </div>
        </div>

        {/* Destekler (S1, S2, Fib 38.2) */}
        <div className="bg-emerald-500/5 border border-emerald-500/15 rounded-xl p-3">
          <div className="flex items-center justify-between text-emerald-400 mb-2">
            <span className="flex items-center gap-1 font-semibold text-[11px] uppercase">
              <ArrowDown className="w-3 h-3" /> Kritik Destek Eşikleri
            </span>
            <span className="text-[10px] text-zinc-500">Tepki Alım Tabanı</span>
          </div>
          <div className="grid grid-cols-3 gap-2 text-center">
            <div className="bg-zinc-900/70 p-2 rounded-lg border border-zinc-800">
              <span className="text-[10px] text-zinc-500 block">S1 Destek</span>
              <span className="font-bold text-zinc-200">{data.destekler.s1.toFixed(2)} ₺</span>
            </div>
            <div className="bg-zinc-900/70 p-2 rounded-lg border border-zinc-800">
              <span className="text-[10px] text-zinc-500 block">S2 Destek</span>
              <span className="font-bold text-zinc-200">{data.destekler.s2.toFixed(2)} ₺</span>
            </div>
            <div className="bg-zinc-900/70 p-2 rounded-lg border border-zinc-800">
              <span className="text-[10px] text-zinc-500 block">Fib %38.2</span>
              <span className="font-bold text-zinc-200">{data.destekler.fib_382.toFixed(2)} ₺</span>
            </div>
          </div>
        </div>

        {/* 14G RSI & Hareketli Ortalamalar */}
        <div className="grid grid-cols-2 gap-3 pt-1">
          <div className="bg-zinc-900/60 p-3 rounded-xl border border-zinc-800">
            <div className="flex justify-between items-center mb-1">
              <span className="text-zinc-500 text-[11px]">14G RSI</span>
              <span className="font-bold text-white">{data.rsi_14.toFixed(1)}</span>
            </div>
            <div className="w-full bg-zinc-800 h-1.5 rounded-full overflow-hidden mb-1">
              <div
                className={`h-full rounded-full ${
                  data.rsi_14 >= 70
                    ? "bg-rose-500"
                    : data.rsi_14 <= 30
                    ? "bg-emerald-500"
                    : "bg-cyan-500"
                }`}
                style={{ width: `${Math.min(100, data.rsi_14)}%` }}
              />
            </div>
            <span className="text-[10px] text-zinc-400 block">{data.rsi_bolgesi}</span>
          </div>

          <div className="bg-zinc-900/60 p-3 rounded-xl border border-zinc-800">
            <span className="text-zinc-500 text-[11px] block mb-1">Trend Ortalamaları</span>
            <div className="flex justify-between text-[11px]">
              <span className="text-zinc-400">20G HO:</span>
              <span className="font-bold text-zinc-200">{data.hareketli_ortalamalar.sma_20.toFixed(2)} ₺</span>
            </div>
            <div className="flex justify-between text-[11px] mt-0.5">
              <span className="text-zinc-400">50G HO:</span>
              <span className="font-bold text-zinc-200">{data.hareketli_ortalamalar.sma_50.toFixed(2)} ₺</span>
            </div>
          </div>
        </div>

        {/* 52 Hafta Bandı */}
        <div className="bg-zinc-900/40 p-3 rounded-xl border border-zinc-800/80">
          <div className="flex justify-between items-center text-[10px] text-zinc-400 mb-1.5">
            <span>52H Dip: {data["52h_dip"].toFixed(2)} ₺</span>
            <span className="text-zinc-300 font-bold">
              Zirveye Uzaklık: %{data.zirveye_uzaklik_yuzde.toFixed(1)}
            </span>
            <span>52H Zirve: {data["52h_zirve"].toFixed(2)} ₺</span>
          </div>
          <div className="w-full bg-zinc-800 h-1.5 rounded-full overflow-hidden relative">
            <div
              className="bg-indigo-500 h-full rounded-full"
              style={{ width: `${rangePos}%` }}
            />
          </div>
        </div>
      </div>
    </div>
  );
}
