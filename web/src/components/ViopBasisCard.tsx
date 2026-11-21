import React from "react";
import { Activity } from "lucide-react";

export interface ViopBasisData {
  spot_xu030: number;
  vadeli_f_xu030: number;
  basis_puan: number;
  basis_yuzde: number;
  /** Kotasyonun alındığı an (ISO). Yoksa veri gösterilmez. */
  veri_tarihi?: string;
  degerlendirme?: string;
}

interface ViopBasisCardProps {
  data: ViopBasisData;
}

const nf = (v: number, d = 2) =>
  v.toLocaleString("tr-TR", { minimumFractionDigits: d, maximumFractionDigits: d });

function isNum(v: unknown): v is number {
  return typeof v === "number" && Number.isFinite(v);
}

export function ViopBasisCard({ data }: ViopBasisCardProps) {
  // Gerçek kotasyon (sayısal alanlar + veri tarihi) yoksa sayı göstermeyiz.
  const hasData =
    !!data &&
    isNum(data.spot_xu030) &&
    isNum(data.vadeli_f_xu030) &&
    isNum(data.basis_puan) &&
    isNum(data.basis_yuzde) &&
    !!data.veri_tarihi;
  const isContango = hasData && data.basis_puan >= 0;
  const asOf = hasData
    ? new Date(data.veri_tarihi as string).toLocaleString("tr-TR", { timeZone: "Europe/Istanbul" })
    : null;

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
              VİOP BIST 30 Basis
              <span className="text-xs font-mono px-2 py-0.5 rounded bg-zinc-900 border border-zinc-800 text-zinc-400">
                F_XU030
              </span>
            </h3>
            <p className="text-xs text-zinc-400 mt-0.5">Spot endeks ile vadeli kontrat arasındaki prim/iskonto</p>
          </div>
        </div>

        <span className="px-2.5 py-1 rounded-lg text-xs font-mono font-semibold bg-cyan-500/10 border border-cyan-500/30 text-cyan-400 shrink-0">
          {!hasData ? "Veri yok" : isContango ? "Contango (Vadeli Primli)" : "Backwardation (Vadeli İskontolu)"}
        </span>
      </div>

      {!hasData ? (
        <p className="text-xs text-zinc-400">
          Veri yok: VİOP spot/vadeli kotasyonu alınamadı. Eski veya örnek değer gösterilmez.
        </p>
      ) : (
        <>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs font-mono mb-5">
            <div className="bg-zinc-900/60 p-3.5 rounded-xl border border-zinc-800">
              <span className="text-xs text-zinc-400 block uppercase">Spot XU030</span>
              <span className="text-xl font-extrabold text-white block mt-1">{nf(data.spot_xu030)}</span>
            </div>
            <div className="bg-zinc-900/60 p-3.5 rounded-xl border border-zinc-800">
              <span className="text-xs text-zinc-400 block uppercase">Vadeli (XU030D)</span>
              <span className="text-xl font-extrabold text-white block mt-1">{nf(data.vadeli_f_xu030)}</span>
            </div>
            <div className="bg-zinc-900/60 p-3.5 rounded-xl border border-zinc-800">
              <span className="text-xs text-zinc-400 block uppercase">Basis</span>
              <span className="text-xl font-extrabold text-white block mt-1">
                {data.basis_puan > 0 ? "+" : ""}
                {nf(data.basis_puan)} puan
              </span>
              <span className="text-xs text-cyan-400 block mt-1.5 font-sans">
                {data.basis_yuzde > 0 ? "+" : ""}%{nf(data.basis_yuzde)}
              </span>
            </div>
          </div>

          <div className="pt-3 border-t border-zinc-800/80 text-xs text-zinc-400 leading-relaxed">
            {data.degerlendirme && <p className="mb-1.5">{data.degerlendirme}</p>}
            <p className="font-mono">Veri tarihi: {asOf}</p>
          </div>
        </>
      )}
    </div>
  );
}
