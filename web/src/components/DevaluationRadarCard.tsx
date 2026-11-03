import React from "react";
import Link from "next/link";
import {
  AlertTriangle,
  ShieldCheck,
  Flame,
  ArrowRight,
  TrendingDown,
  TrendingUp,
  Landmark,
  Scale,
  Gauge,
  Percent,
} from "lucide-react";

export interface DevaluationRadarData {
  composite_score: number;
  risk_level: "LOW" | "MODERATE" | "HIGH" | "CRITICAL";
  risk_label: string;
  risk_summary: string;
  updated_at: string;
  components: {
    viop_implied_yield: {
      spot_usd: number;
      futures_usd: number;
      days_to_expiry: number;
      implied_rate_pct: number;
      policy_rate_pct: number;
      spread_pct: number;
      score: number;
      status: string;
    };
    tcmb_reserves: {
      swap_free_net_usd_bn: number;
      monthly_change_usd_bn: number;
      burn_rate_status: string;
      score: number;
      status: string;
    };
    grand_bazaar_spread: {
      interbank_usd: number;
      grand_bazaar_usd: number;
      spread_pct: number;
      score: number;
      status: string;
    };
    cds_5y: {
      value_bps: number;
      score: number;
      status: string;
    };
    reer: {
      value: number;
      score: number;
      status: string;
    };
  };
  historical_benchmarks?: Array<{
    period: string;
    label: string;
    score: number;
    usd_try: string;
    spread_bazaar: string;
    net_reserves: string;
    result: string;
  }>;
}

interface DevaluationRadarCardProps {
  data: DevaluationRadarData;
  compact?: boolean;
}

