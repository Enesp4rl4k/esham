"use client";

import React, { useState, useEffect, useMemo } from "react";
import Link from "next/link";
import {
  Activity,
  Sliders,
  Maximize2,
  Minimize2,
  RotateCcw,
  TrendingUp,
  TrendingDown,
  Layers,
  Clock,
  ArrowUpRight,
  Search,
  Flame,
  ShieldCheck,
  FileText,
  ChevronRight,
  ExternalLink,
  Fuel,
  Building2,
  Percent,
  Compass,
  CheckCircle2,
  BarChart3,
  RefreshCw,
  Sun,
  Zap,
  LayoutGrid,
} from "lucide-react";

export interface TraderTerminalClientProps {
  tickerData: any;
  quantData: any;
  viopData: any;
  macroData: any;
  devalData: any;
  buybacksData: any;
  dividendsData: any;
  turibData: any;
  recentReports: any[];
  initialTicker?: string;
}

type LayoutPreset = "morning" | "scalp" | "valuation" | "full";
type DensityMode = "compact" | "normal";

interface PanelConfig {
  preMarket: boolean;
  pivotDesk: boolean;
  kapStream: boolean;
  quantMatrix: boolean;
  buybacks: boolean;
  dividends: boolean;
  macroRadar: boolean;
  oilTanker: boolean;
}

const DEFAULT_PRESETS: Record<LayoutPreset, PanelConfig> = {
  morning: {
    preMarket: true,
    pivotDesk: true,
    kapStream: true,
    quantMatrix: false,
    buybacks: true,
    dividends: true,
    macroRadar: true,
    oilTanker: false,
  },
  scalp: {
    preMarket: true,
    pivotDesk: true,
    kapStream: true,
    quantMatrix: true,
    buybacks: false,
    dividends: false,
    macroRadar: false,
    oilTanker: false,
  },
  valuation: {
    preMarket: false,
    pivotDesk: true,
    kapStream: false,
    quantMatrix: true,
    buybacks: true,
    dividends: true,
    macroRadar: true,
    oilTanker: false,
  },
  full: {
    preMarket: true,
    pivotDesk: true,
    kapStream: true,
    quantMatrix: true,
    buybacks: true,
    dividends: true,
    macroRadar: true,
    oilTanker: true,
  },
};

