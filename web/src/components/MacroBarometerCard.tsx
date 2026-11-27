import React from "react";
import {
  Globe,
  ShieldCheck,
  TrendingDown,
  TrendingUp,
  Activity,
  Layers,
  Banknote,
  Info,
} from "lucide-react";

export interface MacroBarometerData {
  cds_5y_bps: number;
  cds_bolgesi: string;
  cds_aylik_degisim: number;
  tcmb_brut_rezerv_milyar_dolar: number;
  tcmb_net_rezerv_milyar_dolar: number;
  tcmb_swap_haric_net_rezerv_milyar_dolar: number;
  rezerv_trendi: string;
  politika_faizi_yuzde: number;
  mevduat_faizi_yuzde: number;
  gosterge_tahvil_2y_yuzde: number;
  hisse_risk_primi_erp_yuzde: number;
  piyasa_risk_istahi: string;
  ozet: string;
}

interface MacroBarometerCardProps {
  data: MacroBarometerData;
}

export function MacroBarometerCard({ data }: MacroBarometerCardProps) {
  const isCdsSafe = data.cds_5y_bps < 260;
  const isCdsDown = data.cds_aylik_degisim <= 0;

  return (
    <div className="rounded-2xl border border-zinc-800 bg-zinc-950/85 p-6 backdrop-blur-md shadow-xl">
      {/* Başlık */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-4 border-b border-zinc-800 mb-5 gap-3">
        <div className="flex items-center gap-2.5">
          <span className="p-2 rounded-xl bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
            <Globe className="w-5 h-5" />
          </span>
          <div>
            <h3 className="text-sm font-bold text-white tracking-tight flex items-center gap-2">
              Türkiye Makro Risk & Rezerv Barometresi
              <span className="text-xs font-mono px-2 py-0.5 rounded bg-zinc-900 border border-zinc-800 text-zinc-400">
                TCMB & CDS
              </span>
            </h3>
            <p className="text-xs text-zinc-400 mt-0.5">
              5 Yıllık Kredi İflas Takası (CDS), Swap Hariç Rezervler ve Hisse Risk Primi
            </p>
          </div>
        </div>

        <span
          className={`px-2.5 py-1 rounded-lg text-xs font-mono font-semibold border shrink-0 ${
            isCdsSafe
              ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-400"
              : "bg-amber-500/10 border-amber-500/30 text-amber-400"
          }`}
        >
          {data.piyasa_risk_istahi}
        </span>
      </div>

      {/* Grid 4 Kart */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs font-mono mb-5">
        {/* 1. Türkiye 5Y CDS */}
        <div className="bg-zinc-900/60 p-3.5 rounded-xl border border-zinc-800">
          <span className="text-xs text-zinc-400 block uppercase">5Y CDS Primi</span>
          <div className="flex items-baseline gap-1.5 mt-1">
            <span className="text-xl font-extrabold text-white">
              {data.cds_5y_bps.toFixed(0)}
            </span>
            <span className="text-xs text-zinc-400 font-mono">bps</span>
          </div>
          <span
            className={`flex items-center gap-1 text-xs font-bold mt-1.5 ${
              isCdsDown ? "text-emerald-400" : "text-rose-400"
            }`}
          >
            {isCdsDown ? <TrendingDown className="w-3 h-3" /> : <TrendingUp className="w-3 h-3" />}
            {data.cds_aylik_degisim > 0 ? `+${data.cds_aylik_degisim}` : data.cds_aylik_degisim} bps (Aylık)
          </span>
        </div>

        {/* 2. Swap Hariç Net Rezerv */}
        <div className="bg-zinc-900/60 p-3.5 rounded-xl border border-zinc-800">
          <span className="text-xs text-zinc-400 block uppercase">TCMB Swap Hariç Net</span>
          <div className="flex items-baseline gap-1 mt-1">
            <span className="text-xl font-extrabold text-emerald-400">
              +${data.tcmb_swap_haric_net_rezerv_milyar_dolar.toFixed(1)}
            </span>
            <span className="text-xs text-zinc-400 font-mono">Milyar $</span>
          </div>
          <span className="text-xs text-zinc-400 block mt-1.5 font-sans">
            Brüt: ${data.tcmb_brut_rezerv_milyar_dolar} Milyar
          </span>
        </div>

        {/* 3. Hisse Risk Primi (ERP) */}
        <div className="bg-zinc-900/60 p-3.5 rounded-xl border border-zinc-800">
          <span className="text-xs text-zinc-400 block uppercase">Hisse Risk Primi (ERP)</span>
          <div className="flex items-baseline gap-1 mt-1">
            <span className="text-xl font-extrabold text-cyan-400">
              %{data.hisse_risk_primi_erp_yuzde.toFixed(1)}
            </span>
          </div>
          <span className="text-xs text-zinc-400 block mt-1.5 font-sans">
            BIST Beklenen vs Tahvil
          </span>
        </div>

        {/* 4. Politika Faizi */}
        <div className="bg-zinc-900/60 p-3.5 rounded-xl border border-zinc-800">
          <span className="text-xs text-zinc-400 block uppercase">TCMB Politika Faizi</span>
          <div className="flex items-baseline gap-1 mt-1">
            <span className="text-xl font-extrabold text-white">
              %{data.politika_faizi_yuzde.toFixed(0)}
            </span>
            <span className="text-xs text-zinc-400 font-mono">1 Hafta Repo</span>
          </div>
          <span className="text-xs text-zinc-400 block mt-1.5 font-sans">
            Mevduat: %{data.mevduat_faizi_yuzde}
          </span>
        </div>
      </div>

      {/* Makro Analist Notu */}
      <div className="pt-3 border-t border-zinc-800/80 flex items-center gap-2 text-xs text-zinc-400">
        <Info className="w-3.5 h-3.5 text-indigo-400 shrink-0" />
        <span className="truncate">{data.ozet}</span>
      </div>
    </div>
  );
}
