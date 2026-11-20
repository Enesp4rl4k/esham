"use client";

import React from "react";
import Link from "next/link";
import { Scale, ArrowUpRight, TrendingUp, TrendingDown, Layers, CheckCircle2 } from "lucide-react";

interface PeerMetricItem {
  ticker: string;
  sirket: string;
  sektor: string;
  son_fiyat: number;
  piyasa_degeri_fmt: string;
  piyasa_degeri_tl: number;
  fiyat_kazanc_fk: number | null;
  piyasa_defter_pddd: number | null;
  fd_favok: number | null;
  roe: number | null;
  net_marj: number | null;
  dcf_adil_deger: number | null;
  dcf_potansiyel: number | null;
}

interface StockPeerComparisonCardProps {
  currentTicker: string;
  currentSector: string;
  quantData: Record<string, any>;
}

export function StockPeerComparisonCard({
  currentTicker,
  currentSector,
  quantData,
}: StockPeerComparisonCardProps) {
  if (!quantData || Object.keys(quantData).length === 0) return null;

  // 1. Aynı sektördeki hisseleri topla
  const peerList: PeerMetricItem[] = [];

  for (const [tick, d] of Object.entries(quantData)) {
    const f = d?.fundamental;
    const dcf = d?.dcf;
    const kl = d?.key_levels;

    peerList.push({
      ticker: tick,
      sirket: f?.sirket || tick,
      sektor: f?.sektor || "Genel BIST",
      son_fiyat: kl?.son_fiyat || dcf?.guncel_fiyat || 0,
      piyasa_degeri_fmt: f?.piyasa_degeri_fmt || "—",
      piyasa_degeri_tl: f?.piyasa_degeri_tl || 0,
      fiyat_kazanc_fk: f?.fiyat_kazanc_fk ?? null,
      piyasa_defter_pddd: f?.piyasa_defter_pddd ?? null,
      fd_favok: f?.fd_favok ?? null,
      roe: f?.ozsermaye_karliligi_roe ?? null,
      net_marj: f?.net_kar_marji_yuzde ?? null,
      dcf_adil_deger: dcf?.hisse_basina_adil_deger_try ?? null,
      dcf_potansiyel: dcf?.getiri_potansiyeli_yuzde ?? null,
    });
  }

  // Önce aynı sektördekiler
  let sectorPeers = peerList.filter((p) => p.sektor === currentSector);

  // Eğer sektörde 2'den az şirket varsa genel BIST-30 öncülerini ekle
  if (sectorPeers.length < 3) {
    const fallbackPeers = peerList.filter(
      (p) => p.ticker !== currentTicker && !sectorPeers.some((sp) => sp.ticker === p.ticker)
    );
    sectorPeers = [...sectorPeers, ...fallbackPeers.slice(0, 5 - sectorPeers.length)];
  }

  // Şu anki hisseyi listenin en başına veya içine al
  if (!sectorPeers.some((p) => p.ticker === currentTicker)) {
    const selfItem = peerList.find((p) => p.ticker === currentTicker);
    if (selfItem) sectorPeers.unshift(selfItem);
  }

  // Sektör Medyanı Hesabı
  const validPeers = sectorPeers.filter((p) => p.ticker !== currentTicker);
  const peVals = validPeers.map((p) => p.fiyat_kazanc_fk).filter((v): v is number => v !== null && v > 0);
  const pbVals = validPeers.map((p) => p.piyasa_defter_pddd).filter((v): v is number => v !== null && v > 0);
  const roeVals = validPeers.map((p) => p.roe).filter((v): v is number => v !== null);

  const median = (arr: number[]) => {
    if (arr.length === 0) return null;
    const sorted = [...arr].sort((a, b) => a - b);
    const mid = Math.floor(sorted.length / 2);
    return sorted.length % 2 !== 0 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2;
  };

  const medianPE = median(peVals);
  const medianPB = median(pbVals);
  const medianROE = median(roeVals);

  return (
    <div className="rounded-2xl border border-zinc-800 bg-zinc-950/80 p-6 backdrop-blur-sm shadow-xl space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-zinc-800/80">
        <div className="flex items-center gap-2">
          <span className="p-1.5 rounded-lg bg-sky-500/10 text-sky-400 border border-sky-500/20">
            <Scale className="w-4 h-4" />
          </span>
          <div>
            <h3 className="text-sm font-bold text-white tracking-tight">
              Sektörel Akran Değerleme Matrisi
            </h3>
            <p className="text-xs text-zinc-400 font-mono">
              {currentSector} sektörü çarpanları ve nispi değerleme kıyaslaması
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2 text-xs font-mono">
          {medianPE && (
            <span className="px-2.5 py-1 rounded bg-zinc-900 border border-zinc-800 text-zinc-400">
              Sektör F/K Medyanı: <strong className="text-white">{medianPE.toFixed(1)}x</strong>
            </span>
          )}
          {medianPB && (
            <span className="px-2.5 py-1 rounded bg-zinc-900 border border-zinc-800 text-zinc-400">
              PD/DD Medyanı: <strong className="text-white">{medianPB.toFixed(1)}x</strong>
            </span>
          )}
        </div>
      </div>

      {/* Tablo */}
      <div className="overflow-x-auto">
        <table className="w-full text-left border-collapse text-xs font-mono">
          <thead>
            <tr className="border-b border-zinc-800 text-zinc-400 text-xs uppercase tracking-wider">
              <th className="py-2.5 px-3">Hisse</th>
              <th className="py-2.5 px-3 text-right">Son Fiyat</th>
              <th className="py-2.5 px-3 text-right">Piyasa Değeri</th>
              <th className="py-2.5 px-3 text-right">F/K</th>
              <th className="py-2.5 px-3 text-right">PD/DD</th>
              <th className="py-2.5 px-3 text-right">FD/FAVÖK</th>
              <th className="py-2.5 px-3 text-right">ROE</th>
              <th className="py-2.5 px-3 text-right">Net Marj</th>
              <th className="py-2.5 px-3 text-right">DCF Potansiyeli</th>
              <th className="py-2.5 px-3 text-center">İncele</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-800/60">
            {sectorPeers.map((peer) => {
              const isCurrent = peer.ticker === currentTicker;
              const hasUpside = peer.dcf_potansiyel !== null && peer.dcf_potansiyel >= 0;

              return (
                <tr
                  key={peer.ticker}
                  className={`transition-colors ${
                    isCurrent
                      ? "bg-sky-500/10 font-semibold border-l-2 border-l-sky-400"
                      : "hover:bg-zinc-900/50"
                  }`}
                >
                  {/* Ticker */}
                  <td className="py-3 px-3">
                    <div className="flex items-center gap-1.5">
                      <span className={`font-bold ${isCurrent ? "text-sky-300" : "text-white"}`}>
                        ${peer.ticker}
                      </span>
                      {isCurrent && (
                        <span className="text-xs uppercase px-1.5 py-0.2 rounded bg-sky-400/20 text-sky-300 border border-sky-400/30">
                          Aktif
                        </span>
                      )}
                    </div>
                    <span className="text-xs text-zinc-400 block truncate max-w-[130px] font-sans">
                      {peer.sirket}
                    </span>
                  </td>

                  {/* Son Fiyat */}
                  <td className="py-3 px-3 text-right text-zinc-200">
                    {peer.son_fiyat ? `${peer.son_fiyat.toFixed(2)} ₺` : "—"}
                  </td>

                  {/* Piyasa Değeri */}
                  <td className="py-3 px-3 text-right text-zinc-400">
                    {peer.piyasa_degeri_fmt}
                  </td>

                  {/* F/K */}
                  <td className="py-3 px-3 text-right">
                    <span
                      className={
                        peer.fiyat_kazanc_fk
                          ? medianPE && peer.fiyat_kazanc_fk < medianPE
                            ? "text-emerald-400 font-bold"
                            : "text-zinc-300"
                          : "text-zinc-400"
                      }
                    >
                      {peer.fiyat_kazanc_fk ? `${peer.fiyat_kazanc_fk.toFixed(1)}x` : "—"}
                    </span>
                  </td>

                  {/* PD/DD */}
                  <td className="py-3 px-3 text-right">
                    <span
                      className={
                        peer.piyasa_defter_pddd
                          ? medianPB && peer.piyasa_defter_pddd < medianPB
                            ? "text-emerald-400 font-bold"
                            : "text-zinc-300"
                          : "text-zinc-400"
                      }
                    >
                      {peer.piyasa_defter_pddd ? `${peer.piyasa_defter_pddd.toFixed(1)}x` : "—"}
                    </span>
                  </td>

                  {/* FD/FAVÖK */}
                  <td className="py-3 px-3 text-right text-zinc-300">
                    {peer.fd_favok ? `${peer.fd_favok.toFixed(1)}x` : "—"}
                  </td>

                  {/* ROE */}
                  <td className="py-3 px-3 text-right">
                    <span
                      className={
                        peer.roe && peer.roe > 20
                          ? "text-emerald-400 font-bold"
                          : "text-zinc-400"
                      }
                    >
                      {peer.roe !== null ? `%${peer.roe.toFixed(1)}` : "—"}
                    </span>
                  </td>

                  {/* Net Marj */}
                  <td className="py-3 px-3 text-right text-zinc-300">
                    {peer.net_marj !== null ? `%${peer.net_marj.toFixed(1)}` : "—"}
                  </td>

                  {/* DCF Potansiyel */}
                  <td className="py-3 px-3 text-right">
                    {peer.dcf_potansiyel !== null ? (
                      <span
                        className={`font-bold ${
                          hasUpside ? "text-emerald-400" : "text-rose-400"
                        }`}
                      >
                        %{hasUpside ? "+" : ""}
                        {peer.dcf_potansiyel.toFixed(1)}
                      </span>
                    ) : (
                      <span className="text-zinc-400">—</span>
                    )}
                  </td>

                  {/* İncele Linki */}
                  <td className="py-3 px-3 text-center">
                    {isCurrent ? (
                      <span className="text-zinc-400">—</span>
                    ) : (
                      <Link
                        href={`/hisse/${peer.ticker}`}
                        className="inline-flex items-center gap-1 text-xs text-sky-400 hover:text-sky-300 transition-colors p-1 rounded hover:bg-sky-500/10"
                        title={`${peer.ticker} detaylı analizi`}
                      >
                        <span>İncele</span>
                        <ArrowUpRight className="w-3 h-3" />
                      </Link>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <div className="flex flex-col sm:flex-row sm:items-center justify-between text-xs text-zinc-400 font-mono gap-2 pt-2 border-t border-zinc-800/80">
        <span>* Yeşil renkli F/K ve PD/DD değerleri, sektör medyanına göre iskontolu çarpanı gösterir.</span>
        <span>Kaynak: Borsa İstanbul, KAP ve Esham Quant Modeli</span>
      </div>
    </div>
  );
}
