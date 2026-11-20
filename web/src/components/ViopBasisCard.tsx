import React from "react";
import {
  TrendingUp,
  Activity,
  ShieldCheck,
  AlertTriangle,
  ArrowRight,
  Layers,
  Coins,
} from "lucide-react";

export interface ViopBasisData {
  spot_xu030: number;
  vadeli_f_xu030: number;
  basis_puan: number;
  basis_yuzde: number;
  ima_edilen_yillik_faiz_yuzde: number;
  vadeye_kalan_gun: number;
  acik_pozisyon_lot: number;
  acik_pozisyon_gunluk_degisim: number;
  teminat_tamamlama_durumu: string;
  teminat_tamamlama_tutari: string;
  degerlendirme: string;
}

interface ViopBasisCardProps {
  data: ViopBasisData;
}

export function ViopBasisCard({ data }: ViopBasisCardProps) {
  const isContango = data.basis_puan >= 0;
  const isOiUp = data.acik_pozisyon_gunluk_degisim >= 0;

  return (
    <div className="rounded-2xl border border-zinc-800 bg-zinc-950/85 p-6 backdrop-blur-md shadow-xl">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-4 border-b border-zinc-800 mb-5 gap-3">
        <div className="flex items-center gap-2.5">
          <span className="p-2 rounded-xl bg-cyan-500/10 text-cyan-400 border border-cyan-500/20">
            <Activity className="w-5 h-5" />
          </span>
          <div>
            <h3 className="text-sm font-bold text-white tracking-tight flex items-center gap-2">
              VİOP BIST 30 Basis & Likidite Radarı
              <span className="text-xs font-mono px-2 py-0.5 rounded bg-zinc-900 border border-zinc-800 text-zinc-400">
                F_XU030
              </span>
            </h3>
            <p className="text-xs text-zinc-400 mt-0.5">
              Spot vs. Vadeli Prim/İskonto, Taşıma Maliyeti ve Takasbank Teminat Göstergeleri
            </p>
          </div>
        </div>

        <span className="px-2.5 py-1 rounded-lg text-xs font-mono font-semibold bg-cyan-500/10 border border-cyan-500/30 text-cyan-400 shrink-0">
          {isContango ? "Contango (Vadeli Primli)" : "Backwardation (Vadeli İskontolu)"}
        </span>
      </div>

      {/* 4 KPI Kutusu */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs font-mono mb-5">
        {/* 1. Basis Farkı */}
        <div className="bg-zinc-900/60 p-3.5 rounded-xl border border-zinc-800">
          <span className="text-xs text-zinc-400 block uppercase">Basis (Fark Puan)</span>
          <div className="flex items-baseline gap-1 mt-1">
            <span className="text-xl font-extrabold text-white">
              {data.basis_puan > 0 ? `+${data.basis_puan}` : data.basis_puan}
            </span>
            <span className="text-xs text-zinc-400">puan</span>
          </div>
          <span className="text-xs text-cyan-400 block mt-1.5 font-sans">
            %{data.basis_yuzde.toFixed(2)} Vadeli Primi
          </span>
        </div>

        {/* 2. İma Edilen Yıllık Faiz */}
        <div className="bg-zinc-900/60 p-3.5 rounded-xl border border-zinc-800">
          <span className="text-xs text-zinc-400 block uppercase">İma Edilen Taşıma Faizi</span>
          <div className="flex items-baseline gap-1 mt-1">
            <span className="text-xl font-extrabold text-emerald-400">
              %{data.ima_edilen_yillik_faiz_yuzde.toFixed(1)}
            </span>
            <span className="text-xs text-zinc-400 font-mono">Yıllık</span>
          </div>
          <span className="text-xs text-zinc-400 block mt-1.5 font-sans">
            Vadeye {data.vadeye_kalan_gun} Gün Kaldı
          </span>
        </div>

        {/* 3. Açık Pozisyon (Open Interest) */}
        <div className="bg-zinc-900/60 p-3.5 rounded-xl border border-zinc-800">
          <span className="text-xs text-zinc-400 block uppercase">Açık Pozisyon Sayısı</span>
          <div className="flex items-baseline gap-1 mt-1">
            <span className="text-xl font-extrabold text-white">
              {(data.acik_pozisyon_lot / 1000).toFixed(1)}K
            </span>
            <span className="text-xs text-zinc-400">lot</span>
          </div>
          <span
            className={`flex items-center gap-1 text-xs font-bold mt-1.5 ${
              isOiUp ? "text-emerald-400" : "text-rose-400"
            }`}
          >
            <TrendingUp className="w-3 h-3" />
            {data.acik_pozisyon_gunluk_degisim > 0 ? `+${data.acik_pozisyon_gunluk_degisim}` : data.acik_pozisyon_gunluk_degisim} lot (Günlük)
          </span>
        </div>

        {/* 4. Takasbank Margin Call */}
        <div className="bg-zinc-900/60 p-3.5 rounded-xl border border-zinc-800">
          <span className="text-xs text-zinc-400 block uppercase">Takasbank Margin Call</span>
          <div className="flex items-baseline gap-1 mt-1">
            <span className="text-lg font-bold text-white">
              {data.teminat_tamamlama_tutari}
            </span>
          </div>
          <span className="text-xs text-emerald-400 block mt-1.5 font-sans">
            {data.teminat_tamamlama_durumu}
          </span>
        </div>
      </div>

      {/* Değerlendirme Çubuğu */}
      <div className="pt-3 border-t border-zinc-800/80 text-xs text-zinc-400 leading-relaxed">
        <strong>Kurumsal Sinyal:</strong> {data.degerlendirme}
      </div>
    </div>
  );
}
