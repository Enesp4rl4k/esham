"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import {
  Compass,
  TrendingUp,
  TrendingDown,
  Layers,
  FileText,
  Calendar,
  Clock,
  ChevronDown,
  ChevronUp,
  ArrowRight,
  ShieldAlert,
  Zap,
} from "lucide-react";
import type { Report } from "@/lib/content";

interface MorningCockpitProps {
  viopData?: any;
  tickerData?: any;
  quantData?: any;
  calendarData?: any;
  reports?: Report[];
}

export function MorningCockpit({
  viopData,
  tickerData,
  quantData,
  calendarData,
  reports = [],
}: MorningCockpitProps) {
  // Varsayılan: Sabah seansı açık, 12:30'dan sonra otomatik kapalı
  const [isOpen, setIsOpen] = useState(true);
  const [isClient, setIsClient] = useState(false);
  const [sessionPhase, setSessionPhase] = useState("Seans Kontrol Ediliyor");

  useEffect(() => {
    setIsClient(true);
    const now = new Date();
    // Türkiye saati UTC+3
    const utcHours = now.getUTCHours();
    const trHours = (utcHours + 3) % 24;
    const trMinutes = now.getUTCMinutes();
    const timeVal = trHours + trMinutes / 60;

    // Seans Fazı Tespiti
    if (timeVal >= 8.5 && timeVal < 9.92) {
      setSessionPhase("Seans Öncesi & Açılış Müzayedesi (08:30 - 09:55)");
    } else if (timeVal >= 9.92 && timeVal < 18.0) {
      setSessionPhase("Sürekli Müzayede Seansı Aktif (10:00 - 18:00)");
    } else if (timeVal >= 18.0 && timeVal < 18.15) {
      setSessionPhase("Kapanış Müzayedesi Seansı (18:00 - 18:10)");
    } else if (timeVal >= 19.0 && timeVal < 23.0) {
      setSessionPhase("VİOP Akşam Seansı (19:00 - 23:00)");
    } else {
      setSessionPhase("Piyasalar Kapalı (Yeni Seans 08:30)");
    }

    // Kullanıcının bugünkü manuel tercihi var mı?
    const todayKey = `esham_cockpit_${now.toISOString().split("T")[0]}`;
    const savedState = sessionStorage.getItem(todayKey);

    if (savedState !== null) {
      setIsOpen(savedState === "open");
    } else {
      // 12:30'dan sonra otomatik kapanır, sabahları açık gelir
      if (timeVal >= 12.5) {
        setIsOpen(false);
      } else {
        setIsOpen(true);
      }
    }
  }, []);

  const toggleOpen = () => {
    const next = !isOpen;
    setIsOpen(next);
    if (typeof window !== "undefined") {
      const todayKey = `esham_cockpit_${new Date().toISOString().split("T")[0]}`;
      sessionStorage.setItem(todayKey, next ? "open" : "closed");
    }
  };

  // 1. VİOP & Açılış Beklentisi Hesabı
  // Gerçek kotasyon yoksa (viop-basis.json yok / sayısal alan eksik) hiçbir sayı ya da yön gösterilmez.
  const hasViop =
    typeof viopData?.basis_puan === "number" &&
    typeof viopData?.basis_yuzde === "number" &&
    typeof viopData?.vadeli_f_xu030 === "number" &&
    !!viopData?.veri_tarihi;
  const isViopPositive = hasViop && viopData.basis_puan >= 0;
  const basisPuan: number = hasViop ? viopData.basis_puan : 0;
  const basisYuzde: number = hasViop ? viopData.basis_yuzde : 0;
  const vadeliFiyat: number = hasViop ? viopData.vadeli_f_xu030 : 0;
  const viopAsOf: string | null = hasViop
    ? new Date(viopData.veri_tarihi).toLocaleString("tr-TR", { timeZone: "Europe/Istanbul" })
    : null;
  const fmt = (v: number, d = 1) => v.toLocaleString("tr-TR", { minimumFractionDigits: d, maximumFractionDigits: d });

  const openingSentiment = !hasViop
    ? {
        label: "Veri yok",
        badgeClass: "bg-zinc-800 text-zinc-400 border-zinc-700",
        summary: "VİOP kotasyonu alınamadı; açılış görünümü için veri yok.",
      }
    : isViopPositive
    ? {
        label: "Pozitif / Alıcılı Açılış",
        badgeClass: "bg-emerald-500/15 text-emerald-400 border-emerald-500/30",
        summary:
          "VİOP F_XU030 vadeli kontratı spot piyasaya göre primli işlem görüyor. Kurumsal vadeli alımlar açılışta pozitif risk iştahını destekliyor.",
      }
    : {
        label: "Satıcılı / Temkinli Açılış",
        badgeClass: "bg-rose-500/15 text-rose-400 border-rose-500/30",
        summary:
          "VİOP kontratında basis iskontosu ve temkinli fiyatlama izleniyor; açılışta direnç seviyelerinde kâr realizasyonu görülebilir.",
      };

  // 2. BIST-30 Öncü Pivot Seviyeleri
  // Yalnızca TARİHLİ (updated_at) bist-quant-valuation.json'daki hesaplanmış seviyelerden; tarihsiz dosya gösterilmez,
  // veri olmayan hisse listelenmez, hiç veri yoksa kart hiç çizilmez (boş kutu yok).
  const pivotAsOf: string | null = typeof quantData?.updated_at === "string" ? quantData.updated_at.slice(0, 10) : null;
  const pivotList: { ticker: string; pivot: number }[] = ["THYAO", "GARAN", "ASELS", "TUPRS", "KCHOL", "EREGL"]
    .map((ticker) => ({ ticker, pivot: quantData?.[ticker]?.key_levels?.pivot_noktasi }))
    .filter((x): x is { ticker: string; pivot: number } => typeof x.pivot === "number");

  // 3. Sabahın En Kritik 3 KAP Haberi
  const topKapReports = reports.slice(0, 3);

  // 4. Günün Ajandası (TradingView Ekonomik Takvim)
  const calendarEvents: { time: string; country: string; event: string }[] = calendarData?.events?.slice(0, 4) || [];

  return (
    <section className="mb-10 w-full">
      <div className="rounded-2xl border border-zinc-800 bg-gradient-to-b from-zinc-900/90 to-zinc-950/95 backdrop-blur-xl shadow-2xl overflow-hidden transition-all duration-300">
        {/* Üst Başlık Şeridi */}
        <div className="px-5 py-3.5 border-b border-zinc-800/80 flex items-center justify-between gap-4 bg-zinc-900/40">
          <div className="flex items-center gap-3">
            <span className="w-2.5 h-2.5 rounded-full bg-zinc-600 shrink-0" aria-hidden="true" />
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-xs font-mono font-bold uppercase tracking-wider text-white">
                Günün Seans Açılış Kokpiti
              </span>
              <span className="text-xs font-mono px-2 py-0.5 rounded bg-zinc-800 border border-zinc-700 text-zinc-300 hidden sm:inline">
                {sessionPhase}
              </span>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <span className="text-xs font-mono text-zinc-400 hidden md:inline">
              {/* Bugünün tarihi yalnızca istemcide: statik HTML derleme gününün tarihini taşır (hydration #418) */}
              {isClient
                ? new Date().toLocaleDateString("tr-TR", { weekday: "long", day: "numeric", month: "long", timeZone: "Europe/Istanbul" })
                : ""}
            </span>
            <button
              onClick={toggleOpen}
              className="inline-flex items-center gap-1.5 px-3 py-1 text-xs font-mono font-semibold rounded-lg bg-zinc-800/80 hover:bg-zinc-700 text-zinc-300 hover:text-white border border-zinc-700 transition-colors"
            >
              <span>{isOpen ? "Gizle" : "Kokpiti Genişlet"}</span>
              {isOpen ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
            </button>
          </div>
        </div>

        {/* Kapalı Haldeki İnce Özet Şeridi */}
        {!isOpen && (
          <div className="px-5 py-3 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs font-mono bg-zinc-950/60">
            <div className="flex items-center gap-3 text-zinc-400">
              <span className="text-zinc-400">Açılış Görünümü:</span>
              <span className={`px-2 py-0.5 rounded text-xs font-bold border ${openingSentiment.badgeClass}`}>
                {openingSentiment.label}
              </span>
              <span className="hidden md:inline text-zinc-400">•</span>
              <span className="hidden md:inline text-zinc-300">
                VİOP Basis:{" "}
                {hasViop ? (
                  <strong className={isViopPositive ? "text-emerald-400" : "text-rose-400"}>
                    {basisPuan > 0 ? "+" : ""}
                    {fmt(basisPuan)} Puan {isViopPositive ? "Contango" : "Backwardation"}
                  </strong>
                ) : (
                  <strong className="text-zinc-400">Veri yok</strong>
                )}
              </span>
            </div>
            <button
              onClick={toggleOpen}
              className="text-xs text-amber-400 hover:text-amber-300 inline-flex items-center gap-1 self-start sm:self-auto"
            >
              <span>4 Kritik Seans Verisini Gör</span>
              <ArrowRight className="w-3 h-3" />
            </button>
          </div>
        )}

        {/* Açık Haldeki 4 Kritik Veri Kartı */}
        {isOpen && (
          <div className="p-5 md:p-6 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-5">
            {/* 1. KART: Günün Açılış Beklentisi & VİOP */}
            <div className="flex flex-col justify-between p-4 rounded-xl border border-zinc-800/80 bg-zinc-900/60 shadow-inner">
              <div>
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <span className="p-1.5 rounded-lg bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                      <TrendingUp className="w-4 h-4" />
                    </span>
                    <h3 className="text-xs font-bold text-white uppercase tracking-wider font-mono">
                      Açılış & VİOP
                    </h3>
                  </div>
                  <span className={`text-xs font-mono font-bold px-2 py-0.5 rounded border ${openingSentiment.badgeClass}`}>
                    {openingSentiment.label}
                  </span>
                </div>

                <div className="space-y-2 mb-3 font-mono text-xs">
                  <div className="flex justify-between items-center bg-zinc-950/70 p-2 rounded border border-zinc-800/60">
                    <span className="text-zinc-400">F_XU030 Vadeli</span>
                    <span className="font-bold text-white">{hasViop ? `${fmt(vadeliFiyat, 2)} ₺` : "Veri yok"}</span>
                  </div>
                  <div className="flex justify-between items-center bg-zinc-950/70 p-2 rounded border border-zinc-800/60">
                    <span className="text-zinc-400">Basis Makası</span>
                    <span className={`font-bold ${hasViop ? (isViopPositive ? "text-emerald-400" : "text-rose-400") : "text-zinc-400"}`}>
                      {hasViop
                        ? `${basisPuan > 0 ? "+" : ""}${fmt(basisPuan)} pt (%${fmt(basisYuzde, 2)})`
                        : "Veri yok"}
                    </span>
                  </div>
                </div>

                <p className="text-xs text-zinc-400 leading-relaxed font-sans">
                  {openingSentiment.summary}
                </p>
              </div>

              <div className="mt-4 pt-3 border-t border-zinc-800/70 flex items-center justify-between text-xs font-mono text-zinc-400">
                <span>{viopAsOf ? `Veri tarihi: ${viopAsOf}` : "Veri tarihi: yok"}</span>
                <span className="text-zinc-400">{hasViop ? (isViopPositive ? "Contango" : "Backwardation") : "—"}</span>
              </div>
            </div>

            {/* 2. KART: Kritik BIST-30 Seviyeleri (Pivot & Kırılma) */}
            {pivotAsOf && pivotList.length > 0 && (
            <div className="flex flex-col justify-between p-4 rounded-xl border border-zinc-800/80 bg-zinc-900/60 shadow-inner">
              <div>
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <span className="p-1.5 rounded-lg bg-cyan-500/10 text-cyan-400 border border-cyan-500/20">
                      <Compass className="w-4 h-4" />
                    </span>
                    <h3 className="text-xs font-bold text-white uppercase tracking-wider font-mono">
                      Kritik Pivotlar
                    </h3>
                  </div>
                  <span className="text-xs font-mono px-2 py-0.5 rounded bg-zinc-800 text-zinc-400 border border-zinc-700">
                    BIST-30
                  </span>
                </div>

                <div className="grid grid-cols-2 gap-1.5 mb-2 font-mono text-xs">
                  {pivotList.map((item) => (
                    <Link
                      key={item.ticker}
                      href={`/hisse/${item.ticker}`}
                      className="p-1.5 rounded bg-zinc-950/70 hover:bg-zinc-800/80 border border-zinc-800/60 hover:border-cyan-500/40 transition-colors flex items-center justify-between group"
                    >
                      <span className="font-bold text-white group-hover:text-cyan-400">
                        ${item.ticker}
                      </span>
                      <span className="text-xs text-zinc-400">
                        P: <strong className="text-cyan-300">{fmt(item.pivot, 2)}</strong>
                      </span>
                    </Link>
                  ))}
                </div>

                <p className="text-xs text-zinc-400 font-sans mt-2">
                  * Pivot üzeri fiyatlamalar alıcılı trendi, altı ise S1 destek testini tetikler.
                </p>
              </div>

              <div className="mt-4 pt-3 border-t border-zinc-800/70 flex items-center justify-between text-xs font-mono text-zinc-400">
                <span>Veri tarihi: {pivotAsOf}</span>
                <span className="text-zinc-400">—</span>
              </div>
            </div>
            )}

            {/* 3. KART: Günün En Kritik 3 KAP Haberi */}
            <div className="flex flex-col justify-between p-4 rounded-xl border border-zinc-800/80 bg-zinc-900/60 shadow-inner">
              <div>
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <span className="p-1.5 rounded-lg bg-amber-500/10 text-amber-400 border border-amber-500/20">
                      <FileText className="w-4 h-4" />
                    </span>
                    <h3 className="text-xs font-bold text-white uppercase tracking-wider font-mono">
                      Sabah KAP Akışı
                    </h3>
                  </div>
                  <span className="text-xs font-mono px-2 py-0.5 rounded bg-amber-500/10 text-amber-400 border border-amber-500/20">
                    Son 24 Saat
                  </span>
                </div>

                <div className="space-y-2.5">
                  {topKapReports.map((r, i) => (
                    <Link
                      key={r.slug}
                      href={`/rapor/${r.slug}`}
                      className="block group border-b border-zinc-800/50 pb-2 last:border-0 last:pb-0"
                    >
                      <div className="flex items-center gap-1.5 mb-0.5">
                        <span className="text-xs font-mono uppercase px-1.5 py-0.2 rounded bg-zinc-800 text-zinc-300">
                          {r.ipo?.ticker ? `$${r.ipo.ticker}` : r.tags?.[0] ? `$${r.tags[0].toUpperCase()}` : "BIST"}
                        </span>
                        <span className="text-xs font-mono text-zinc-400">
                          #{i + 1}
                        </span>
                      </div>
                      <p className="text-xs text-zinc-300 group-hover:text-amber-300 transition-colors line-clamp-1 font-medium">
                        {r.title}
                      </p>
                    </Link>
                  ))}
                </div>
              </div>

              <div className="mt-4 pt-3 border-t border-zinc-800/70 flex items-center justify-between text-xs font-mono text-zinc-400">
                <Link href="/kategori/bist" className="text-amber-400 hover:underline flex items-center gap-1">
                  <span>Tüm KAP bildirimleri</span>
                  <ArrowRight className="w-3 h-3" />
                </Link>
              </div>
            </div>

            {/* 4. KART: Günün Ajandası / Veri Takvimi */}
            <div className="flex flex-col justify-between p-4 rounded-xl border border-zinc-800/80 bg-zinc-900/60 shadow-inner">
              <div>
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <span className="p-1.5 rounded-lg bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
                      <Clock className="w-4 h-4" />
                    </span>
                    <h3 className="text-xs font-bold text-white uppercase tracking-wider font-mono">
                      Günün Ajandası
                    </h3>
                  </div>
                  <span className="text-xs font-mono px-2 py-0.5 rounded bg-zinc-800 text-zinc-400 border border-zinc-700">
                    Ekonomik Takvim
                  </span>
                </div>

                {calendarEvents.length === 0 && <p className="text-xs text-zinc-400 font-sans mb-2">Bugün için takvim verisi yok.</p>}
                <div className="space-y-2 font-mono text-xs">
                  {calendarEvents.map((evt: any, idx: number) => (
                    <div
                      key={idx}
                      className="flex items-start gap-2.5 p-1.5 rounded bg-zinc-950/70 border border-zinc-800/60"
                    >
                      <span className="text-amber-400 font-bold shrink-0 text-xs mt-0.5">
                        {evt.time}
                      </span>
                      <div className="min-w-0">
                        <span className="text-xs text-zinc-400 block">
                          {evt.country}
                        </span>
                        <span className="text-zinc-300 block truncate text-xs font-sans">
                          {evt.event}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              <div className="mt-4 pt-3 border-t border-zinc-800/70 flex items-center justify-between text-xs font-mono text-zinc-400">
                <span>Saat Dilimi: GMT+3 (TSİ)</span>
                <span className="text-indigo-400">TradingView API</span>
              </div>
            </div>
          </div>
        )}
      </div>
    </section>
  );
}
