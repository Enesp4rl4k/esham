import React from "react";
import Link from "next/link";
import type { Metadata } from "next";
import { promises as fs } from "fs";
import path from "path";
import {
  ArrowLeft,
  ShieldCheck,
  TrendingUp,
  TrendingDown,
  PieChart,
  Coins,
  ArrowUpRight,
  Info,
  Calendar,
} from "lucide-react";

export const metadata: Metadata = {
  title: "BIST Aktif Pay Geri Alım (Share Buyback) Programları | Esham",
  description:
    "Borsa İstanbul şirketlerinin KAP'a bildirdikleri aktif hisse geri alım fonları, gerçekleşen pay alımları ve ortalama maliyet tablosu.",
};

async function loadBuybacksData() {
  try {
    const filePath = path.join(process.cwd(), "public", "data", "bist-buybacks.json");
    const raw = await fs.readFile(filePath, "utf-8");
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

export default async function BuybacksPage() {
  const data = await loadBuybacksData();
  const programs = data?.programs || [];
  const totalFund = data?.total_allocated_fund_try || 0;

  return (
    <div className="container mx-auto px-6 py-12 max-w-6xl">
      {/* Breadcrumb */}
      <div className="flex items-center gap-3 mb-8 text-xs text-zinc-500">
        <Link href="/" className="inline-flex items-center gap-1.5 hover:text-white transition-colors">
          <ArrowLeft className="w-3.5 h-3.5" /> Ana Sayfa
        </Link>
        <span>/</span>
        <span className="text-zinc-300 font-semibold">Piyasa Göstergeleri</span>
        <span>/</span>
        <span className="text-cyan-400 font-mono font-semibold">Pay Geri Alımları</span>
      </div>

      {/* Hero Header */}
      <div className="rounded-2xl border border-zinc-800 bg-zinc-950/80 p-6 md:p-8 mb-10 relative overflow-hidden backdrop-blur-sm">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-6">
          <div>
            <div className="flex items-center gap-2.5 mb-2">
              <span className="p-2 rounded-xl bg-cyan-500/10 text-cyan-400 border border-cyan-500/20">
                <Coins className="w-5 h-5" />
              </span>
              <span className="text-xs font-mono font-semibold uppercase tracking-wider px-2.5 py-1 rounded bg-zinc-900 border border-zinc-800 text-zinc-400">
                SPK II-22.1 Tebliği Uyumlu
              </span>
            </div>
            <h1 className="text-2xl md:text-3xl font-extrabold text-white tracking-tight">
              BIST Aktif Pay Geri Alım (Share Buyback) Radarı
            </h1>
            <p className="text-sm text-zinc-400 mt-1 max-w-2xl">
              Şirket yönetimlerinin kendi hisselerine duyduğu güvenin en somut göstergesi:
              Yetkilendirilen fon büyüklüğü, gerçekleşen alımlar ve piyasa kâr/zarar oranları.
            </p>
          </div>

          <div className="bg-zinc-900/80 border border-zinc-800 rounded-xl p-4 min-w-[220px]">
            <span className="text-[10px] font-bold uppercase tracking-wider text-zinc-500 block">
              Toplam Yetkili Fon Büyüklüğü
            </span>
            <span className="text-2xl font-mono font-bold text-cyan-400 mt-1 block">
              {(totalFund / 1_000_000_000).toFixed(1)} Milyar TL
            </span>
            <span className="text-[11px] font-mono text-zinc-400 mt-0.5 block">
              {programs.length} Aktif Şirket Programı
            </span>
          </div>
        </div>
      </div>

      {/* Geri Alım Tablosu */}
      <div className="rounded-2xl border border-zinc-800 bg-zinc-950/90 overflow-hidden shadow-2xl mb-10">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs font-mono">
            <thead className="bg-zinc-900/80 border-b border-zinc-800 text-[11px] uppercase tracking-wider text-zinc-400">
              <tr>
                <th className="py-4 px-5">Şirket / Kod</th>
                <th className="py-4 px-4">Ayrılan Fon</th>
                <th className="py-4 px-4">İlerleme (%)</th>
                <th className="py-4 px-4">Sermaye Payı</th>
                <th className="py-4 px-4">Ort. Maliyet</th>
                <th className="py-4 px-4">Güncel Fiyat</th>
                <th className="py-4 px-4">Getiri / Fark</th>
                <th className="py-4 px-4 text-right">Detay</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-800/80">
              {programs.map((p: any) => {
                const isProfitable = p.maliyete_gore_getiri_yuzde >= 0;
                return (
                  <tr key={p.ticker} className="hover:bg-zinc-900/50 transition-colors">
                    <td className="py-4 px-5">
                      <div className="flex items-center gap-2.5">
                        <span className="text-sm font-bold text-white">${p.ticker}</span>
                        <span className="text-xs font-sans text-zinc-400 truncate max-w-[140px] md:max-w-[200px]">
                          {p.sirket}
                        </span>
                      </div>
                    </td>
                    <td className="py-4 px-4 font-semibold text-zinc-200">
                      {p.ayrilan_fon_fmt}
                    </td>
                    <td className="py-4 px-4 min-w-[140px]">
                      <div className="flex items-center gap-2">
                        <span className="font-bold text-white">%{p.tamamlanma_orani_yuzde}</span>
                      </div>
                      <div className="w-full bg-zinc-800 h-1.5 rounded-full mt-1.5 overflow-hidden">
                        <div
                          className="bg-cyan-500 h-full rounded-full transition-all"
                          style={{ width: `${Math.min(100, p.tamamlanma_orani_yuzde)}%` }}
                        />
                      </div>
                    </td>
                    <td className="py-4 px-4 text-zinc-300">
                      %{p.sermayeye_orani_yuzde.toFixed(2)}
                    </td>
                    <td className="py-4 px-4 text-zinc-400">
                      {p.ortalama_maliyet_tl.toFixed(2)} ₺
                    </td>
                    <td className="py-4 px-4 font-bold text-white">
                      {p.guncel_fiyat_tl.toFixed(2)} ₺
                    </td>
                    <td className="py-4 px-4">
                      <span
                        className={`inline-flex items-center gap-1 font-bold ${
                          isProfitable ? "text-emerald-400" : "text-rose-400"
                        }`}
                      >
                        {isProfitable ? <TrendingUp className="w-3.5 h-3.5" /> : <TrendingDown className="w-3.5 h-3.5" />}
                        %{Math.abs(p.maliyete_gore_getiri_yuzde).toFixed(1)}
                      </span>
                    </td>
                    <td className="py-4 px-4 text-right">
                      <Link
                        href={`/hisse/${p.ticker}`}
                        className="inline-flex items-center gap-1 text-[11px] text-cyan-400 hover:text-cyan-300 transition-colors font-sans"
                      >
                        Terminal <ArrowUpRight className="w-3.5 h-3.5" />
                      </Link>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* Stratejik Analist Notu */}
      <div className="p-6 rounded-2xl border border-zinc-800 bg-zinc-950/60 flex items-start gap-3.5 text-xs text-zinc-400">
        <Info className="w-5 h-5 text-cyan-400 shrink-0 mt-0.5" />
        <div>
          <h4 className="font-bold text-white mb-1">Pay Geri Alımının Kurumsal Anlamı</h4>
          <p>
            Şirketlerin kendi paylarını borsadan geri alması, dolaşımdaki hisse adedini azaltarak hisse başına düşen kârı (EPS) artırır
            ve sermaye piyasalarında taban fiyat desteği sağlar. Şirketin geri alım ortalama maliyetinin altında işlem gören hisseler,
            tarihsel olarak kurumsal yatırımcılar için güçlü bir güvenlik marjı (margin of safety) sunar.
          </p>
        </div>
      </div>
    </div>
  );
}
