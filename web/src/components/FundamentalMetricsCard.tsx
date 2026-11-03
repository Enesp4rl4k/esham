import React from "react";
import { Building2, PieChart, ShieldCheck, Award } from "lucide-react";

interface FundamentalData {
  ticker: string;
  sirket: string;
  sektor: string;
  alt_sektor: string;
  piyasa_degeri_tl: number;
  piyasa_degeri_fmt: string;
  fiyat_kazanc_fk: number | null;
  piyasa_defter_pddd: number | null;
  fd_favok: number | null;
  yillik_hasilat_tl: number | null;
  hasilat_fmt: string;
  net_kar_marji_yuzde: number | null;
  ozsermaye_karliligi_roe: number | null;
  sozlesme_ciro_analizi: {
    sozlesme_tutari_str: string;
    ciro_orani_yuzde: number;
    tier: string;
    degerlendirme: string;
  } | null;
}

interface FundamentalMetricsCardProps {
  data: FundamentalData;
}

export function FundamentalMetricsCard({ data }: FundamentalMetricsCardProps) {
  return (
    <div className="rounded-2xl border border-zinc-800 bg-zinc-950/80 p-6 backdrop-blur-sm shadow-xl">
      <div className="flex items-center justify-between pb-4 border-b border-zinc-800/80 mb-5">
        <div className="flex items-center gap-2">
          <span className="p-1.5 rounded-lg bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
            <PieChart className="w-4 h-4" />
          </span>
          <h3 className="text-sm font-bold text-white tracking-tight">
            Temel Finansal Çarpanlar
          </h3>
        </div>
        <span className="text-[11px] font-mono text-zinc-400 bg-zinc-900 px-2 py-0.5 rounded border border-zinc-800">
          {data.sektor}
        </span>
      </div>

      <div className="grid grid-cols-2 gap-3 text-xs font-mono">
        <div className="bg-zinc-900/60 p-3 rounded-xl border border-zinc-800">
          <span className="text-[10px] text-zinc-500 block uppercase">Piyasa Değeri</span>
          <span className="text-sm font-bold text-white mt-0.5 block">{data.piyasa_degeri_fmt}</span>
        </div>

        <div className="bg-zinc-900/60 p-3 rounded-xl border border-zinc-800">
          <span className="text-[10px] text-zinc-500 block uppercase">Fiyat / Kazanç (F/K)</span>
          <span className="text-sm font-bold text-cyan-400 mt-0.5 block">
            {data.fiyat_kazanc_fk ? data.fiyat_kazanc_fk.toFixed(2) : "—"}
          </span>
        </div>

        <div className="bg-zinc-900/60 p-3 rounded-xl border border-zinc-800">
          <span className="text-[10px] text-zinc-500 block uppercase">Piyasa / Defter (PD/DD)</span>
          <span className="text-sm font-bold text-zinc-200 mt-0.5 block">
            {data.piyasa_defter_pddd ? data.piyasa_defter_pddd.toFixed(2) : "—"}
          </span>
        </div>

        <div className="bg-zinc-900/60 p-3 rounded-xl border border-zinc-800">
          <span className="text-[10px] text-zinc-500 block uppercase">FD / FAVÖK</span>
          <span className="text-sm font-bold text-zinc-200 mt-0.5 block">
            {data.fd_favok ? data.fd_favok.toFixed(2) : "—"}
          </span>
        </div>

        <div className="bg-zinc-900/60 p-3 rounded-xl border border-zinc-800">
          <span className="text-[10px] text-zinc-500 block uppercase">Yıllık Ciro (Hasılat)</span>
          <span className="text-sm font-bold text-zinc-200 mt-0.5 block">{data.hasilat_fmt}</span>
        </div>

        <div className="bg-zinc-900/60 p-3 rounded-xl border border-zinc-800">
          <span className="text-[10px] text-zinc-500 block uppercase">Net Kâr Marjı</span>
          <span className="text-sm font-bold text-emerald-400 mt-0.5 block">
            {data.net_kar_marji_yuzde !== null ? `%${data.net_kar_marji_yuzde.toFixed(1)}` : "—"}
          </span>
        </div>

        <div className="col-span-2 bg-zinc-900/60 p-3 rounded-xl border border-zinc-800 flex justify-between items-center">
          <div>
            <span className="text-[10px] text-zinc-500 block uppercase">Özsermaye Kârlılığı (ROE)</span>
            <span className="text-xs text-zinc-400">Sermaye getiri verimliliği</span>
          </div>
          <span className="text-base font-bold text-emerald-400">
            {data.ozsermaye_karliligi_roe !== null ? `%${data.ozsermaye_karliligi_roe.toFixed(1)}` : "—"}
          </span>
        </div>
      </div>

      {/* Sözleşme Ciro Analizi Varsa */}
      {data.sozlesme_ciro_analizi && (
        <div className="mt-4 p-3.5 rounded-xl bg-amber-500/10 border border-amber-500/20 text-xs">
          <div className="flex items-center gap-1.5 text-amber-400 font-bold mb-1">
            <Award className="w-3.5 h-3.5" />
            <span>{data.sozlesme_ciro_analizi.tier}</span>
          </div>
          <div className="text-[11px] text-zinc-300 space-y-0.5">
            <p>Sözleşme Tutarı: <strong>{data.sozlesme_ciro_analizi.sozlesme_tutari_str}</strong></p>
            <p>Yıllık Ciroya Oranı: <strong>%{data.sozlesme_ciro_analizi.ciro_orani_yuzde.toFixed(1)}</strong></p>
            <p className="text-[10px] text-zinc-400 mt-1">{data.sozlesme_ciro_analizi.degerlendirme}</p>
          </div>
        </div>
      )}
    </div>
  );
}