export function DevaluationRadarCard({ data, compact = false }: DevaluationRadarCardProps) {
  const score = data.composite_score;

  // Renk kodlaması
  const isLow = data.risk_level === "LOW";
  const isModerate = data.risk_level === "MODERATE";
  const isHigh = data.risk_level === "HIGH";
  const isCritical = data.risk_level === "CRITICAL";

  const badgeColor = isLow
    ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-400"
    : isModerate
    ? "bg-amber-500/10 border-amber-500/30 text-amber-400"
    : isHigh
    ? "bg-orange-500/10 border-orange-500/30 text-orange-400"
    : "bg-rose-500/10 border-rose-500/30 text-rose-400 animate-pulse";

  const progressPercent = Math.min(100, Math.max(0, score));

  return (
    <div className="rounded-2xl border border-zinc-800 bg-zinc-950/85 p-6 backdrop-blur-md shadow-xl">
      {/* Üst Başlık */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-4 border-b border-zinc-800 mb-5 gap-3">
        <div className="flex items-center gap-2.5">
          <span className="p-2 rounded-xl bg-amber-500/10 text-amber-400 border border-amber-500/20">
            <Gauge className="w-5 h-5" />
          </span>
          <div>
            <h3 className="text-sm font-bold text-white tracking-tight flex items-center gap-2">
              TRY Kur Şoku & Devalüasyon Basınç Radarı
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-zinc-900 border border-zinc-800 text-zinc-400">
                0-100 Endeks
              </span>
            </h3>
            <p className="text-xs text-zinc-400 mt-0.5">
              VİOP İma Edilen Faiz, Swap Hariç Rezerv Yanma Hızı ve Kapalıçarşı Makas Analizi
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <span className={`px-2.5 py-1 rounded-lg text-xs font-mono font-semibold border shrink-0 ${badgeColor}`}>
            {isLow && <ShieldCheck className="w-3.5 h-3.5 inline mr-1" />}
            {isHigh && <Flame className="w-3.5 h-3.5 inline mr-1" />}
            {isCritical && <AlertTriangle className="w-3.5 h-3.5 inline mr-1" />}
            {data.risk_label} ({score}/100)
          </span>
        </div>
      </div>

      {/* Görsel Basınç Barı */}
      <div className="mb-6 p-4 rounded-xl bg-zinc-900/60 border border-zinc-800/80">
        <div className="flex justify-between items-center text-xs font-mono mb-2">
          <span className="text-zinc-400">Kur Basınç Skoru</span>
          <span className="font-bold text-white">
            %{score.toFixed(1)}{" "}
            <span className="text-[10px] text-zinc-500 font-normal">
              (0 = Tam İstikrar, 100 = Ani Kur Şoku)
            </span>
          </span>
        </div>

        {/* Çok kademeli renk çubuğu */}
        <div className="relative h-3 w-full rounded-full bg-zinc-800 overflow-hidden flex">
          <div className="w-[30%] bg-emerald-500/70 h-full" title="0-30: Düşük Risk" />
          <div className="w-[30%] bg-amber-500/70 h-full" title="31-60: Dengeli" />
          <div className="w-[20%] bg-orange-500/70 h-full" title="61-80: Yüksek Basınç" />
          <div className="w-[20%] bg-rose-500/80 h-full" title="81-100: Kriz Alarmı" />
          
          {/* İbre Noktası */}
          <div
            className="absolute top-0 bottom-0 w-1.5 bg-white shadow-[0_0_10px_#ffffff] rounded-full -ml-0.5 transition-all duration-500"
            style={{ left: `${progressPercent}%` }}
          />
        </div>

        {/* Eşik etiketleri */}
        <div className="flex justify-between text-[10px] font-mono text-zinc-500 mt-1.5">
          <span>0 (Sakin)</span>
          <span>30 (Düşük)</span>
          <span>60 (Dengeli)</span>
          <span>80 (Yüksek)</span>
          <span>100 (Şok)</span>
        </div>
      </div>

      {/* 5 Temel Gösterge Izgarası */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3 text-xs font-mono mb-5">
        {/* 1. Kapalıçarşı Makası */}
        <div className="p-3 rounded-xl bg-zinc-900/70 border border-zinc-800 flex flex-col justify-between">
          <span className="text-[11px] text-zinc-400 flex items-center gap-1">
            <Scale className="w-3 h-3 text-amber-400" />
            Tahtakale Makası
          </span>
          <div className="mt-2">
            <span className="text-sm font-bold text-white">
              %{data.components.grand_bazaar_spread.spread_pct.toFixed(2)}
            </span>
            <span className="text-[10px] block text-emerald-400 mt-0.5">
              Normal (&le; %0.4)
            </span>
          </div>
        </div>

        {/* 2. VİOP İma Edilen Faiz */}
        <div className="p-3 rounded-xl bg-zinc-900/70 border border-zinc-800 flex flex-col justify-between">
          <span className="text-[11px] text-zinc-400 flex items-center gap-1">
            <Percent className="w-3 h-3 text-sky-400" />
            VİOP İma Edilen Faiz
          </span>
          <div className="mt-2">
            <span className="text-sm font-bold text-white">
              %{data.components.viop_implied_yield.implied_rate_pct.toFixed(1)}
            </span>
            <span className="text-[10px] block text-zinc-400 mt-0.5">
              TCMB %{data.components.viop_implied_yield.policy_rate_pct.toFixed(0)} altı
            </span>
          </div>
        </div>

        {/* 3. TCMB Swap Hariç Rezerv */}
        <div className="p-3 rounded-xl bg-zinc-900/70 border border-zinc-800 flex flex-col justify-between">
          <span className="text-[11px] text-zinc-400 flex items-center gap-1">
            <Landmark className="w-3 h-3 text-emerald-400" />
            Swap Hariç Rezerv
          </span>
          <div className="mt-2">
            <span className="text-sm font-bold text-emerald-400">
              +${data.components.tcmb_reserves.swap_free_net_usd_bn.toFixed(1)} Mrd
            </span>
            <span className="text-[10px] block text-emerald-500 mt-0.5">
              +{data.components.tcmb_reserves.monthly_change_usd_bn.toFixed(1)} Mrd$/ay
            </span>
          </div>
        </div>

        {/* 4. Türkiye 5Y CDS */}
        <div className="p-3 rounded-xl bg-zinc-900/70 border border-zinc-800 flex flex-col justify-between">
          <span className="text-[11px] text-zinc-400 flex items-center gap-1">
            <ShieldCheck className="w-3 h-3 text-violet-400" />
            5Y CDS Primi
          </span>
          <div className="mt-2">
            <span className="text-sm font-bold text-white">
              {data.components.cds_5y.value_bps.toFixed(0)} bps
            </span>
            <span className="text-[10px] block text-emerald-400 mt-0.5">
              Düşük Risk (&lt; 280)
            </span>
          </div>
        </div>

        {/* 5. TÜFE REER */}
        <div className="p-3 rounded-xl bg-zinc-900/70 border border-zinc-800 flex flex-col justify-between col-span-2 md:col-span-1">
          <span className="text-[11px] text-zinc-400 flex items-center gap-1">
            <Gauge className="w-3 h-3 text-pink-400" />
            TÜFE REER Endeksi
          </span>
          <div className="mt-2">
            <span className="text-sm font-bold text-white">
              {data.components.reer.value.toFixed(1)}
            </span>
            <span className="text-[10px] block text-zinc-400 mt-0.5">
              Dengeli Bant (55-68)
            </span>
          </div>
        </div>
      </div>

      {/* Özet ve Değerlendirme */}
      <div className="p-3.5 rounded-xl bg-zinc-900/40 border border-zinc-800/60 text-xs text-zinc-300 leading-relaxed mb-4">
        {data.risk_summary}
      </div>

      {/* Alt Link */}
      {!compact && (
        <div className="flex items-center justify-between pt-2 border-t border-zinc-800/60 text-xs">
          <span className="text-zinc-500 font-mono text-[11px]">
            Son Güncelleme: {data.updated_at}
          </span>
          <Link
            href="/piyasa/devaluasyon-radari"
            className="text-amber-400 hover:text-amber-300 font-medium inline-flex items-center gap-1 transition-colors"
          >
            Kriz Kıyaslamaları & Hazine Terminali <ArrowRight className="w-3.5 h-3.5" />
          </Link>
        </div>
      )}
    </div>
  );
}
