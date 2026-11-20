"use client";

import React, { useState } from "react";
import {
  ShieldCheck,
  ShieldAlert,
  Activity,
  CheckCircle2,
  XCircle,
  HelpCircle,
  Info,
  Layers,
  ArrowRight,
  TrendingUp,
} from "lucide-react";

export interface PiotroskiCriterion {
  kod: string;
  kategori: string;
  aciklama: string;
  gecerli: boolean;
  deger: string;
}

export interface FinancialHealthData {
  ticker: string;
  sirket: string;
  piotroski_skor: number;
  piotroski_degerlendirme: string;
  piotroski_kriterler: PiotroskiCriterion[];
  altman_z_skor: number;
  altman_bolge: string;
  altman_bilesenler: Record<string, number>;
  dupont_analizi: {
    net_kar_marji: number;
    aktif_devir_hizi: number;
    kaldirac_carpani: number;
    hesaplanan_roe: number;
  };
  ozet: string;
}

interface FinancialHealthCardProps {
  health: FinancialHealthData;
}

export function FinancialHealthCard({ health }: FinancialHealthCardProps) {
  const [activeTab, setActiveTab] = useState<"piotroski" | "dupont" | "altman">("piotroski");

  const score = health.piotroski_skor;
  const isStrong = score >= 6;
  const isModerate = score >= 4 && score < 6;

  // Altman Z Zone Colors
  const z = health.altman_z_skor;
  const isZSafe = z >= 2.99;
  const isZGrey = z >= 1.81 && z < 2.99;

  const dupont = health.dupont_analizi || {
    net_kar_marji: 0,
    aktif_devir_hizi: 0,
    kaldirac_carpani: 1,
    hesaplanan_roe: 0,
  };

  // Group criteria by category
  const categories = [
    { name: "Kârlılık (Profitability)", filter: (c: PiotroskiCriterion) => c.kategori.includes("Karl") },
    { name: "Kaldıraç & Likidite", filter: (c: PiotroskiCriterion) => c.kategori.includes("Kaldir") || c.kategori.includes("Likidite") },
    { name: "Operasyonel Verimlilik", filter: (c: PiotroskiCriterion) => c.kategori.includes("Verim") },
  ];

  return (
    <div className="rounded-2xl border border-zinc-800 bg-zinc-950/90 p-6 md:p-8 backdrop-blur-md shadow-2xl">
      {/* Başlık ve Durum Rozeti */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-6 border-b border-zinc-800 gap-4 mb-6">
        <div>
          <div className="flex items-center gap-2.5">
            <span className="p-2 rounded-xl bg-cyan-500/10 text-cyan-400 border border-cyan-500/20">
              <ShieldCheck className="w-5 h-5" />
            </span>
            <div>
              <h3 className="text-lg font-bold text-white tracking-tight flex items-center gap-2">
                Kurumsal Finansal Sağlık & Skor Kartı
                <span className="text-xs px-2 py-0.5 rounded-full font-mono bg-zinc-900 border border-zinc-800 text-zinc-400">
                  TMS Standartları
                </span>
              </h3>
              <p className="text-xs text-zinc-400 mt-0.5">
                Piotroski F-Score (0-9), Altman Z İflas Riski ve 3 Aşamalı DuPont kârlılık analizi
              </p>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          <span
            className={`px-3 py-1.5 rounded-lg text-xs font-mono font-semibold border ${
              isStrong
                ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-400"
                : isModerate
                ? "bg-amber-500/10 border-amber-500/30 text-amber-400"
                : "bg-rose-500/10 border-rose-500/30 text-rose-400"
            }`}
          >
            {health.piotroski_degerlendirme}
          </span>
        </div>
      </div>

      {/* 3 Büyük KPI Kutusu */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
        {/* 1. Piotroski F-Score */}
        <div className="p-4 rounded-xl border border-zinc-800 bg-zinc-900/40 relative overflow-hidden">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-bold uppercase tracking-wider text-zinc-400">
              Piotroski F-Skoru
            </span>
            <span className="text-xs font-mono text-zinc-400">9 Kriter</span>
          </div>
          <div className="flex items-baseline gap-2">
            <span
              className={`text-3xl font-extrabold font-mono ${
                isStrong ? "text-emerald-400" : isModerate ? "text-amber-400" : "text-rose-400"
              }`}
            >
              {score}
            </span>
            <span className="text-zinc-400 text-sm font-mono">/ 9</span>
          </div>

          {/* 9 Segmentli Bar */}
          <div className="grid grid-cols-9 gap-1 mt-3">
            {Array.from({ length: 9 }).map((_, i) => (
              <div
                key={i}
                className={`h-1.5 rounded-full transition-all ${
                  i < score
                    ? isStrong
                      ? "bg-emerald-500"
                      : isModerate
                      ? "bg-amber-500"
                      : "bg-rose-500"
                    : "bg-zinc-800"
                }`}
              />
            ))}
          </div>
          <p className="text-xs text-zinc-400 mt-2 line-clamp-1">
            {isStrong
              ? "Sağlam bilanço ve operasyonel nakit üretimi."
              : isModerate
              ? "Dengeli mali yapı, seçici göstergeler izlenmeli."
              : "Bilanço baskısı, borçluluk yakından izlenmeli."}
          </p>
        </div>

        {/* 2. Altman Z-Score */}
        <div className="p-4 rounded-xl border border-zinc-800 bg-zinc-900/40">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-bold uppercase tracking-wider text-zinc-400">
              Altman Z-Skoru
            </span>
            <span
              className={`text-xs px-2 py-0.5 rounded font-mono font-semibold ${
                isZSafe
                  ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                  : isZGrey
                  ? "bg-amber-500/10 text-amber-400 border border-amber-500/20"
                  : "bg-rose-500/10 text-rose-400 border border-rose-500/20"
              }`}
            >
              {isZSafe ? "Güvenli" : isZGrey ? "Gri Bölge" : "Riskli"}
            </span>
          </div>
          <div className="flex items-baseline gap-2">
            <span
              className={`text-3xl font-extrabold font-mono ${
                isZSafe ? "text-emerald-400" : isZGrey ? "text-amber-400" : "text-rose-400"
              }`}
            >
              {z > 0 ? z.toFixed(2) : "—"}
            </span>
            <span className="text-zinc-400 text-xs font-mono">Eşik: 2.99</span>
          </div>

          {/* Mini Kadran Görseli */}
          <div className="h-1.5 w-full bg-zinc-800 rounded-full mt-3 overflow-hidden flex">
            <div className="w-[33%] bg-rose-500/60" />
            <div className="w-[33%] bg-amber-500/60" />
            <div className="w-[34%] bg-emerald-500/60" />
          </div>
          <div className="flex justify-between text-xs font-mono text-zinc-400 mt-1">
            <span>&lt;1.81 İflas Riski</span>
            <span>1.81-2.99 Gri</span>
            <span>&gt;2.99 Güvenli</span>
          </div>
        </div>

        {/* 3. DuPont 3 Aşamalı ROE */}
        <div className="p-4 rounded-xl border border-zinc-800 bg-zinc-900/40">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-bold uppercase tracking-wider text-zinc-400">
              DuPont Hesaplanmış ROE
            </span>
            <span className="text-xs font-mono text-cyan-400">Sermaye Verimi</span>
          </div>
          <div className="flex items-baseline gap-2">
            <span className="text-3xl font-extrabold font-mono text-cyan-400">
              %{dupont.hesaplanan_roe.toFixed(1)}
            </span>
            <span className="text-zinc-400 text-xs font-mono">Yıllık</span>
          </div>

          <div className="mt-3 flex items-center justify-between text-xs font-mono text-zinc-400 border-t border-zinc-800 pt-2">
            <div>
              <span className="text-zinc-400 block text-xs">KÂR MARJI</span>
              <span>%{dupont.net_kar_marji.toFixed(1)}</span>
            </div>
            <span className="text-zinc-400">×</span>
            <div>
              <span className="text-zinc-400 block text-xs">DEVİR HIZI</span>
              <span>{dupont.aktif_devir_hizi.toFixed(2)}x</span>
            </div>
            <span className="text-zinc-400">×</span>
            <div>
              <span className="text-zinc-400 block text-xs">KALDIRAÇ</span>
              <span>{dupont.kaldirac_carpani.toFixed(2)}x</span>
            </div>
          </div>
        </div>
      </div>

      {/* Sekmeler (Tablar): Piotroski Kriterleri vs DuPont Görseli */}
      <div className="flex border-b border-zinc-800 mb-6 gap-2">
        <button
          onClick={() => setActiveTab("piotroski")}
          className={`pb-3 text-xs font-bold tracking-wider uppercase transition-all border-b-2 px-3 ${
            activeTab === "piotroski"
              ? "border-cyan-500 text-cyan-400"
              : "border-transparent text-zinc-400 hover:text-white"
          }`}
        >
          Piotroski Kriter Analizi (9/9)
        </button>
        <button
          onClick={() => setActiveTab("dupont")}
          className={`pb-3 text-xs font-bold tracking-wider uppercase transition-all border-b-2 px-3 ${
            activeTab === "dupont"
              ? "border-cyan-500 text-cyan-400"
              : "border-transparent text-zinc-400 hover:text-white"
          }`}
        >
          DuPont 3 Aşamalı Ayrıştırma
        </button>
        <button
          onClick={() => setActiveTab("altman")}
          className={`pb-3 text-xs font-bold tracking-wider uppercase transition-all border-b-2 px-3 ${
            activeTab === "altman"
              ? "border-cyan-500 text-cyan-400"
              : "border-transparent text-zinc-400 hover:text-white"
          }`}
        >
          Altman Z Bileşenleri
        </button>
      </div>

      {/* Tab İçeriği: Piotroski Kriterleri */}
      {activeTab === "piotroski" && (
        <div className="space-y-6">
          {categories.map((cat, idx) => {
            const list = (health.piotroski_kriterler || []).filter(cat.filter);
            if (list.length === 0) return null;

            return (
              <div key={idx} className="rounded-xl border border-zinc-800/80 bg-zinc-900/30 p-4">
                <h4 className="text-xs font-bold font-mono uppercase tracking-wider text-zinc-400 mb-3 flex items-center justify-between">
                  <span>{cat.name}</span>
                  <span className="text-xs text-zinc-400">
                    {list.filter((c) => c.gecerli).length} / {list.length} Puan
                  </span>
                </h4>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-2.5">
                  {list.map((crit, cIdx) => (
                    <div
                      key={cIdx}
                      className={`p-3 rounded-lg border text-xs flex items-start gap-3 transition-colors ${
                        crit.gecerli
                          ? "bg-emerald-500/5 border-emerald-500/20 text-zinc-200"
                          : "bg-zinc-900/60 border-zinc-800/80 text-zinc-400"
                      }`}
                    >
                      <span className="mt-0.5 shrink-0">
                        {crit.gecerli ? (
                          <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                        ) : (
                          <XCircle className="w-4 h-4 text-zinc-400" />
                        )}
                      </span>
                      <div className="min-w-0 flex-1">
                        <span className="font-medium text-white block">{crit.aciklama}</span>
                        <span className="text-xs font-mono text-zinc-400 block mt-0.5">
                          Metrik: {crit.deger}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Tab İçeriği: DuPont Ayrıştırması */}
      {activeTab === "dupont" && (
        <div className="p-6 rounded-xl border border-zinc-800 bg-zinc-900/30">
          <h4 className="text-sm font-bold text-white mb-2">
            DuPont 3 Aşamalı Özsermaye Kârlılığı Modeli
          </h4>
          <p className="text-xs text-zinc-400 mb-6">
            Özsermaye kârlılığının (ROE) hangi kaynaktan beslendiğini gösterir: Operasyonel marjlar mı,
            varlık devir hızı mı, yoksa finansal borçlanma (kaldıraç) mı?
          </p>

          <div className="grid grid-cols-1 md:grid-cols-7 items-center gap-4 text-center">
            {/* 1. Net Marj */}
            <div className="md:col-span-2 p-4 rounded-xl border border-zinc-800 bg-zinc-950/70">
              <span className="text-xs font-bold text-zinc-400 uppercase block mb-1">
                Adım 1: Kâr Marjı
              </span>
              <span className="text-2xl font-extrabold font-mono text-white block">
                %{dupont.net_kar_marji.toFixed(1)}
              </span>
              <span className="text-xs text-zinc-400 mt-1 block">
                Net Kâr / Toplam Hasılat
              </span>
              <span className="text-xs text-emerald-400 block mt-2 font-mono">
                Fiyatlama & Maliyet Gücü
              </span>
            </div>

            <div className="hidden md:flex justify-center text-zinc-400 font-mono text-xl">
              ×
            </div>

            {/* 2. Aktif Devir Hızı */}
            <div className="md:col-span-2 p-4 rounded-xl border border-zinc-800 bg-zinc-950/70">
              <span className="text-xs font-bold text-zinc-400 uppercase block mb-1">
                Adım 2: Devir Hızı
              </span>
              <span className="text-2xl font-extrabold font-mono text-white block">
                {dupont.aktif_devir_hizi.toFixed(2)}x
              </span>
              <span className="text-xs text-zinc-400 mt-1 block">
                Hasılat / Toplam Varlıklar
              </span>
              <span className="text-xs text-cyan-400 block mt-2 font-mono">
                Operasyonel Varlık Verimi
              </span>
            </div>

            <div className="hidden md:flex justify-center text-zinc-400 font-mono text-xl">
              ×
            </div>

            {/* 3. Finansal Kaldıraç */}
            <div className="md:col-span-2 p-4 rounded-xl border border-zinc-800 bg-zinc-950/70">
              <span className="text-xs font-bold text-zinc-400 uppercase block mb-1">
                Adım 3: Kaldıraç Çarpanı
              </span>
              <span className="text-2xl font-extrabold font-mono text-white block">
                {dupont.kaldirac_carpani.toFixed(2)}x
              </span>
              <span className="text-xs text-zinc-400 mt-1 block">
                Toplam Varlık / Özkaynak
              </span>
              <span className="text-xs text-amber-400 block mt-2 font-mono">
                Finansal Risk / Borçlanma
              </span>
            </div>
          </div>

          {/* Sonuç Eşitliği */}
          <div className="mt-6 p-4 rounded-xl bg-cyan-500/5 border border-cyan-500/20 flex flex-col sm:flex-row items-center justify-between gap-4">
            <div className="flex items-center gap-3">
              <TrendingUp className="w-5 h-5 text-cyan-400 shrink-0" />
              <div className="text-xs">
                <span className="font-bold text-white block">
                  DuPont ROE Bileşimi Sonucu: %{dupont.hesaplanan_roe.toFixed(1)}
                </span>
                <span className="text-zinc-400 block mt-0.5">
                  {dupont.kaldirac_carpani > 3.0
                    ? "Kârlılıkta finansal kaldıraç (borç) payı yüksek, borç çevirme maliyeti kritik."
                    : dupont.aktif_devir_hizi > 1.0
                    ? "Varlık devir hızı yüksek, sağlıklı operasyonel satış döngüsü mevcut."
                    : "Kârlılık temel olarak net operasyonel kâr marjından kaynaklanmaktadır."}
                </span>
              </div>
            </div>
            <span className="text-xl font-extrabold font-mono text-cyan-400 shrink-0">
              %{dupont.hesaplanan_roe.toFixed(1)} ROE
            </span>
          </div>
        </div>
      )}

      {/* Tab İçeriği: Altman Z Bileşenleri */}
      {activeTab === "altman" && (
        <div className="p-6 rounded-xl border border-zinc-800 bg-zinc-900/30">
          <h4 className="text-sm font-bold text-white mb-2">
            Altman Z-Score Formül Katsayıları & Bileşenleri
          </h4>
          <p className="text-xs text-zinc-400 mb-6">
            Sanayi ve üretim şirketlerinin borç/özkaynak dengesi ile operasyonel nakit üretimini harmanlayan iflas riski modeli.
          </p>

          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-5 gap-3 text-xs font-mono">
            {Object.entries(health.altman_bilesenler || {}).map(([key, val]) => (
              <div key={key} className="p-3 rounded-lg border border-zinc-800 bg-zinc-950/70">
                <span className="text-xs text-zinc-400 block uppercase truncate">
                  {key.replace(/_/g, " ")}
                </span>
                <span className="text-base font-bold text-white mt-1 block">
                  {typeof val === "number" ? val.toFixed(3) : val}
                </span>
              </div>
            ))}
          </div>

          <div className="mt-5 text-xs text-zinc-400 bg-zinc-950 p-3 rounded-lg border border-zinc-800/80">
            <strong>Analist Notu:</strong> Altman Z-Skoru 2.99 üzeri şirketler finansal darboğaz açısından güvenli kabul edilir.
            1.81 altı skorlar ise yüksek borçluluk ve likidite sıkışması riski taşır.
          </div>
        </div>
      )}

      {/* Özet ve SPK Yasal Uyarısı */}
      <div className="mt-6 pt-4 border-t border-zinc-800/80 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs text-zinc-400">
        <p className="flex items-center gap-1.5">
          <Info className="w-3.5 h-3.5 text-zinc-400 shrink-0" />
          <span>{health.ozet}</span>
        </p>
        <span className="shrink-0 font-mono text-xs text-zinc-400">
          SPK 2026 Uyumlu Algoritma
        </span>
      </div>
    </div>
  );
}
