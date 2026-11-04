"use client";

import React from "react";
import { RefreshCcw, Calendar, TrendingUp, TrendingDown, DollarSign, ShieldCheck, CheckCircle2 } from "lucide-react";

export interface BuybackProgram {
  ticker: string;
  sirket: string;
  ayrilan_fon_tl: number;
  ayrilan_fon_fmt: string;
  azami_lot: number;
  geri_alinan_lot: number;
  tamamlanma_orani_yuzde: number;
  sermayeye_orani_yuzde: number;
  ortalama_maliyet_tl: number;
  guncel_fiyat_tl: number;
  maliyete_gore_getiri_yuzde: number;
  yetki_tarihi: string;
  durum: string;
  amac: string;
}

export interface DividendRecord {
  ticker: string;
  sirket: string;
  brut_temettu_tl: number;
  net_temettu_tl: number;
  temettu_verimi_yuzde: number;
  hak_kullanim_tarihi: string;
  odeme_tarihi: string;
  kar_dagitim_orani_yuzde: number;
  durum: string;
}

interface StockCorporateActionsCardProps {
  ticker: string;
  buyback?: BuybackProgram | null;
  dividend?: DividendRecord | null;
}

export function StockCorporateActionsCard({
  ticker,
  buyback,
  dividend,
}: StockCorporateActionsCardProps) {
  if (!buyback && !dividend) {
    return (
      <div className="rounded-2xl border border-zinc-800 bg-zinc-950/80 p-6 backdrop-blur-sm shadow-xl">
        <div className="flex items-center gap-2 pb-4 border-b border-zinc-800/80 mb-4">
          <span className="p-1.5 rounded-lg bg-zinc-900 text-zinc-400 border border-zinc-800">
            <ShieldCheck className="w-4 h-4" />
          </span>
          <h3 className="text-sm font-bold text-white tracking-tight">
            Kurumsal Sermaye Eylemleri (Geri Alım & Temettü)
          </h3>
        </div>
        <p className="text-xs text-zinc-400 leading-relaxed font-mono">
          ${ticker} için KAP sisteminde kayıtlı güncel bir pay geri alım programı veya kesinleşmiş kâr dağıtım takvimi bulunmamaktadır. Şirket genel kurul kararları ve yönetim kurulu bildirimleri anlık taranmaktadır.
        </p>
      </div>
    );
  }

  const isBuybackProfitable = buyback ? buyback.maliyete_gore_getiri_yuzde >= 0 : false;

  return (
    <div className="rounded-2xl border border-zinc-800 bg-zinc-950/80 p-6 backdrop-blur-sm shadow-xl space-y-6">
      {/* Başlık */}
      <div className="flex items-center justify-between pb-4 border-b border-zinc-800/80">
        <div className="flex items-center gap-2">
          <span className="p-1.5 rounded-lg bg-amber-500/10 text-amber-400 border border-amber-500/20">
            <RefreshCcw className="w-4 h-4" />
          </span>
          <div>
            <h3 className="text-sm font-bold text-white tracking-tight">
              Kurumsal Sermaye Eylemleri
            </h3>
            <p className="text-[11px] text-zinc-500 font-mono">
              Pay geri alım fonu ve nakit kâr payı dağıtım parametreleri
            </p>
          </div>
        </div>
        <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-zinc-900 border border-zinc-800 text-zinc-400">
          KAP Doğrulamalı
        </span>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* 1. Pay Geri Alım Kartı */}
        {buyback ? (
          <div className="rounded-xl border border-zinc-800/90 bg-zinc-900/50 p-4 space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
                <span className="text-xs font-bold text-zinc-200 uppercase tracking-wider font-mono">
                  Aktif Pay Geri Alım Programı
                </span>
              </div>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                {buyback.durum}
              </span>
            </div>

            {/* İlerleme Çubuğu */}
            <div>
              <div className="flex justify-between text-[11px] font-mono text-zinc-400 mb-1.5">
                <span>Tamamlanma Oranı</span>
                <span className="text-white font-bold">%{buyback.tamamlanma_orani_yuzde.toFixed(1)}</span>
              </div>
              <div className="w-full h-2 bg-zinc-800 rounded-full overflow-hidden">
                <div
                  className="h-full bg-gradient-to-r from-emerald-500 to-cyan-400 transition-all duration-500"
                  style={{ width: `${Math.min(100, buyback.tamamlanma_orani_yuzde)}%` }}
                />
              </div>
            </div>

            {/* Metrikler Grid */}
            <div className="grid grid-cols-2 gap-2 text-xs font-mono">
              <div className="bg-zinc-950/70 p-2.5 rounded-lg border border-zinc-800/80">
                <span className="text-[10px] text-zinc-500 block uppercase">Tahsis Edilen Fon</span>
                <span className="font-bold text-white mt-0.5 block">{buyback.ayrilan_fon_fmt}</span>
              </div>
              <div className="bg-zinc-950/70 p-2.5 rounded-lg border border-zinc-800/80">
                <span className="text-[10px] text-zinc-500 block uppercase">Geri Alınan Pay</span>
                <span className="font-bold text-zinc-200 mt-0.5 block">
                  {(buyback.geri_alinan_lot / 1_000_000).toFixed(1)}M Lot
                </span>
              </div>
              <div className="bg-zinc-950/70 p-2.5 rounded-lg border border-zinc-800/80">
                <span className="text-[10px] text-zinc-500 block uppercase">Ortalama Maliyet</span>
                <span className="font-bold text-zinc-300 mt-0.5 block">
                  {buyback.ortalama_maliyet_tl.toFixed(2)} ₺
                </span>
              </div>
              <div className="bg-zinc-950/70 p-2.5 rounded-lg border border-zinc-800/80">
                <span className="text-[10px] text-zinc-500 block uppercase">Maliyet Performansı</span>
                <span
                  className={`font-bold mt-0.5 block ${
                    isBuybackProfitable ? "text-emerald-400" : "text-rose-400"
                  }`}
                >
                  %{buyback.maliyete_gore_getiri_yuzde >= 0 ? "+" : ""}
                  {buyback.maliyete_gore_getiri_yuzde.toFixed(1)}
                </span>
              </div>
            </div>

            {buyback.amac && (
              <p className="text-[11px] text-zinc-400 bg-zinc-950/50 p-2 rounded border border-zinc-800/60 leading-relaxed">
                <span className="text-zinc-500 font-mono mr-1">Amaç:</span>
                {buyback.amac}
              </p>
            )}
          </div>
        ) : (
          <div className="rounded-xl border border-zinc-800/60 bg-zinc-900/30 p-5 flex flex-col justify-center items-center text-center">
            <RefreshCcw className="w-8 h-8 text-zinc-600 mb-2" />
            <span className="text-xs font-semibold text-zinc-300">Aktif Geri Alım Yok</span>
            <span className="text-[11px] text-zinc-500 mt-1">
              Şirket adına açılmış yürürlükte bir hisse geri alım programı bildirilmemiştir.
            </span>
          </div>
        )}

        {/* 2. Temettü Kartı */}
        {dividend ? (
          <div className="rounded-xl border border-zinc-800/90 bg-zinc-900/50 p-4 space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Calendar className="w-4 h-4 text-amber-400" />
                <span className="text-xs font-bold text-zinc-200 uppercase tracking-wider font-mono">
                  Nakit Kâr Payı (Temettü)
                </span>
              </div>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-amber-500/10 text-amber-300 border border-amber-500/20">
                {dividend.durum}
              </span>
            </div>

            {/* Verim Vurgusu */}
            <div className="flex items-center justify-between bg-zinc-950/80 p-3 rounded-lg border border-zinc-800">
              <div>
                <span className="text-[10px] text-zinc-500 block uppercase font-mono">Temettü Verimi</span>
                <span className="text-xs text-zinc-400">Son Fiyata Göre Net Getiri</span>
              </div>
              <span className="text-xl font-mono font-black text-amber-400">
                %{dividend.temettu_verimi_yuzde.toFixed(2)}
              </span>
            </div>

            {/* Temettü Detay Grid */}
            <div className="grid grid-cols-2 gap-2 text-xs font-mono">
              <div className="bg-zinc-950/70 p-2.5 rounded-lg border border-zinc-800/80">
                <span className="text-[10px] text-zinc-500 block uppercase">Hisse Başı Net</span>
                <span className="font-bold text-emerald-400 mt-0.5 block">
                  {dividend.net_temettu_tl.toFixed(2)} ₺
                </span>
              </div>
              <div className="bg-zinc-950/70 p-2.5 rounded-lg border border-zinc-800/80">
                <span className="text-[10px] text-zinc-500 block uppercase">Hisse Başı Brüt</span>
                <span className="font-bold text-zinc-300 mt-0.5 block">
                  {dividend.brut_temettu_tl.toFixed(2)} ₺
                </span>
              </div>
              <div className="bg-zinc-950/70 p-2.5 rounded-lg border border-zinc-800/80">
                <span className="text-[10px] text-zinc-500 block uppercase">Hak Kullanım</span>
                <span className="font-bold text-zinc-300 mt-0.5 block">
                  {dividend.hak_kullanim_tarihi}
                </span>
              </div>
              <div className="bg-zinc-950/70 p-2.5 rounded-lg border border-zinc-800/80">
                <span className="text-[10px] text-zinc-500 block uppercase">Hesaba Geçiş</span>
                <span className="font-bold text-zinc-300 mt-0.5 block">
                  {dividend.odeme_tarihi}
                </span>
              </div>
            </div>

            <div className="flex items-center justify-between text-[11px] font-mono text-zinc-400 px-1 pt-1">
              <span>Dağıtım Oranı (Payout)</span>
              <span className="text-white font-semibold">%{dividend.kar_dagitim_orani_yuzde.toFixed(1)}</span>
            </div>
          </div>
        ) : (
          <div className="rounded-xl border border-zinc-800/60 bg-zinc-900/30 p-5 flex flex-col justify-center items-center text-center">
            <Calendar className="w-8 h-8 text-zinc-600 mb-2" />
            <span className="text-xs font-semibold text-zinc-300">Açıklanmış Temettü Yok</span>
            <span className="text-[11px] text-zinc-500 mt-1">
              Mevcut takvim dönemi için genel kurul onaylı kâr payı tarihi ilan edilmemiştir.
            </span>
          </div>
        )}
      </div>
    </div>
  );
}
