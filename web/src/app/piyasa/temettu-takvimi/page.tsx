import React from "react";
import Link from "next/link";
import type { Metadata } from "next";
import { promises as fs } from "fs";
import path from "path";
import {
  ArrowLeft,
  Calendar,
  Percent,
  TrendingUp,
  ArrowUpRight,
  Info,
  DollarSign,
  Award,
} from "lucide-react";

export const metadata: Metadata = {
  title: "BIST Temettü Takvimi & Temettü Verimi Sıralaması | Esham",
  description:
    "Borsa İstanbul şirketlerinin güncel temettü dağıtım takvimi, hak kullanım tarihleri, hisse başına net nakit kâr payı ve temettü verimi sıralaması.",
  alternates: {
    canonical: "https://esham.pages.dev/piyasa/temettu-takvimi",
  },
  keywords: [
    "Temettü Takvimi",
    "Temettü Verimi",
    "BIST Temettü",
    "Kâr Payı Dağıtımı",
    "Temettü Tarihleri",
    "Temettü Hisseleri",
  ],
};

async function loadDividendsData() {
  try {
    const filePath = path.join(process.cwd(), "public", "data", "bist-dividends.json");
    const raw = await fs.readFile(filePath, "utf-8");
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

export default async function DividendsPage() {
  const data = await loadDividendsData();
  const records = data?.records || [];
  const avgYield = data?.avg_yield_pct || 0;

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
        <span className="text-emerald-400 font-mono font-semibold">Temettü Takvimi</span>
      </div>

      {/* Hero Header */}
      <div className="rounded-2xl border border-zinc-800 bg-zinc-950/80 p-6 md:p-8 mb-10 relative overflow-hidden backdrop-blur-sm">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-6">
          <div>
            <div className="flex items-center gap-2.5 mb-2">
              <span className="p-2 rounded-xl bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                <Percent className="w-5 h-5" />
              </span>
              <span className="text-xs font-mono font-semibold uppercase tracking-wider px-2.5 py-1 rounded bg-zinc-900 border border-zinc-800 text-zinc-400">
                2026 Dağıtım Dönemi
              </span>
            </div>
            <h1 className="text-2xl md:text-3xl font-extrabold text-white tracking-tight">
              BIST Temettü Dağıtım Takvimi & Verim Sıralaması
            </h1>
            <p className="text-sm text-zinc-400 mt-1 max-w-2xl">
              Nakit kâr payı dağıtan BIST şirketlerinin hak kullanım (ex-date) tarihleri,
              hisse başına net ödeme tutarları ve yıllıklandırılmış temettü verimleri.
            </p>
          </div>

          <div className="bg-zinc-900/80 border border-zinc-800 rounded-xl p-4 min-w-[220px]">
            <span className="text-[10px] font-bold uppercase tracking-wider text-zinc-500 block">
              Ortalama Temettü Verimi
            </span>
            <span className="text-2xl font-mono font-bold text-emerald-400 mt-1 block">
              %{avgYield}
            </span>
            <span className="text-[11px] font-mono text-zinc-400 mt-0.5 block">
              {records.length} Şirket Açıklaması
            </span>
          </div>
        </div>
      </div>

      {/* Temettü Tablosu */}
      <div className="rounded-2xl border border-zinc-800 bg-zinc-950/90 overflow-hidden shadow-2xl mb-10">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs font-mono">
            <thead className="bg-zinc-900/80 border-b border-zinc-800 text-[11px] uppercase tracking-wider text-zinc-400">
              <tr>
                <th className="py-4 px-5">Şirket / Kod</th>
                <th className="py-4 px-4">Temettü Verimi</th>
                <th className="py-4 px-4">Net Tutar (TL)</th>
                <th className="py-4 px-4">Brüt Tutar (TL)</th>
                <th className="py-4 px-4">Hak Kullanım (Ex-Date)</th>
                <th className="py-4 px-4">Hesaba Geçiş</th>
                <th className="py-4 px-4">Dağıtım Oranı</th>
                <th className="py-4 px-4 text-right">Detay</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-800/80">
              {records.map((r: any) => (
                <tr key={r.ticker} className="hover:bg-zinc-900/50 transition-colors">
                  <td className="py-4 px-5">
                    <div className="flex items-center gap-2.5">
                      <span className="text-sm font-bold text-white">${r.ticker}</span>
                      <span className="text-xs font-sans text-zinc-400 truncate max-w-[140px] md:max-w-[200px]">
                        {r.sirket}
                      </span>
                    </div>
                  </td>
                  <td className="py-4 px-4">
                    <span className="px-2 py-0.5 rounded text-xs font-bold bg-emerald-500/10 border border-emerald-500/30 text-emerald-400">
                      %{r.temettu_verimi_yuzde.toFixed(1)}
                    </span>
                  </td>
                  <td className="py-4 px-4 font-bold text-white">
                    {r.net_temettu_tl.toFixed(2)} ₺
                  </td>
                  <td className="py-4 px-4 text-zinc-400">
                    {r.brut_temettu_tl.toFixed(2)} ₺
                  </td>
                  <td className="py-4 px-4 text-zinc-200">
                    <div className="flex items-center gap-1.5">
                      <Calendar className="w-3.5 h-3.5 text-zinc-500" />
                      <span>{r.hak_kullanim_tarihi}</span>
                    </div>
                  </td>
                  <td className="py-4 px-4 text-zinc-400">
                    {r.odeme_tarihi}
                  </td>
                  <td className="py-4 px-4 text-zinc-300">
                    %{r.kar_dagitim_orani_yuzde.toFixed(1)}
                  </td>
                  <td className="py-4 px-4 text-right">
                    <Link
                      href={`/hisse/${r.ticker}`}
                      className="inline-flex items-center gap-1 text-[11px] text-emerald-400 hover:text-emerald-300 transition-colors font-sans"
                    >
                      Terminal <ArrowUpRight className="w-3.5 h-3.5" />
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Bilgilendirme Kutusu */}
      <div className="p-6 rounded-2xl border border-zinc-800 bg-zinc-950/60 flex items-start gap-3.5 text-xs text-zinc-400">
        <Info className="w-5 h-5 text-emerald-400 shrink-0 mt-0.5" />
        <div>
          <h4 className="font-bold text-white mb-1">Temettü Hak Kullanımı ve Stopaj</h4>
          <p>
            Temettüden yararlanabilmek için hak kullanım (ex-dividend) tarihinden bir önceki işlem günü seans kapanışında hisseye sahip olunması gerekmektedir.
            Bireysel yatırımcılar için %10 stopaj kesintisi düşülmüş net tutarlar tabloda gösterilmektedir.
          </p>
        </div>
      </div>
    </div>
  );
}