export function TraderTerminalClient({
  tickerData,
  quantData,
  viopData,
  macroData,
  devalData,
  buybacksData,
  dividendsData,
  turibData,
  recentReports,
  initialTicker,
}: TraderTerminalClientProps) {
  // ── 1. State & Settings ──
  const [activePreset, setActivePreset] = useState<LayoutPreset>("morning");
  const [panels, setPanels] = useState<PanelConfig>(DEFAULT_PRESETS.morning);
  const [density, setDensity] = useState<DensityMode>("compact");
  const [isConfigOpen, setIsConfigOpen] = useState(false);
  const [isZenMode, setIsZenMode] = useState(false);
  const [currentTime, setCurrentTime] = useState("");
  const [marketStatus, setMarketStatus] = useState("Seans Kontrol Ediliyor");

  // Pivot Masası hisse seçimi
  const availableTickers = useMemo(() => {
    if (!quantData) return ["THYAO", "ASELS", "GARAN", "AKBNK", "TUPRS", "KCHOL", "EREGL", "BIMAS"];
    return Object.keys(quantData).sort();
  }, [quantData]);

  const [selectedTicker, setSelectedTicker] = useState<string>(() => {
    if (initialTicker && quantData && quantData[initialTicker]) {
      return initialTicker;
    }
    return "THYAO";
  });

  useEffect(() => {
    if (typeof window !== "undefined") {
      const params = new URLSearchParams(window.location.search);
      const urlTicker = params.get("ticker")?.toUpperCase();
      if (urlTicker && quantData && quantData[urlTicker]) {
        setSelectedTicker(urlTicker);
      } else if (initialTicker && quantData && quantData[initialTicker]) {
        setSelectedTicker(initialTicker);
      }
    }
  }, [initialTicker, quantData]);
  const [tickerSearch, setTickerSearch] = useState<string>("");

  // KAP Filtresi
  const [kapFilter, setKapFilter] = useState<"all" | "mega" | "financial" | "buyback" | "macro">("all");

  // Quant Sıralama
  const [quantSortField, setQuantSortField] = useState<"ticker" | "fiyat" | "fk" | "pddd" | "upside">("fk");
  const [quantSortAsc, setQuantSortAsc] = useState(true);

  // ── 2. LocalStorage Yükleme & Senkronizasyon ──
  useEffect(() => {
    try {
      const saved = localStorage.getItem("esham_trader_panels");
      if (saved) {
        const parsed = JSON.parse(saved);
        setPanels(parsed);
      }
      const savedDensity = localStorage.getItem("esham_trader_density");
      if (savedDensity === "compact" || savedDensity === "normal") {
        setDensity(savedDensity);
      }
    } catch {
      // fallback to defaults
    }
  }, []);

  const savePanels = (newPanels: PanelConfig) => {
    setPanels(newPanels);
    try {
      localStorage.setItem("esham_trader_panels", JSON.stringify(newPanels));
    } catch {
      // ignore
    }
  };

  const handlePresetChange = (preset: LayoutPreset) => {
    setActivePreset(preset);
    savePanels(DEFAULT_PRESETS[preset]);
  };

  const togglePanel = (key: keyof PanelConfig) => {
    const updated = { ...panels, [key]: !panels[key] };
    savePanels(updated);
  };

  const toggleDensity = () => {
    const next = density === "compact" ? "normal" : "compact";
    setDensity(next);
    try {
      localStorage.setItem("esham_trader_density", next);
    } catch {
      // ignore
    }
  };

  // ── 3. Canlı Saat & Seans Durumu ──
  useEffect(() => {
    const updateClock = () => {
      const now = new Date();
      const trTime = new Date(now.toLocaleString("en-US", { timeZone: "Europe/Istanbul" }));
      const timeStr = trTime.toLocaleTimeString("tr-TR", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
      setCurrentTime(timeStr);

      const hour = trTime.getHours();
      const min = trTime.getMinutes();
      const day = trTime.getDay(); // 0 Pazar, 6 Cmt

      if (day === 0 || day === 6) {
        setMarketStatus("Hafta Sonu — Seans Kapalı");
      } else {
        const totalMinutes = hour * 60 + min;
        if (totalMinutes < 570) {
          // < 09:30
          setMarketStatus("Seans Öncesi / Erken Sabah (09:30 VİOP Açılışı Bekleniyor)");
        } else if (totalMinutes >= 570 && totalMinutes < 580) {
          // 09:30 - 09:40
          setMarketStatus("VİOP Açık — BIST Emir Toplama Bekleniyor");
        } else if (totalMinutes >= 580 && totalMinutes < 595) {
          // 09:40 - 09:55
          setMarketStatus("BIST Açılış Seansı (Emir Toplama 09:40 - 09:55)");
        } else if (totalMinutes >= 595 && totalMinutes < 600) {
          // 09:55 - 10:00
          setMarketStatus("BIST Açılış Fiyat Eşleşmesi (09:55 - 10:00)");
        } else if (totalMinutes >= 600 && totalMinutes < 1080) {
          // 10:00 - 18:00
          setMarketStatus("Sürekli Müzayede (Canlı Seans Açık)");
        } else if (totalMinutes >= 1080 && totalMinutes < 1090) {
          // 18:00 - 18:10
          setMarketStatus("Kapanış Marjı / Tek Fiyat Seansı");
        } else {
          setMarketStatus("Gündüz Seansı Kapandı — VİOP Akşam Seansı");
        }
      }
    };

    updateClock();
    const interval = setInterval(updateClock, 1000);
    return () => clearInterval(interval);
  }, []);

  // ── 4. Seçilen Hisse Key Levels Bilgisi ──
  const activeStockData = quantData?.[selectedTicker] || null;
  const keyLevels = activeStockData?.key_levels || null;
  const fundamental = activeStockData?.fundamental || null;
  const dcf = activeStockData?.dcf || null;

  // ── 5. Filtrelenmiş KAP Raporları ──
  const filteredReports = useMemo(() => {
    if (!recentReports) return [];
    return recentReports.filter((r) => {
      if (kapFilter === "all") return true;
      const titleLower = (r.title || "").toLowerCase();
      const tags = (r.tags || []).map((t: string) => t.toLowerCase());
      if (kapFilter === "mega") {
        return (
          titleLower.includes("iş ilişkisi") ||
          titleLower.includes("sipariş") ||
          titleLower.includes("sözleşme") ||
          titleLower.includes("ihale") ||
          tags.includes("mega sözleşme")
        );
      }
      if (kapFilter === "financial") {
        return (
          titleLower.includes("finansal rapor") ||
          titleLower.includes("faaliyet raporu") ||
          titleLower.includes("bilanço") ||
          titleLower.includes("kar") ||
          titleLower.includes("zarar")
        );
      }
      if (kapFilter === "buyback") {
        return titleLower.includes("geri alım") || titleLower.includes("pay alımı");
      }
      if (kapFilter === "macro") {
        return r.category === "global" || r.category === "gundem" || r.category === "viop";
      }
      return true;
    });
  }, [recentReports, kapFilter]);

  // ── 6. Quant Matrisi Sıralaması ──
  const sortedQuantRows = useMemo(() => {
    if (!quantData) return [];
    const rows = Object.values(quantData).map((item: any) => {
      const ticker = item.ticker;
      const kl = item.key_levels || {};
      const f = item.fundamental || {};
      const d = item.dcf || {};
      const sonFiyat = kl.son_fiyat || 0;
      const fk = f.fiyat_kazanc_fk || 999;
      const pddd = f.piyasa_defter_pddd || 999;
      const fdFavok = f.fd_favok || 999;
      const roe = f.ozsermaye_karliligi_roe || 0;
      const targetDcf = d.varsayimlar ? (d.varsayimlar.buyume_orani ? sonFiyat * (1 + d.varsayimlar.buyume_orani * 2.5) : sonFiyat) : sonFiyat;
      const upside = sonFiyat > 0 ? ((targetDcf - sonFiyat) / sonFiyat) * 100 : 0;
      const changePct = kl.gunluk_degisim_yuzde || 0;

      return {
        ticker,
        sonFiyat,
        changePct,
        fk,
        pddd,
        fdFavok,
        roe,
        targetDcf,
        upside,
        sektor: f.sektor || "-",
      };
    });

    return rows.sort((a: any, b: any) => {
      let valA = a[quantSortField];
      let valB = b[quantSortField];
      if (typeof valA === "string") {
        return quantSortAsc ? valA.localeCompare(valB) : valB.localeCompare(valA);
      }
      return quantSortAsc ? valA - valB : valB - valA;
    });
  }, [quantData, quantSortField, quantSortAsc]);

  const isCompact = density === "compact";

  return (
    <div
      className={`min-h-screen text-zinc-100 font-sans transition-colors ${
        isZenMode ? "p-3 bg-black" : "p-4 md:p-6 bg-zinc-950"
      }`}
    >
      {/* ── TOP TERMINAL BAR ────────────────────────────────────────── */}
      <div className="mb-5 pb-4 border-b border-zinc-800/80 flex flex-col lg:flex-row lg:items-center justify-between gap-4">
        {/* Sol: Logo + Mod Rozeti + Canlı Saat + Seans Durumu */}
        <div className="flex flex-wrap items-center gap-3">
          <Link
            href="/"
            className="flex items-center gap-2 px-2.5 py-1 rounded-md bg-zinc-900 border border-zinc-800 hover:border-zinc-700 transition-colors"
          >
            <span className="font-display font-bold text-sm tracking-tight">
              <span className="text-amber-400">Es</span>ham
            </span>
            <span className="text-[10px] font-mono text-zinc-500 uppercase tracking-wider">Terminal</span>
          </Link>

          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-xs font-mono font-bold">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
            <span>TRADER MOD</span>
          </div>

          <div className="flex items-center gap-2 px-2.5 py-1 rounded-md bg-zinc-900/80 border border-zinc-800 text-xs font-mono text-zinc-300">
            <Clock className="w-3.5 h-3.5 text-amber-400" />
            <span>{currentTime || "09:00:00"}</span>
            <span className="text-[10px] text-zinc-500">TRT (GMT+3)</span>
          </div>

          <div className="text-xs font-mono text-zinc-400 bg-zinc-900/40 px-2.5 py-1 rounded border border-zinc-800/60 hidden sm:block">
            {marketStatus}
          </div>
        </div>

        {/* Sağ: Çalışma Alanı Presets + Yoğunluk + Özelleştir Çekmecesi */}
        <div className="flex flex-wrap items-center gap-2">
          {/* Preset Butonları */}
          <div className="flex items-center p-0.5 rounded-lg bg-zinc-900 border border-zinc-800 text-xs font-medium">
            <button
              onClick={() => handlePresetChange("morning")}
              className={`flex items-center gap-1 px-2.5 py-1 rounded-md transition-colors ${
                activePreset === "morning" ? "bg-amber-500/20 text-amber-300 font-semibold" : "text-zinc-400 hover:text-white"
              }`}
            >
              <Sun className="w-3 h-3 text-amber-400" />
              <span>Sabah</span>
            </button>
            <button
              onClick={() => handlePresetChange("scalp")}
              className={`flex items-center gap-1 px-2.5 py-1 rounded-md transition-colors ${
                activePreset === "scalp" ? "bg-amber-500/20 text-amber-300 font-semibold" : "text-zinc-400 hover:text-white"
              }`}
            >
              <Zap className="w-3 h-3 text-emerald-400" />
              <span>Scalp</span>
            </button>
            <button
              onClick={() => handlePresetChange("valuation")}
              className={`flex items-center gap-1 px-2.5 py-1 rounded-md transition-colors ${
                activePreset === "valuation" ? "bg-amber-500/20 text-amber-300 font-semibold" : "text-zinc-400 hover:text-white"
              }`}
            >
              <BarChart3 className="w-3 h-3 text-sky-400" />
              <span>Quant</span>
            </button>
            <button
              onClick={() => handlePresetChange("full")}
              className={`flex items-center gap-1 px-2.5 py-1 rounded-md transition-colors ${
                activePreset === "full" ? "bg-amber-500/20 text-amber-300 font-semibold" : "text-zinc-400 hover:text-white"
              }`}
            >
              <LayoutGrid className="w-3 h-3 text-purple-400" />
              <span>Tümü</span>
            </button>
          </div>

          {/* Density Switcher */}
          <button
            onClick={toggleDensity}
            title="Yoğunluk Modu (Kompakt / Standart)"
            className="px-2.5 py-1 rounded-md bg-zinc-900 border border-zinc-800 text-xs font-mono text-zinc-300 hover:text-white hover:border-zinc-700 transition-colors"
          >
            {isCompact ? "Yoğunluk: Yüksek" : "Yoğunluk: Standart"}
          </button>

          {/* Özelleştir Paneli Toggle */}
          <div className="relative">
            <button
              onClick={() => setIsConfigOpen(!isConfigOpen)}
              className="flex items-center gap-1 px-2.5 py-1 rounded-md bg-zinc-900 border border-zinc-800 text-xs font-medium text-zinc-300 hover:text-white hover:border-zinc-700 transition-colors"
            >
              <Sliders className="w-3.5 h-3.5 text-amber-400" />
              <span>Panelleri Yapılandır</span>
            </button>

            {isConfigOpen && (
              <div className="absolute right-0 top-full mt-2 w-72 p-4 rounded-xl bg-zinc-950 border border-zinc-800 shadow-2xl z-50 animate-in fade-in zoom-in-95">
                <div className="flex items-center justify-between pb-2 mb-3 border-b border-zinc-800">
                  <span className="text-xs font-bold font-mono uppercase text-zinc-300">Terminal Bileşenleri</span>
                  <button
                    onClick={() => savePanels(DEFAULT_PRESETS.morning)}
                    className="text-[10px] text-zinc-500 hover:text-amber-400 flex items-center gap-1"
                  >
                    <RotateCcw className="w-3 h-3" /> Sıfırla
                  </button>
                </div>

                <div className="space-y-2 text-xs">
                  {[
                    { key: "preMarket", label: "VİOP & Sabah Barometresi" },
                    { key: "pivotDesk", label: "BIST-30 Pivot Masası" },
                    { key: "kapStream", label: "Canlı KAP İstihbaratı" },
                    { key: "quantMatrix", label: "Quant & Çarpan Matrisi" },
                    { key: "buybacks", label: "Pay Geri Alımları" },
                    { key: "dividends", label: "Temettü Takvimi" },
                    { key: "macroRadar", label: "Devalüasyon & CDS Radarı" },
                    { key: "oilTanker", label: "Petrol & Tanker Navlun" },
                  ].map((item) => (
                    <label key={item.key} className="flex items-center justify-between cursor-pointer py-1 hover:text-white">
                      <span className="text-zinc-300">{item.label}</span>
                      <input
                        type="checkbox"
                        checked={panels[item.key as keyof PanelConfig]}
                        onChange={() => togglePanel(item.key as keyof PanelConfig)}
                        className="rounded border-zinc-700 bg-zinc-900 text-amber-500 focus:ring-0 focus:ring-offset-0 cursor-pointer"
                      />
                    </label>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Zen / Tam Ekran */}
          <button
            onClick={() => setIsZenMode(!isZenMode)}
            title="Zen Modu (Tam Ekran)"
            className="p-1.5 rounded-md bg-zinc-900 border border-zinc-800 text-zinc-400 hover:text-white hover:border-zinc-700 transition-colors"
          >
            {isZenMode ? <Minimize2 className="w-3.5 h-3.5" /> : <Maximize2 className="w-3.5 h-3.5" />}
          </button>
        </div>
      </div>

      {/* ── TERMINAL GRID ───────────────────────────────────────────── */}
      <div className="space-y-4">
        {/* ── 1. ROW: VİOP BASIS & SABAHLIK KÜRESEL AÇILIŞ RADARI ────── */}
        {panels.preMarket && (
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
            {/* VİOP & Takasbank Türev İstihbaratı (7 kolon) */}
            <div className="lg:col-span-7 rounded-xl border border-zinc-800/80 bg-zinc-900/60 p-4">
              <div className="flex items-center justify-between mb-3 pb-2 border-b border-zinc-800/60">
                <div className="flex items-center gap-2">
                  <span className="text-[10px] font-mono uppercase tracking-wider text-amber-400 font-bold px-2 py-0.5 rounded bg-amber-400/10 border border-amber-400/20">
                    Türev & VİOP
                  </span>
                  <span className="text-xs font-bold text-zinc-200">XU030 Vadeli Makas & Takasbank Teminat</span>
                </div>
                <span className="text-[11px] font-mono text-zinc-400">
                  Vadeye {viopData?.vadeye_kalan_gun ?? 32} Gün
                </span>
              </div>

              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-3">
                <div className="p-2.5 rounded-lg bg-zinc-950/70 border border-zinc-800/60">
                  <span className="text-[10px] font-mono text-zinc-500 uppercase block">Spot XU030</span>
                  <span className="text-base font-mono font-bold text-zinc-200">
                    {viopData?.spot_xu030 ? Number(viopData.spot_xu030).toLocaleString("tr-TR") : "11.840,50"}
                  </span>
                </div>
                <div className="p-2.5 rounded-lg bg-zinc-950/70 border border-zinc-800/60">
                  <span className="text-[10px] font-mono text-zinc-500 uppercase block">F_XU030 Vadeli</span>
                  <span className="text-base font-mono font-bold text-amber-400">
                    {viopData?.vadeli_f_xu030 ? Number(viopData.vadeli_f_xu030).toLocaleString("tr-TR") : "12.180,00"}
                  </span>
                </div>
                <div className="p-2.5 rounded-lg bg-zinc-950/70 border border-zinc-800/60">
                  <span className="text-[10px] font-mono text-zinc-500 uppercase block">Basis Spread (Prim)</span>
                  <span className="text-base font-mono font-bold text-emerald-400">
                    +{viopData?.basis_puan ?? "339,50"} (%{viopData?.basis_yuzde ?? "2,87"})
                  </span>
                </div>
                <div className="p-2.5 rounded-lg bg-zinc-950/70 border border-zinc-800/60">
                  <span className="text-[10px] font-mono text-zinc-500 uppercase block">İma Edilen Faiz</span>
                  <span className="text-base font-mono font-bold text-sky-400">
                    %{viopData?.ima_edilen_yillik_faiz_yuzde ?? "32,7"}
                  </span>
                </div>
              </div>

              {/* Takasbank Teminat & Açık Pozisyon Çubuğu */}
              <div className="flex flex-col sm:flex-row items-center justify-between gap-2 p-2.5 rounded-lg bg-zinc-950/40 border border-zinc-800/40 text-xs font-mono">
                <div className="flex items-center gap-2">
                  <span className="text-zinc-500">Takasbank Teminat Stresi:</span>
                  <span className="text-emerald-400 font-semibold px-2 py-0.5 rounded bg-emerald-500/10 border border-emerald-500/20">
                    {viopData?.teminat_tamamlama_durumu ?? "Normal (Düşük Sıkışma)"}
                  </span>
                </div>
                <div className="text-zinc-400">
                  Açık Pozisyon: <span className="text-zinc-200 font-bold">{viopData?.acik_pozisyon_lot ? Number(viopData.acik_pozisyon_lot).toLocaleString("tr-TR") : "342.500"} lot</span>
                  <span className="text-emerald-400 ml-1.5">(+{viopData?.acik_pozisyon_gunluk_degisim ?? "14.200"} lot)</span>
                </div>
              </div>
            </div>

            {/* Küresel İklim & Vadeli Barometresi (5 kolon) */}
            <div className="lg:col-span-5 rounded-xl border border-zinc-800/80 bg-zinc-900/60 p-4">
              <div className="flex items-center justify-between mb-3 pb-2 border-b border-zinc-800/60">
                <div className="flex items-center gap-2">
                  <span className="text-[10px] font-mono uppercase tracking-wider text-purple-400 font-bold px-2 py-0.5 rounded bg-purple-400/10 border border-purple-400/20">
                    Küresel İklim
                  </span>
                  <span className="text-xs font-bold text-zinc-200">Açılış Vadeli & Emtia Barometresi</span>
                </div>
                <span className="text-[10px] font-mono text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded border border-emerald-500/20 font-bold">
                  İklim: Pozitif Risk İştahı
                </span>
              </div>

              <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                {[
                  { label: "S&P 500 Vadeli", val: "7.706,17", chg: "+1,81%", up: true },
                  { label: "NASDAQ Vadeli", val: "25.886,32", chg: "+2,03%", up: true },
                  { label: "DAX Vadeli", val: "26.437,67", chg: "+2,22%", up: true },
                  { label: "Brent Petrol", val: "$74,20", chg: "+1,42%", up: true },
                  { label: "Ons Altın", val: "$4.076", chg: "+3,45%", up: true },
                  { label: "VIX Korku", val: "17,22", chg: "-18,10%", up: false },
                ].map((item, idx) => (
                  <div key={idx} className="p-2 rounded-lg bg-zinc-950/70 border border-zinc-800/60 font-mono">
                    <span className="text-[10px] text-zinc-500 block truncate">{item.label}</span>
                    <div className="flex items-baseline justify-between mt-1">
                      <span className="text-xs font-bold text-zinc-200">{item.val}</span>
                      <span className={`text-[11px] font-bold ${item.up ? "text-emerald-400" : "text-rose-400"}`}>
                        {item.chg}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* ── 2. ROW: BIST-30 GÜNLÜK PİVOT MASASI & CANLI KAP İSTİHBARATI ─ */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
          {/* BIST-30 PİVOT & TEKNİK SEVİYELER (7 kolon) */}
          {panels.pivotDesk && (
            <div className={`${panels.kapStream ? "lg:col-span-7" : "lg:col-span-12"} rounded-xl border border-zinc-800/80 bg-zinc-900/60 p-4`}>
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4 pb-3 border-b border-zinc-800/60">
                <div className="flex items-center gap-2">
                  <span className="text-[10px] font-mono uppercase tracking-wider text-sky-400 font-bold px-2 py-0.5 rounded bg-sky-400/10 border border-sky-400/20">
                    Teknik Masa
                  </span>
                  <span className="text-xs font-bold text-zinc-200">Günün Pivot & Kritik Seviyeleri</span>
                </div>

                {/* Hisse Seçici */}
                <div className="flex items-center gap-2">
                  <select
                    value={selectedTicker}
                    onChange={(e) => setSelectedTicker(e.target.value)}
                    className="px-2.5 py-1 rounded bg-zinc-950 border border-zinc-700 text-xs font-mono font-bold text-amber-400 focus:outline-none focus:border-amber-400 cursor-pointer"
                  >
                    {availableTickers.map((t) => (
                      <option key={t} value={t}>
                        {t} — {quantData?.[t]?.fundamental?.sirket || t}
                      </option>
                    ))}
                  </select>
                  <Link
                    href={`/hisse/${selectedTicker}`}
                    className="p-1 rounded bg-zinc-950 border border-zinc-700 text-zinc-400 hover:text-white"
                    title="Hisse Detayına Git"
                  >
                    <ExternalLink className="w-3.5 h-3.5" />
                  </Link>
                </div>
              </div>

              {/* Seçili Hisse Üst Bilgi Kartı */}
              <div className="flex items-baseline justify-between p-3 rounded-lg bg-zinc-950/80 border border-zinc-800/80 mb-4 font-mono">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="text-xl font-bold text-white">{selectedTicker}</span>
                    <span className="text-xs text-zinc-400 truncate max-w-[200px]">
                      {fundamental?.sirket ?? "Şirket Bilgisi"}
                    </span>
                  </div>
                  <span className="text-[11px] text-zinc-500">{fundamental?.sektor ?? "-"}</span>
                </div>
                <div className="text-right">
                  <span className="text-2xl font-bold text-zinc-100 block">
                    {keyLevels?.son_fiyat ? `${keyLevels.son_fiyat.toFixed(2)} ₺` : "259.50 ₺"}
                  </span>
                  <span
                    className={`text-xs font-bold ${
                      (keyLevels?.gunluk_degisim_yuzde ?? 0) >= 0 ? "text-emerald-400" : "text-rose-400"
                    }`}
                  >
                    {(keyLevels?.gunluk_degisim_yuzde ?? 0) >= 0 ? "+" : ""}
                    {keyLevels?.gunluk_degisim_yuzde ? `${keyLevels.gunluk_degisim_yuzde.toFixed(2)}%` : "+7.14%"}
                  </span>
                </div>
              </div>

              {/* PİVOT SEVİYELERİ TABLOSU */}
              <div className="grid grid-cols-2 sm:grid-cols-5 gap-2 mb-4 font-mono text-center">
                <div className="p-2 rounded bg-rose-950/30 border border-rose-900/50">
                  <span className="text-[10px] text-rose-400 uppercase font-semibold block">S2 (Kritik Destek)</span>
                  <span className="text-xs font-bold text-zinc-200">
                    {keyLevels?.destekler?.s2 ? `${keyLevels.destekler.s2.toFixed(2)} ₺` : "-"}
                  </span>
                </div>
                <div className="p-2 rounded bg-rose-950/20 border border-rose-900/30">
                  <span className="text-[10px] text-rose-300 uppercase font-semibold block">S1 (Destek)</span>
                  <span className="text-xs font-bold text-zinc-200">
                    {keyLevels?.destekler?.s1 ? `${keyLevels.destekler.s1.toFixed(2)} ₺` : "-"}
                  </span>
                </div>
                <div className="p-2 rounded bg-amber-500/10 border border-amber-500/30">
                  <span className="text-[10px] text-amber-400 uppercase font-bold block">PIVOT NOKTASI</span>
                  <span className="text-xs font-bold text-amber-300">
                    {keyLevels?.pivot_noktasi ? `${keyLevels.pivot_noktasi.toFixed(2)} ₺` : "-"}
                  </span>
                </div>
                <div className="p-2 rounded bg-emerald-950/20 border border-emerald-900/30">
                  <span className="text-[10px] text-emerald-300 uppercase font-semibold block">R1 (Direnç)</span>
                  <span className="text-xs font-bold text-zinc-200">
                    {keyLevels?.direncler?.r1 ? `${keyLevels.direncler.r1.toFixed(2)} ₺` : "-"}
                  </span>
                </div>
                <div className="p-2 rounded bg-emerald-950/30 border border-emerald-900/50">
                  <span className="text-[10px] text-emerald-400 uppercase font-semibold block">R2 (Ana Hedef)</span>
                  <span className="text-xs font-bold text-zinc-200">
                    {keyLevels?.direncler?.r2 ? `${keyLevels.direncler.r2.toFixed(2)} ₺` : "-"}
                  </span>
                </div>
              </div>

              {/* Teknik İndikatörler & Ortalamalar */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs font-mono">
                <div className="p-2 rounded bg-zinc-950/50 border border-zinc-800/40">
                  <span className="text-[10px] text-zinc-500 block">20G Hareketli Ort.</span>
                  <span className="font-bold text-zinc-300">
                    {keyLevels?.hareketli_ortalamalar?.sma_20 ? `${keyLevels.hareketli_ortalamalar.sma_20.toFixed(2)} ₺` : "-"}
                  </span>
                </div>
                <div className="p-2 rounded bg-zinc-950/50 border border-zinc-800/40">
                  <span className="text-[10px] text-zinc-500 block">50G Hareketli Ort.</span>
                  <span className="font-bold text-zinc-300">
                    {keyLevels?.hareketli_ortalamalar?.sma_50 ? `${keyLevels.hareketli_ortalamalar.sma_50.toFixed(2)} ₺` : "-"}
                  </span>
                </div>
                <div className="p-2 rounded bg-zinc-950/50 border border-zinc-800/40">
                  <span className="text-[10px] text-zinc-500 block">RSI (14) Göstergesi</span>
                  <span className="font-bold text-amber-400">
                    {keyLevels?.rsi_14 ? `${keyLevels.rsi_14.toFixed(0)}` : "33"} — {keyLevels?.rsi_bolgesi ?? "Nötr"}
                  </span>
                </div>
                <div className="p-2 rounded bg-zinc-950/50 border border-zinc-800/40">
                  <span className="text-[10px] text-zinc-500 block">Zirveye Uzaklık</span>
                  <span className="font-bold text-rose-400">
                    {keyLevels?.zirveye_uzaklik_yuzde ? `${keyLevels.zirveye_uzaklik_yuzde.toFixed(1)}%` : "-27.0%"}
                  </span>
                </div>
              </div>
            </div>
          )}

          {/* CANLI KAP & İSTİHBARAT AKIŞI (5 kolon) */}
          {panels.kapStream && (
            <div className={`${panels.pivotDesk ? "lg:col-span-5" : "lg:col-span-12"} rounded-xl border border-zinc-800/80 bg-zinc-900/60 p-4 flex flex-col`}>
              <div className="flex items-center justify-between mb-3 pb-2 border-b border-zinc-800/60">
                <div className="flex items-center gap-2">
                  <span className="text-[10px] font-mono uppercase tracking-wider text-rose-400 font-bold px-2 py-0.5 rounded bg-rose-400/10 border border-rose-400/20">
                    KAP Canlı
                  </span>
                  <span className="text-xs font-bold text-zinc-200">Şirket & Makro İstihbarat</span>
                </div>
                <span className="text-[10px] font-mono text-zinc-500">
                  {filteredReports.length} bildirim
                </span>
              </div>

              {/* Filtre Sekmeleri */}
              <div className="flex items-center gap-1 overflow-x-auto pb-2 mb-2 text-[11px] font-medium no-scrollbar">
                {[
                  { id: "all", label: "Tümü" },
                  { id: "mega", label: "Mega İşler" },
                  { id: "financial", label: "Bilanço" },
                  { id: "buyback", label: "Geri Alım" },
                  { id: "macro", label: "Makro" },
                ].map((tab) => (
                  <button
                    key={tab.id}
                    onClick={() => setKapFilter(tab.id as any)}
                    className={`px-2.5 py-1 rounded whitespace-nowrap transition-colors ${
                      kapFilter === tab.id
                        ? "bg-zinc-800 text-amber-400 font-bold border border-zinc-700"
                        : "text-zinc-400 hover:text-white hover:bg-zinc-800/50"
                    }`}
                  >
                    {tab.label}
                  </button>
                ))}
              </div>

              {/* Rapor Listesi */}
              <div className="flex-1 overflow-y-auto space-y-2 max-h-[360px] pr-1">
                {filteredReports.slice(0, 15).map((rep) => (
                  <Link
                    key={rep.slug}
                    href={`/rapor/${rep.slug}`}
                    className="block p-2.5 rounded-lg bg-zinc-950/50 border border-zinc-800/50 hover:border-zinc-700 hover:bg-zinc-900/80 transition-all group"
                  >
                    <div className="flex items-center justify-between text-[10px] font-mono text-zinc-500 mb-1">
                      <span className="text-amber-400/90 font-bold uppercase">
                        {rep.category || "KAP"}
                      </span>
                      <span>
                        {new Date(rep.publishedAt).toLocaleTimeString("tr-TR", { hour: "2-digit", minute: "2-digit" })}
                      </span>
                    </div>
                    <p className="text-xs font-semibold text-zinc-200 group-hover:text-amber-300 line-clamp-2 leading-snug">
                      {rep.title}
                    </p>
                  </Link>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* ── 3. ROW: BIST-30 QUANT ÇARPAN & DEĞERLEME MATRİSİ ───────── */}
        {panels.quantMatrix && (
          <div className="rounded-xl border border-zinc-800/80 bg-zinc-900/60 p-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-3 pb-2 border-b border-zinc-800/60">
              <div className="flex items-center gap-2">
                <span className="text-[10px] font-mono uppercase tracking-wider text-emerald-400 font-bold px-2 py-0.5 rounded bg-emerald-400/10 border border-emerald-400/20">
                  Quant Masası
                </span>
                <span className="text-xs font-bold text-zinc-200">
                  BIST-30 Çoklu Çarpan, Kârlılık & DCF İskonto Matrisi
                </span>
              </div>
              <span className="text-[11px] font-mono text-zinc-500">
                Sütun başlıklarına tıklayarak sıralayabilirsiniz
              </span>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse text-xs font-mono">
                <thead>
                  <tr className="border-b border-zinc-800 text-[10px] text-zinc-500 uppercase tracking-wider">
                    <th
                      className="py-2 px-3 cursor-pointer hover:text-white"
                      onClick={() => {
                        setQuantSortField("ticker");
                        setQuantSortAsc(!quantSortAsc);
                      }}
                    >
                      Hisse
                    </th>
                    <th
                      className="py-2 px-3 text-right cursor-pointer hover:text-white"
                      onClick={() => {
                        setQuantSortField("fiyat");
                        setQuantSortAsc(!quantSortAsc);
                      }}
                    >
                      Son Fiyat
                    </th>
                    <th className="py-2 px-3 text-right">Günlük %</th>
                    <th
                      className="py-2 px-3 text-right cursor-pointer hover:text-white"
                      onClick={() => {
                        setQuantSortField("fk");
                        setQuantSortAsc(!quantSortAsc);
                      }}
                    >
                      F/K
                    </th>
                    <th
                      className="py-2 px-3 text-right cursor-pointer hover:text-white"
                      onClick={() => {
                        setQuantSortField("pddd");
                        setQuantSortAsc(!quantSortAsc);
                      }}
                    >
                      PD/DD
                    </th>
                    <th className="py-2 px-3 text-right">FD/FAVÖK</th>
                    <th className="py-2 px-3 text-right">ROE (%)</th>
                    <th
                      className="py-2 px-3 text-right cursor-pointer hover:text-white"
                      onClick={() => {
                        setQuantSortField("upside");
                        setQuantSortAsc(!quantSortAsc);
                      }}
                    >
                      DCF Prim Potansiyeli
                    </th>
                    <th className="py-2 px-3 text-center">İşlem</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-zinc-800/40">
                  {sortedQuantRows.slice(0, 12).map((row: any) => (
                    <tr key={row.ticker} className="hover:bg-zinc-800/40 transition-colors">
                      <td className="py-2.5 px-3 font-bold text-amber-400">
                        <button
                          onClick={() => setSelectedTicker(row.ticker)}
                          className="hover:underline text-left cursor-pointer"
                        >
                          {row.ticker}
                        </button>
                      </td>
                      <td className="py-2.5 px-3 text-right text-zinc-200">
                        {row.sonFiyat > 0 ? `${row.sonFiyat.toFixed(2)} ₺` : "-"}
                      </td>
                      <td
                        className={`py-2.5 px-3 text-right font-bold ${
                          row.changePct >= 0 ? "text-emerald-400" : "text-rose-400"
                        }`}
                      >
                        {row.changePct >= 0 ? "+" : ""}
                        {row.changePct.toFixed(2)}%
                      </td>
                      <td className="py-2.5 px-3 text-right text-zinc-300">
                        {row.fk < 900 ? row.fk.toFixed(1) : "-"}
                      </td>
                      <td className="py-2.5 px-3 text-right text-zinc-300">
                        {row.pddd < 900 ? row.pddd.toFixed(2) : "-"}
                      </td>
                      <td className="py-2.5 px-3 text-right text-zinc-400">
                        {row.fdFavok < 900 ? row.fdFavok.toFixed(1) : "-"}
                      </td>
                      <td className="py-2.5 px-3 text-right text-emerald-400">
                        %{row.roe.toFixed(1)}
                      </td>
                      <td className="py-2.5 px-3 text-right font-bold text-amber-300">
                        {row.upside > 0 ? `+%${row.upside.toFixed(1)}` : "%0"}
                      </td>
                      <td className="py-2.5 px-3 text-center">
                        <Link
                          href={`/hisse/${row.ticker}`}
                          className="inline-flex items-center gap-1 text-[11px] text-zinc-400 hover:text-white px-2 py-0.5 rounded bg-zinc-800/60 border border-zinc-700/60"
                        >
                          Analiz <ChevronRight className="w-3 h-3" />
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* ── 4. ROW: GERİ ALIMLAR & TEMETTÜ TAKVİMİ ──────────────────── */}
        {(panels.buybacks || panels.dividends) && (
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
            {/* Pay Geri Alımları (6 kolon) */}
            {panels.buybacks && (
              <div className={`${panels.dividends ? "lg:col-span-6" : "lg:col-span-12"} rounded-xl border border-zinc-800/80 bg-zinc-900/60 p-4`}>
                <div className="flex items-center justify-between mb-3 pb-2 border-b border-zinc-800/60">
                  <div className="flex items-center gap-2">
                    <span className="text-[10px] font-mono uppercase tracking-wider text-amber-400 font-bold px-2 py-0.5 rounded bg-amber-400/10 border border-amber-400/20">
                      Geri Alım
                    </span>
                    <span className="text-xs font-bold text-zinc-200">Aktif Şirket Pay Geri Alımları</span>
                  </div>
                  <Link href="/piyasa/geri-alimlar" className="text-[11px] text-zinc-400 hover:text-white">
                    Tümü →
                  </Link>
                </div>

                <div className="space-y-2 font-mono text-xs">
                  {(buybacksData?.programs || []).slice(0, 4).map((prog: any) => (
                    <div key={prog.ticker} className="p-2.5 rounded-lg bg-zinc-950/60 border border-zinc-800/60 flex items-center justify-between">
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="font-bold text-amber-400">{prog.ticker}</span>
                          <span className="text-[11px] text-zinc-400 truncate max-w-[150px]">{prog.sirket}</span>
                        </div>
                        <span className="text-[10px] text-zinc-500">Fon: {prog.ayrilan_fon_fmt}</span>
                      </div>
                      <div className="text-right">
                        <span className="text-xs font-bold text-emerald-400">%{prog.tamamlanma_orani_yuzde} Dolu</span>
                        <span className="text-[10px] text-zinc-500 block">Getiri: +%{prog.maliyete_gore_getiri_yuzde}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Temettü Takvimi (6 kolon) */}
            {panels.dividends && (
              <div className={`${panels.buybacks ? "lg:col-span-6" : "lg:col-span-12"} rounded-xl border border-zinc-800/80 bg-zinc-900/60 p-4`}>
                <div className="flex items-center justify-between mb-3 pb-2 border-b border-zinc-800/60">
                  <div className="flex items-center gap-2">
                    <span className="text-[10px] font-mono uppercase tracking-wider text-sky-400 font-bold px-2 py-0.5 rounded bg-sky-400/10 border border-sky-400/20">
                      Temettü
                    </span>
                    <span className="text-xs font-bold text-zinc-200">Günün & Yaklaşan Temettü Takvimi</span>
                  </div>
                  <Link href="/piyasa/temettu-takvimi" className="text-[11px] text-zinc-400 hover:text-white">
                    Tümü →
                  </Link>
                </div>

                <div className="space-y-2 font-mono text-xs">
                  {(dividendsData?.dividends || []).slice(0, 4).map((div: any, i: number) => (
                    <div key={i} className="p-2.5 rounded-lg bg-zinc-950/60 border border-zinc-800/60 flex items-center justify-between">
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="font-bold text-sky-400">{div.ticker}</span>
                          <span className="text-[11px] text-zinc-400">{div.sirket}</span>
                        </div>
                        <span className="text-[10px] text-zinc-500">Tarih: {div.hak_kullanim_tarihi || "Kasım 2026"}</span>
                      </div>
                      <div className="text-right">
                        <span className="text-xs font-bold text-emerald-400">Verim: %{div.temettu_verimi_yuzde || "5.2"}</span>
                        <span className="text-[10px] text-zinc-400 block">{div.hisse_basi_net_tl || "2.40"} ₺ / Lot</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* ── 5. ROW: MAKRO CDS & PETROL TANKER NAVLUN ─────────────────── */}
        {(panels.macroRadar || panels.oilTanker) && (
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
            {panels.macroRadar && (
              <div className={`${panels.oilTanker ? "lg:col-span-6" : "lg:col-span-12"} rounded-xl border border-zinc-800/80 bg-zinc-900/60 p-4`}>
                <div className="flex items-center justify-between mb-3 pb-2 border-b border-zinc-800/60">
                  <span className="text-xs font-bold text-zinc-200">Türkiye 5Y CDS & Devalüasyon Radarı</span>
                  <span className="text-xs font-mono text-emerald-400 font-bold">CDS: 254 bps (-18 bps)</span>
                </div>
                <div className="grid grid-cols-3 gap-2 text-xs font-mono">
                  <div className="p-2 rounded bg-zinc-950/60 border border-zinc-800/60">
                    <span className="text-[10px] text-zinc-500 block">TCMB Net Rezerv</span>
                    <span className="font-bold text-emerald-400">+$34.6 Mr</span>
                  </div>
                  <div className="p-2 rounded bg-zinc-950/60 border border-zinc-800/60">
                    <span className="text-[10px] text-zinc-500 block">Hisse Risk Primi (ERP)</span>
                    <span className="font-bold text-amber-400">%8.4</span>
                  </div>
                  <div className="p-2 rounded bg-zinc-950/60 border border-zinc-800/60">
                    <span className="text-[10px] text-zinc-500 block">Mevduat Faizi</span>
                    <span className="font-bold text-zinc-200">%51.5</span>
                  </div>
                </div>
              </div>
            )}

            {panels.oilTanker && (
              <div className={`${panels.macroRadar ? "lg:col-span-6" : "lg:col-span-12"} rounded-xl border border-zinc-800/80 bg-zinc-900/60 p-4`}>
                <div className="flex items-center justify-between mb-3 pb-2 border-b border-zinc-800/60">
                  <span className="text-xs font-bold text-zinc-200">Petrol & Tanker Navlun (TCE $/gün)</span>
                  <Link href="/tarim-emtia?tab=petrolTanker" className="text-[11px] text-amber-400">
                    Terminal Detayı →
                  </Link>
                </div>
                <div className="grid grid-cols-3 gap-2 text-xs font-mono">
                  <div className="p-2 rounded bg-zinc-950/60 border border-zinc-800/60">
                    <span className="text-[10px] text-zinc-500 block">Akdeniz 3:2:1 Crack</span>
                    <span className="font-bold text-emerald-400">$18.40/bbl</span>
                  </div>
                  <div className="p-2 rounded bg-zinc-950/60 border border-zinc-800/60">
                    <span className="text-[10px] text-zinc-500 block">VLCC TCE Navlun</span>
                    <span className="font-bold text-amber-400">$46.200/gün</span>
                  </div>
                  <div className="p-2 rounded bg-zinc-950/60 border border-zinc-800/60">
                    <span className="text-[10px] text-zinc-500 block">Aframax Ceyhan TCE</span>
                    <span className="font-bold text-zinc-200">$34.500/gün</span>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
