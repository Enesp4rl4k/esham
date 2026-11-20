"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import {
  Wheat,
  Beef,
  Scale,
  Warehouse,
  Truck,
  TrendingUp,
  TrendingDown,
  Minus,
  Download,
  Copy,
  Check,
  Terminal,
  ExternalLink,
  ShieldCheck,
  Search,
  Sparkles,
  Layers,
  ArrowRight,
  Database,
  Fuel,
} from "lucide-react";
import { PetrolTankerSection } from "@/components/PetrolTankerSection";

export interface PetrolTankerDataset {
  updatedAt?: string;
  date?: string;
  oilBenchmarks?: {
    brent?: { price: number; priceStr: string; changePct: number; changeStr: string };
    wti?: { price: number; priceStr: string; changePct: number; changeStr: string };
    brentWtiSpread?: number;
    urals?: { price: number; discount: number; priceStr: string; g7Cap: number };
    crackSpread321?: { value: number; valueStr: string; interpretation: string };
  };
  freightIndices?: {
    bdti?: { value: number; change: number; label: string };
    bcti?: { value: number; change: number; label: string };
    vlsfoBunker?: { value: number; unit: string };
  };
  rates?: Array<{
    ship_class: string;
    dwt_capacity: string;
    route_code: string;
    route_desc: string;
    daily_rate_usd: number;
    daily_rate_str: string;
    change_usd: number;
    change_pct: number;
    change_str: string;
    worldscale: number;
    fuel_consumption_ton: number;
    cargo_type: string;
    status: string;
    commentary: string;
  }>;
  chokepoints?: Array<{
    name: string;
    flow_mbpd: string;
    wait_time_days: string;
    demurrage_usd_day: string;
    security_level: string;
    impact: string;
  }>;
  bistImpacts?: Array<{
    ticker: string;
    company: string;
    driver: string;
    impact_level: string;
    commentary: string;
  }>;
}

export interface TuribMarketDataset {
  updatedAt: string;
  date: string;
  indices: Array<{
    code: string;
    name: string;
    value: number;
    valueStr: string;
    change: number;
    changePct: number;
    changeStr: string;
    high: number;
    low: number;
    volumeTon: number;
    volumeStr: string;
  }>;
  spotCommodities: Array<{
    name: string;
    code: string;
    avgPrice: number;
    avgPriceStr: string;
    minPrice: number;
    maxPrice: number;
    changePct: number;
    changeStr: string;
    volumeTon: number;
    volumeStr: string;
    volumeTl: number;
    volumeTlStr: string;
  }>;
  bulletinSummary: {
    totalVolumeTon?: number;
    totalVolumeTonStr?: string;
    totalValueTl?: number;
    totalValueTlStr?: string;
    hububatIndex?: number;
    summaryText?: string;
  };
  meatFeed: {
    cpiDate?: string;
    meatCpi?: number;
    headlineCpi?: number;
    meatCpiAnnualPct?: number;
    headlineCpiAnnualPct?: number;
    meatInflationSpread?: number;
    macroCommentary?: string;
    bistSectorImpact?: string;
    parities: Array<{
      title: string;
      meatType: string;
      feedType: string;
      meatPrice: number;
      feedPrice: number;
      ratio: number;
      threshold: number;
      isProfitable: boolean;
      status: string;
      interpretation: string;
    }>;
  };
  tmoComparison: Array<{
    commodity: string;
    tmoProductName: string;
    year: number;
    tmoPurchasePrice: number;
    farmerPremium: number;
    totalFarmerIncome: number;
    tmoSalesPrice: number | null;
    turibFreePrice: number;
    spreadTl: number;
    spreadPct: number;
    totalSpreadPct: number;
    status: string;
    commentary: string;
  }>;
  storageBacktest: {
    productGroup?: string;
    testedSeasonsCount?: number;
    annualInterestPct?: number;
    winRate3mPct?: number;
    winRate6mPct?: number;
    winRate9mPct?: number;
    avgNetReturn6mPct?: number;
    bestStrategy?: string;
    strategicAdvice?: string;
    seasons?: Array<{
      seasonYear: number;
      harvestMonth: string;
      harvestSpotPrice: number;
      winningStrategy: string;
      strategies: Array<{
        strategyName: string;
        termMonths: number;
        saleMonth: string;
        salePrice: number;
        grossSpread: number;
        storageCost: number;
        interestCost: number;
        shrinkageCost: number;
        totalCost: number;
        netProfitTl: number;
        netReturnPct: number;
        beatSpot: boolean;
      }>;
    }>;
  };
  regionalArbitrage: {
    date?: string;
    totalScannedTrades?: number;
    evaluation?: string;
    opportunities: Array<{
      commodity: string;
      cheapCity: string;
      cheapLidas: string;
      cheapPrice: number;
      expensiveCity: string;
      expensiveLidas: string;
      expensivePrice: number;
      grossSpread: number;
      freightCost: number;
      netArbitrage: number;
      netArbitragePct: number;
      opportunityLevel: string;
      notes: string;
    }>;
  };
  agriBist: {
    date?: string;
    xgidaPrice?: string;
    xgidaChange?: string;
    turibHububatIndex?: string;
    turibHububatChange?: string;
    macroTakeaway?: string;
    companies: Array<{
      ticker: string;
      companyName: string;
      stockPrice: string;
      stockChange: string;
      commodity: string;
      commodityPrice: string;
      commodityChange: string;
      marginPressure: string;
      commentary: string;
    }>;
  };
  realReturns: Array<{
    commodityGroup: string;
    startDate: string;
    endDate: string;
    tradingDays: number;
    startPriceTl: number;
    endPriceTl: number;
    nominalReturnPct: number;
    usdReturnPct: number;
    eurReturnPct: number;
    realInflationReturnPct: number;
    commentary: string;
  }>;
  petrolTanker?: PetrolTankerDataset;
}

export function TuribMarketClient({
  dataset,
  initialTab,
}: {
  dataset: TuribMarketDataset;
  initialTab?: string;
}) {
  const [activeTab, setActiveTab] = useState<
    "all" | "petrolTanker" | "indices" | "meatFeed" | "tmoStorage" | "arbitrage" | "agriBist" | "api"
  >((initialTab as any) || "all");

  useEffect(() => {
    if (typeof window !== "undefined") {
      const params = new URLSearchParams(window.location.search);
      const tabParam = params.get("tab");
      if (
        tabParam &&
        ["all", "petrolTanker", "indices", "meatFeed", "tmoStorage", "arbitrage", "agriBist", "api"].includes(
          tabParam
        )
      ) {
        setActiveTab(tabParam as any);
      }
    }
  }, []);
  const [copiedUrl, setCopiedUrl] = useState(false);
  const [copiedMcp, setCopiedMcp] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");

  const handleCopyUrl = async () => {
    try {
      const fullUrl = `${window.location.origin}/data/turib-market.json`;
      await navigator.clipboard.writeText(fullUrl);
      setCopiedUrl(true);
      setTimeout(() => setCopiedUrl(false), 2500);
    } catch {
      // fallback
    }
  };

  const mcpConfigCode = `{
  "mcpServers": {
    "esham-market": {
      "command": "python",
      "args": ["-m", "esham.main", "mcp"],
      "cwd": "C:\\\\Users\\\\eparl\\\\Documents\\\\Default Project\\\\esham\\\\bot"
    }
  }
}`;

  const handleCopyMcp = async () => {
    try {
      await navigator.clipboard.writeText(mcpConfigCode);
      setCopiedMcp(true);
      setTimeout(() => setCopiedMcp(false), 2500);
    } catch {
      // fallback
    }
  };

  const filteredSpot = dataset.spotCommodities.filter((p) =>
    searchQuery === ""
      ? true
      : p.name.toLocaleLowerCase("tr-TR").includes(searchQuery.toLocaleLowerCase("tr-TR"))
  );

  const filteredArb = (dataset.regionalArbitrage.opportunities || []).filter((o) =>
    searchQuery === ""
      ? true
      : o.commodity.toLocaleLowerCase("tr-TR").includes(searchQuery.toLocaleLowerCase("tr-TR")) ||
        o.cheapCity.toLocaleLowerCase("tr-TR").includes(searchQuery.toLocaleLowerCase("tr-TR")) ||
        o.expensiveCity.toLocaleLowerCase("tr-TR").includes(searchQuery.toLocaleLowerCase("tr-TR"))
  );

  return (
    <div className="space-y-12">
      {/* ── Top Bar: Actions & Summary ── */}
      <div
        className="rounded-2xl border p-6 md:p-8 relative overflow-hidden"
        style={{
          background: "linear-gradient(135deg, var(--surface) 0%, rgba(232, 160, 48, 0.04) 100%)",
          borderColor: "var(--border)",
        }}
      >
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-6">
          <div>
            <div className="flex flex-wrap items-center gap-2 mb-3">
              <span
                className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold border"
                style={{
                  background: "var(--accent-glow)",
                  borderColor: "var(--accent-dim)",
                  color: "var(--accent)",
                }}
              >
                <Database className="w-3.5 h-3.5" />
                CANLI TÜRİB & ELÜS VERİ SETİ
              </span>
              <span className="text-xs" style={{ color: "var(--text-muted)" }}>
                Son Güncelleme: {new Date(dataset.updatedAt).toLocaleString("tr-TR", { timeZone: "Europe/Istanbul" })}
              </span>
            </div>
            <h1 className="text-2xl md:text-4xl font-display font-bold tracking-tight mb-2">
              Tarımsal Emtia, TÜRİB & Et-Yem Terminali
            </h1>
            <p className="text-sm md:text-base max-w-2xl leading-relaxed" style={{ color: "var(--text-secondary)" }}>
              Türkiye Ürün İhtisas Borsası (TÜRİB) lisanslı depo işlem fiyatları, et-yem pariteleri,
              TÜİK Et TÜFE enflasyon göstergesi, TMO müdahale fiyatları ve BIST tarım-gıda entegrasyonu.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <a
              href="/data/turib-market.json"
              download="turib-market.json"
              className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl text-xs font-semibold font-sans transition-all cursor-pointer shadow-sm hover:scale-[1.02]"
              style={{
                background: "var(--accent)",
                color: "#1a1200",
              }}
            >
              <Download className="w-4 h-4" />
              JSON Verisini İndir
            </a>

            <button
              onClick={handleCopyUrl}
              className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl text-xs font-semibold border transition-all cursor-pointer hover:border-[var(--accent)]"
              style={{
                background: "var(--surface-2)",
                borderColor: "var(--border-2)",
                color: "var(--text-primary)",
              }}
            >
              {copiedUrl ? <Check className="w-4 h-4 text-emerald-400" /> : <Copy className="w-4 h-4" />}
              {copiedUrl ? "URL Kopyalandı!" : "API / JSON URL'i"}
            </button>

            <button
              onClick={() => setActiveTab("api")}
              className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl text-xs font-semibold border transition-all cursor-pointer hover:border-[var(--accent)]"
              style={{
                background: "var(--surface-2)",
                borderColor: "var(--border-2)",
                color: "var(--text-primary)",
              }}
            >
              <Terminal className="w-4 h-4 text-amber-400" />
              MCP Entegrasyonu
            </button>
          </div>
        </div>

        {/* Bülten Hızlı İstatistikleri */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mt-8 pt-6 border-t" style={{ borderColor: "var(--border)" }}>
          <div>
            <p className="text-xs uppercase tracking-wider font-semibold" style={{ color: "var(--text-muted)" }}>
              Toplam Günlük Hacim
            </p>
            <p className="text-lg md:text-xl font-bold mt-1" style={{ color: "var(--text-primary)" }}>
              {dataset.bulletinSummary.totalVolumeTonStr || "625.021,1 Ton"}
            </p>
          </div>
          <div>
            <p className="text-xs uppercase tracking-wider font-semibold" style={{ color: "var(--text-muted)" }}>
              İşlem Tutarı
            </p>
            <p className="text-lg md:text-xl font-bold mt-1" style={{ color: "var(--accent)" }}>
              {dataset.bulletinSummary.totalValueTlStr || "11,5 Milyar ₺"}
            </p>
          </div>
          <div>
            <p className="text-xs uppercase tracking-wider font-semibold" style={{ color: "var(--text-muted)" }}>
              Dana / Yem Paritesi
            </p>
            <p className="text-lg md:text-xl font-bold mt-1 text-emerald-400 flex items-center gap-1.5">
              {dataset.meatFeed.parities?.[0]?.ratio
                ? `${dataset.meatFeed.parities[0].ratio.toFixed(1)}x`
                : "28.2x"}
              <span className="text-xs px-2 py-0.5 rounded bg-emerald-500/10 border border-emerald-500/30 text-emerald-400">
                Kârlı Alan
              </span>
            </p>
          </div>
          <div>
            <p className="text-xs uppercase tracking-wider font-semibold" style={{ color: "var(--text-muted)" }}>
              Yıllık Et TÜFE
            </p>
            <p className="text-lg md:text-xl font-bold mt-1" style={{ color: "var(--text-primary)" }}>
              %{dataset.meatFeed.meatCpiAnnualPct ? dataset.meatFeed.meatCpiAnnualPct.toFixed(1) : "30.5"}
              <span className="text-xs ml-2 text-emerald-400 font-normal">
                (Manşet: %{dataset.meatFeed.headlineCpiAnnualPct ? dataset.meatFeed.headlineCpiAnnualPct.toFixed(1) : "31.5"})
              </span>
            </p>
          </div>
        </div>
      </div>

      {/* ── Navigation Tabs ── */}
      <div className="flex items-center gap-2 overflow-x-auto pb-2 border-b" style={{ borderColor: "var(--border)" }}>
        {[
          { id: "all", label: "Tüm Terminal", icon: Layers },
          { id: "petrolTanker", label: "Petrol & Tanker Navlun", icon: Fuel },
          { id: "indices", label: "TÜRİB Endeks & Spot", icon: Wheat },
          { id: "meatFeed", label: "Et-Yem & TÜFE", icon: Beef },
          { id: "tmoStorage", label: "TMO & Depolama Backtest", icon: Warehouse },
          { id: "arbitrage", label: "Bölgesel Arbitraj", icon: Truck },
          { id: "agriBist", label: "Agri-BIST Hisseleri", icon: Scale },
          { id: "api", label: "Açık Veri & MCP API", icon: Terminal },
        ].map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id as any)}
              className="inline-flex items-center gap-2 px-4 py-2 rounded-xl text-xs md:text-sm font-medium whitespace-nowrap transition-all cursor-pointer"
              style={{
                background: isActive ? "var(--accent)" : "transparent",
                color: isActive ? "#1a1200" : "var(--text-secondary)",
                fontWeight: isActive ? 600 : 400,
              }}
            >
              <Icon className="w-4 h-4" />
              {tab.label}
            </button>
          );
        })}
      </div>

      {/* ── Section: Petrol Piyasası & Tanker Kiralama Navlun ── */}
      {(activeTab === "all" || activeTab === "petrolTanker") && (
        <PetrolTankerSection data={dataset.petrolTanker} />
      )}

      {/* ── Section: TÜRİB Endeksleri ── */}
      {(activeTab === "all" || activeTab === "indices") && (
        <section className="space-y-6">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div>
              <div className="flex items-center gap-2">
                <Wheat className="w-5 h-5" style={{ color: "var(--accent)" }} />
                <h2 className="text-xl md:text-2xl font-display font-bold">
                  TÜRİB Hububat & Emtia Endeksleri
                </h2>
              </div>
              <p className="text-xs md:text-sm" style={{ color: "var(--text-secondary)" }}>
                TÜRİB borsasında işlem gören lisanslı depo ürün senetlerinin fiyat hareketlerini yansıtan resmi endeksler.
              </p>
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {dataset.indices.map((idx) => {
              const isUp = idx.changePct >= 0;
              return (
                <div
                  key={idx.code}
                  className="rounded-xl border p-5 transition-all hover:border-[var(--accent)]"
                  style={{ background: "var(--surface)", borderColor: "var(--border)" }}
                >
                  <div className="flex items-center justify-between mb-3">
                    <span
                      className="px-2.5 py-0.5 rounded text-xs font-mono font-bold tracking-wider"
                      style={{ background: "var(--surface-2)", color: "var(--accent)" }}
                    >
                      {idx.code}
                    </span>
                    <span
                      className={`inline-flex items-center gap-1 text-xs font-semibold ${
                        isUp ? "text-emerald-400" : "text-red-400"
                      }`}
                    >
                      {isUp ? <TrendingUp className="w-3.5 h-3.5" /> : <TrendingDown className="w-3.5 h-3.5" />}
                      {idx.changeStr}
                    </span>
                  </div>
                  <p className="text-xs line-clamp-1 mb-2" style={{ color: "var(--text-muted)" }}>
                    {idx.name}
                  </p>
                  <p className="text-2xl font-bold font-display" style={{ color: "var(--text-primary)" }}>
                    {idx.valueStr}
                  </p>
                  <div className="mt-4 pt-3 border-t flex items-center justify-between text-xs" style={{ borderColor: "var(--border)" }}>
                    <span style={{ color: "var(--text-muted)" }}>Hacim: {idx.volumeStr}</span>
                    <span style={{ color: "var(--text-muted)" }}>
                      {idx.low > 0 ? `${idx.low.toFixed(1)} - ${idx.high.toFixed(1)}` : "Seans Aktif"}
                    </span>
                  </div>
                </div>
              );
            })}
          </div>

          {/* Spot Emtia Tablosu */}
          <div className="rounded-xl border overflow-hidden" style={{ background: "var(--surface)", borderColor: "var(--border)" }}>
            <div className="p-4 md:p-6 border-b flex flex-col sm:flex-row sm:items-center justify-between gap-4" style={{ borderColor: "var(--border)" }}>
              <div>
                <h3 className="font-display font-bold text-base md:text-lg">
                  TÜRİB Günlük Spot Fiyat Bülteni
                </h3>
                <p className="text-xs" style={{ color: "var(--text-muted)" }}>
                  ELÜS işlemlerinde ağırlıklı ortalama fiyatlar ve gerçekleşen seans hacimleri.
                </p>
              </div>

              <div className="relative">
                <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-zinc-400" />
                <input
                  type="text"
                  placeholder="Ürün ara (buğday, mısır, arpa)..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="pl-9 pr-4 py-2 rounded-lg text-xs border bg-zinc-900 text-zinc-100 placeholder-zinc-500 focus:outline-none focus:border-[var(--accent)] w-full sm:w-64"
                  style={{ borderColor: "var(--border)" }}
                />
              </div>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs md:text-sm">
                <thead>
                  <tr className="border-b text-xs uppercase tracking-wider" style={{ borderColor: "var(--border)", color: "var(--text-muted)" }}>
                    <th className="py-3 px-4 md:px-6">Emtia Ürünü</th>
                    <th className="py-3 px-4">Ort. Fiyat</th>
                    <th className="py-3 px-4">Değişim</th>
                    <th className="py-3 px-4">Min / Max</th>
                    <th className="py-3 px-4">Miktar (Ton)</th>
                    <th className="py-3 px-4 md:px-6 text-right">İşlem Hacmi (₺)</th>
                  </tr>
                </thead>
                <tbody className="divide-y" style={{ borderColor: "var(--border)" }}>
                  {filteredSpot.length > 0 ? (
                    filteredSpot.map((prod) => {
                      const isUp = prod.changePct >= 0;
                      return (
                        <tr key={prod.name} className="hover:bg-zinc-900/50 transition-colors">
                          <td className="py-3.5 px-4 md:px-6 font-semibold" style={{ color: "var(--text-primary)" }}>
                            {prod.name}
                          </td>
                          <td className="py-3.5 px-4 font-mono font-bold" style={{ color: "var(--accent)" }}>
                            {prod.avgPriceStr}
                          </td>
                          <td className="py-3.5 px-4">
                            <span
                              className={`inline-flex items-center gap-1 font-semibold ${
                                isUp ? "text-emerald-400" : "text-red-400"
                              }`}
                            >
                              {isUp ? <TrendingUp className="w-3.5 h-3.5" /> : <TrendingDown className="w-3.5 h-3.5" />}
                              {prod.changeStr}
                            </span>
                          </td>
                          <td className="py-3.5 px-4 font-mono text-xs" style={{ color: "var(--text-secondary)" }}>
                            {prod.minPrice > 0 ? `${prod.minPrice.toFixed(2)} - ${prod.maxPrice.toFixed(2)} ₺` : "—"}
                          </td>
                          <td className="py-3.5 px-4" style={{ color: "var(--text-secondary)" }}>
                            {prod.volumeStr}
                          </td>
                          <td className="py-3.5 px-4 md:px-6 text-right font-mono font-semibold" style={{ color: "var(--text-primary)" }}>
                            {prod.volumeTlStr}
                          </td>
                        </tr>
                      );
                    })
                  ) : (
                    <tr>
                      <td colSpan={6} className="py-8 text-center text-zinc-400">
                        Eşleşen ürün kaydı bulunamadı.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </section>
      )}

      {/* ── Section: Et-Yem Pariteleri & Et TÜFE Enflasyonu ── */}
      {(activeTab === "all" || activeTab === "meatFeed") && (
        <section className="space-y-6">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div>
              <div className="flex items-center gap-2">
                <Beef className="w-5 h-5 text-rose-400" />
                <h2 className="text-xl md:text-2xl font-display font-bold">
                  Et-Yem Paritesi & Et TÜFE Enflasyon Paneli
                </h2>
              </div>
              <p className="text-xs md:text-sm" style={{ color: "var(--text-secondary)" }}>
                Hayvancılık işletmelerinin girdi maliyeti kârlılık rasyonları ve TÜİK Et TÜFE enflasyonunun öncü sinyalleri.
              </p>
            </div>
          </div>

          {/* Et TÜFE vs Manşet TÜFE Gösterge Kartı */}
          <div
            className="rounded-xl border p-6"
            style={{ background: "var(--surface)", borderColor: "var(--border)" }}
          >
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              <div className="space-y-1 md:border-r md:pr-6" style={{ borderColor: "var(--border)" }}>
                <span className="text-xs font-semibold uppercase tracking-wider text-rose-400">
                  TÜİK Et TÜFE Yıllık
                </span>
                <p className="text-3xl font-display font-bold" style={{ color: "var(--text-primary)" }}>
                  %{dataset.meatFeed.meatCpiAnnualPct ? dataset.meatFeed.meatCpiAnnualPct.toFixed(1) : "30.5"}
                </p>
                <p className="text-xs" style={{ color: "var(--text-muted)" }}>
                  Endeks: {dataset.meatFeed.meatCpi ? dataset.meatFeed.meatCpi.toFixed(1) : "1540.0"} (Tarih: {dataset.meatFeed.cpiDate || "2026-11"})
                </p>
              </div>

              <div className="space-y-1 md:border-r md:pr-6" style={{ borderColor: "var(--border)" }}>
                <span className="text-xs font-semibold uppercase tracking-wider" style={{ color: "var(--text-muted)" }}>
                  Manşet TÜFE Enflasyonu
                </span>
                <p className="text-3xl font-display font-bold" style={{ color: "var(--text-primary)" }}>
                  %{dataset.meatFeed.headlineCpiAnnualPct ? dataset.meatFeed.headlineCpiAnnualPct.toFixed(1) : "31.5"}
                </p>
                <p className="text-xs" style={{ color: "var(--text-muted)" }}>
                  Endeks: {dataset.meatFeed.headlineCpi ? dataset.meatFeed.headlineCpi.toFixed(1) : "1210.0"}
                </p>
              </div>

              <div className="space-y-1">
                <span className="text-xs font-semibold uppercase tracking-wider text-emerald-400">
                  Et Enflasyon Primi
                </span>
                <p className="text-3xl font-display font-bold text-emerald-400">
                  {dataset.meatFeed.meatInflationSpread
                    ? `${dataset.meatFeed.meatInflationSpread > 0 ? "+" : ""}${dataset.meatFeed.meatInflationSpread.toFixed(1)}`
                    : "-1.0"}{" "}
                  <span className="text-sm font-normal">puan</span>
                </p>
                <p className="text-xs" style={{ color: "var(--text-muted)" }}>
                  Et fiyat artışı manşet enflasyonun altında seyrediyor.
                </p>
              </div>
            </div>

            {dataset.meatFeed.macroCommentary && (
              <div className="mt-6 pt-4 border-t text-xs md:text-sm leading-relaxed" style={{ borderColor: "var(--border)", color: "var(--text-secondary)" }}>
                <span className="font-semibold text-zinc-300">Makro Değerlendirme: </span>
                {dataset.meatFeed.macroCommentary}
              </div>
            )}
          </div>

          {/* Parite Kartları Grid */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {(dataset.meatFeed.parities || []).map((p, i) => {
              const isOk = p.ratio >= p.threshold;
              return (
                <div
                  key={i}
                  className="rounded-xl border p-5 flex flex-col justify-between"
                  style={{ background: "var(--surface)", borderColor: "var(--border)" }}
                >
                  <div>
                    <div className="flex items-center justify-between mb-3">
                      <span className="text-xs font-bold" style={{ color: "var(--text-primary)" }}>
                        {p.title}
                      </span>
                      <span
                        className={`text-xs font-semibold px-2 py-0.5 rounded border ${
                          isOk
                            ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-400"
                            : "bg-red-500/10 border-red-500/30 text-red-400"
                        }`}
                      >
                        {p.status}
                      </span>
                    </div>

                    <div className="flex items-baseline gap-2 mb-2">
                      <span className="text-3xl font-display font-bold" style={{ color: "var(--accent)" }}>
                        {p.ratio.toFixed(1)}
                      </span>
                      <span className="text-xs" style={{ color: "var(--text-muted)" }}>
                        (Başabaş Eşik: {p.threshold.toFixed(0)})
                      </span>
                    </div>

                    {/* Progress Bar */}
                    <div className="w-full bg-zinc-800 rounded-full h-2 mb-4 overflow-hidden relative">
                      <div
                        className={`h-full rounded-full ${isOk ? "bg-emerald-400" : "bg-red-400"}`}
                        style={{ width: `${Math.min((p.ratio / (p.threshold * 1.5)) * 100, 100)}%` }}
                      />
                    </div>

                    <div className="grid grid-cols-2 gap-2 text-xs py-2 px-3 rounded-lg bg-zinc-900/60 mb-3 border border-zinc-800/80">
                      <div>
                        <span className="text-zinc-400 block text-xs">Karkas Fiyatı</span>
                        <span className="font-semibold text-zinc-200">{p.meatPrice.toFixed(2)} ₺/kg</span>
                      </div>
                      <div>
                        <span className="text-zinc-400 block text-xs">Rasyon Yem</span>
                        <span className="font-semibold text-zinc-200">{p.feedPrice.toFixed(2)} ₺/kg</span>
                      </div>
                    </div>

                    <p className="text-xs leading-relaxed" style={{ color: "var(--text-secondary)" }}>
                      {p.interpretation}
                    </p>
                  </div>
                </div>
              );
            })}
          </div>

          {dataset.meatFeed.bistSectorImpact && (
            <div className="rounded-xl border p-4 bg-zinc-900/30 border-zinc-800/60 text-xs md:text-sm text-zinc-300">
              <span className="font-bold text-amber-400">BIST Gıda/Et Sektörü Yansıması: </span>
              {dataset.meatFeed.bistSectorImpact}
            </div>
          )}
        </section>
      )}

      {/* ── Section: TMO & LİDAŞ Depolama Backtest ── */}
      {(activeTab === "all" || activeTab === "tmoStorage") && (
        <section className="space-y-6">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div>
              <div className="flex items-center gap-2">
                <Warehouse className="w-5 h-5 text-amber-400" />
                <h2 className="text-xl md:text-2xl font-display font-bold">
                  TMO Müdahale & LİDAŞ Depolama Maliyet Analizi
                </h2>
              </div>
              <p className="text-xs md:text-sm" style={{ color: "var(--text-secondary)" }}>
                Toprak Mahsulleri Ofisi taban alım fiyatları vs. ELÜS spot piyasa ve depolama taşıma maliyeti (Cost of Carry).
              </p>
            </div>
          </div>

          {/* TMO Karşılaştırma Tablosu */}
          <div className="rounded-xl border overflow-hidden" style={{ background: "var(--surface)", borderColor: "var(--border)" }}>
            <div className="p-4 md:p-6 border-b" style={{ borderColor: "var(--border)" }}>
              <h3 className="font-display font-bold text-base md:text-lg">
                TMO Taban Alım Fiyatı vs. Serbest Piyasa ELÜS Kıyaslaması
              </h3>
              <p className="text-xs" style={{ color: "var(--text-muted)" }}>
                Üreticinin TMO yerine serbest piyasayı tercih etme prim oranları (TL/kg ve %).
              </p>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs md:text-sm">
                <thead>
                  <tr className="border-b text-xs uppercase tracking-wider" style={{ borderColor: "var(--border)", color: "var(--text-muted)" }}>
                    <th className="py-3 px-4 md:px-6">Emtia</th>
                    <th className="py-3 px-4">TMO Taban Alım</th>
                    <th className="py-3 px-4">Bakanlık Primi</th>
                    <th className="py-3 px-4">Toplam TMO Geliri</th>
                    <th className="py-3 px-4">Cari Serbest ELÜS</th>
                    <th className="py-3 px-4">Serbest Piyasa Farkı</th>
                    <th className="py-3 px-4 md:px-6 text-right">Piyasa Durumu</th>
                  </tr>
                </thead>
                <tbody className="divide-y" style={{ borderColor: "var(--border)" }}>
                  {(dataset.tmoComparison || []).map((tmo) => {
                    const isPremium = tmo.spreadTl >= 0;
                    return (
                      <tr key={tmo.commodity} className="hover:bg-zinc-900/50 transition-colors">
                        <td className="py-3.5 px-4 md:px-6 font-semibold" style={{ color: "var(--text-primary)" }}>
                          {tmo.commodity}
                        </td>
                        <td className="py-3.5 px-4 font-mono">{tmo.tmoPurchasePrice.toFixed(2)} ₺</td>
                        <td className="py-3.5 px-4 font-mono text-emerald-400">+{tmo.farmerPremium.toFixed(2)} ₺</td>
                        <td className="py-3.5 px-4 font-mono font-semibold">{tmo.totalFarmerIncome.toFixed(2)} ₺</td>
                        <td className="py-3.5 px-4 font-mono font-bold" style={{ color: "var(--accent)" }}>
                          {tmo.turibFreePrice.toFixed(2)} ₺
                        </td>
                        <td className="py-3.5 px-4">
                          <span className={`font-semibold ${isPremium ? "text-emerald-400" : "text-red-400"}`}>
                            {isPremium ? "+" : ""}
                            {tmo.spreadTl.toFixed(2)} ₺ (%{tmo.spreadPct.toFixed(1)})
                          </span>
                        </td>
                        <td className="py-3.5 px-4 md:px-6 text-right">
                          <span
                            className={`px-2 py-0.5 rounded text-xs font-semibold border ${
                              isPremium
                                ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-400"
                                : "bg-red-500/10 border-red-500/30 text-red-400"
                            }`}
                          >
                            {tmo.status.replace(/_/g, " ")}
                          </span>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>

          {/* LİDAŞ Depolama Backtest Simülasyonu */}
          {dataset.storageBacktest && dataset.storageBacktest.testedSeasonsCount && (
            <div
              className="rounded-xl border p-6"
              style={{ background: "var(--surface)", borderColor: "var(--border)" }}
            >
              <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-6">
                <div>
                  <h3 className="font-display font-bold text-base md:text-lg">
                    LİDAŞ Depolama Stratejisi Backtest Simülatörü
                  </h3>
                  <p className="text-xs" style={{ color: "var(--text-muted)" }}>
                    Hasat dönemi spot satış vs. 3, 6 ve 9 ay LİDAŞ'ta saklama. Alternatif faiz: %
                    {dataset.storageBacktest.annualInterestPct}
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-xs px-3 py-1 rounded-full bg-zinc-800 text-zinc-300 font-mono">
                    En İyi Strateji:{" "}
                    <strong className="text-amber-400">{dataset.storageBacktest.bestStrategy}</strong>
                  </span>
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
                <div className="p-4 rounded-xl bg-zinc-900/60 border border-zinc-800">
                  <span className="text-xs text-zinc-400 uppercase tracking-wider block">
                    3 Ay Saklama Başarısı
                  </span>
                  <p className="text-2xl font-bold font-display mt-1 text-zinc-200">
                    %{dataset.storageBacktest.winRate3mPct?.toFixed(1)}
                  </p>
                  <p className="text-xs text-zinc-400 mt-1">Hasat spot satışını geçme oranı</p>
                </div>

                <div className="p-4 rounded-xl bg-zinc-900/60 border border-zinc-800">
                  <span className="text-xs text-zinc-400 uppercase tracking-wider block">
                    6 Ay Saklama Başarısı
                  </span>
                  <p className="text-2xl font-bold font-display mt-1 text-zinc-200">
                    %{dataset.storageBacktest.winRate6mPct?.toFixed(1)}
                  </p>
                  <p className="text-xs text-zinc-400 mt-1">
                    Ort. Net Getiri: {dataset.storageBacktest.avgNetReturn6mPct?.toFixed(1)}%
                  </p>
                </div>

                <div className="p-4 rounded-xl bg-zinc-900/60 border border-zinc-800">
                  <span className="text-xs text-zinc-400 uppercase tracking-wider block">
                    9 Ay Saklama Başarısı
                  </span>
                  <p className="text-2xl font-bold font-display mt-1 text-zinc-200">
                    %{dataset.storageBacktest.winRate9mPct?.toFixed(1)}
                  </p>
                  <p className="text-xs text-zinc-400 mt-1">Yüksek faiz taşıma maliyeti baskısı</p>
                </div>
              </div>

              {dataset.storageBacktest.strategicAdvice && (
                <p className="text-xs md:text-sm leading-relaxed p-4 rounded-xl bg-amber-500/5 border border-amber-500/20 text-zinc-300">
                  <strong className="text-amber-400">Stratejik Sonuç: </strong>
                  {dataset.storageBacktest.strategicAdvice}
                </p>
              )}
            </div>
          )}
        </section>
      )}

      {/* ── Section: Bölgesel LİDAŞ Arbitrajı ── */}
      {(activeTab === "all" || activeTab === "arbitrage") && (
        <section className="space-y-6">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div>
              <div className="flex items-center gap-2">
                <Truck className="w-5 h-5 text-sky-400" />
                <h2 className="text-xl md:text-2xl font-display font-bold">
                  Bölgesel Lisanslı Depo Arbitraj Radarı
                </h2>
              </div>
              <p className="text-xs md:text-sm" style={{ color: "var(--text-secondary)" }}>
                Üretim havzası depoları ile tüketim merkezi LİDAŞ'lar arasındaki nakliye maliyeti düşülmüş net arbitraj spread'leri.
              </p>
            </div>
          </div>

          <div className="rounded-xl border overflow-hidden" style={{ background: "var(--surface)", borderColor: "var(--border)" }}>
            <div className="p-4 md:p-6 border-b" style={{ borderColor: "var(--border)" }}>
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                <h3 className="font-display font-bold text-base md:text-lg">
                  En Yüksek Net Arbitraj Fırsatları
                </h3>
                <span className="text-xs text-zinc-400 font-mono">
                  Referans Nakliye: 0,50 ₺/kg
                </span>
              </div>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs md:text-sm">
                <thead>
                  <tr className="border-b text-xs uppercase tracking-wider" style={{ borderColor: "var(--border)", color: "var(--text-muted)" }}>
                    <th className="py-3 px-4 md:px-6">Emtia</th>
                    <th className="py-3 px-4">Kaynak (Ucuz) İl & Depo</th>
                    <th className="py-3 px-4">Hedef (Pahalı) İl & Depo</th>
                    <th className="py-3 px-4">Brüt Makas</th>
                    <th className="py-3 px-4">Tahmini Nakliye</th>
                    <th className="py-3 px-4">Net Arbitraj</th>
                    <th className="py-3 px-4 md:px-6 text-right">Fırsat Seviyesi</th>
                  </tr>
                </thead>
                <tbody className="divide-y" style={{ borderColor: "var(--border)" }}>
                  {filteredArb.length > 0 ? (
                    filteredArb.map((op, i) => (
                      <tr key={i} className="hover:bg-zinc-900/50 transition-colors">
                        <td className="py-3.5 px-4 md:px-6 font-semibold" style={{ color: "var(--text-primary)" }}>
                          {op.commodity}
                        </td>
                        <td className="py-3.5 px-4">
                          <span className="font-semibold block text-zinc-200">{op.cheapCity}</span>
                          <span className="text-xs text-zinc-400">{op.cheapPrice.toFixed(2)} ₺/kg ({op.cheapLidas})</span>
                        </td>
                        <td className="py-3.5 px-4">
                          <span className="font-semibold block text-zinc-200">{op.expensiveCity}</span>
                          <span className="text-xs text-zinc-400">{op.expensivePrice.toFixed(2)} ₺/kg ({op.expensiveLidas})</span>
                        </td>
                        <td className="py-3.5 px-4 font-mono">{op.grossSpread.toFixed(2)} ₺</td>
                        <td className="py-3.5 px-4 font-mono text-zinc-400">-{op.freightCost.toFixed(2)} ₺</td>
                        <td className="py-3.5 px-4 font-mono font-bold text-emerald-400">
                          +{op.netArbitrage.toFixed(2)} ₺/kg (%{op.netArbitragePct.toFixed(1)})
                        </td>
                        <td className="py-3.5 px-4 md:px-6 text-right">
                          <span className="px-2.5 py-0.5 rounded text-xs font-semibold bg-emerald-500/10 border border-emerald-500/30 text-emerald-400">
                            {op.opportunityLevel}
                          </span>
                        </td>
                      </tr>
                    ))
                  ) : (
                    <tr>
                      <td colSpan={7} className="py-8 text-center text-zinc-400">
                        Arbitraj kaydı bulunamadı.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </section>
      )}

      {/* ── Section: Agri-BIST Hisseleri & Korelasyon ── */}
      {(activeTab === "all" || activeTab === "agriBist") && (
        <section className="space-y-6">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div>
              <div className="flex items-center gap-2">
                <Scale className="w-5 h-5 text-indigo-400" />
                <h2 className="text-xl md:text-2xl font-display font-bold">
                  Agri-BIST Çapraz Piyasa & Gıda Hisseleri Radarı
                </h2>
              </div>
              <p className="text-xs md:text-sm" style={{ color: "var(--text-secondary)" }}>
                TÜRİB tarımsal emtia fiyatları ile BIST gıda ve yem şirketlerinin operasyonel marj duyarlılığı.
              </p>
            </div>

            <div className="text-xs px-3 py-1.5 rounded-lg bg-zinc-900 border border-zinc-800 flex items-center gap-2">
              <span className="text-zinc-400">XGIDA Endeksi:</span>
              <strong className="text-zinc-200">{dataset.agriBist.xgidaPrice || "11.240,50"}</strong>
              <span className="text-emerald-400 font-semibold">{dataset.agriBist.xgidaChange || "+2,59%"}</span>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {(dataset.agriBist.companies || []).map((c) => {
              const isUp = !c.stockChange.startsWith("-");
              return (
                <div
                  key={c.ticker}
                  className="rounded-xl border p-5 flex flex-col justify-between"
                  style={{ background: "var(--surface)", borderColor: "var(--border)" }}
                >
                  <div>
                    <div className="flex items-center justify-between mb-3">
                      <div className="flex items-center gap-2">
                        <span className="px-2.5 py-1 rounded text-xs font-mono font-bold bg-zinc-800 text-zinc-100">
                          {c.ticker}
                        </span>
                        <span className="text-xs font-semibold text-zinc-300">{c.companyName}</span>
                      </div>
                      <span className={`text-xs font-semibold font-mono ${isUp ? "text-emerald-400" : "text-red-400"}`}>
                        {c.stockChange}
                      </span>
                    </div>

                    <div className="p-3 rounded-lg bg-zinc-900/60 border border-zinc-800 text-xs mb-3 space-y-1.5">
                      <div className="flex justify-between">
                        <span className="text-zinc-400">Hisse Fiyatı:</span>
                        <span className="font-semibold text-zinc-200">{c.stockPrice} ₺</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-zinc-400">Girdi Emtia:</span>
                        <span className="font-semibold text-amber-400">{c.commodity}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-zinc-400">Emtia Değişim:</span>
                        <span className="font-semibold text-zinc-300">{c.commodityChange}</span>
                      </div>
                      <div className="flex justify-between pt-1 border-t border-zinc-800">
                        <span className="text-zinc-400">Marj Baskısı:</span>
                        <span className="font-semibold text-zinc-200">{c.marginPressure}</span>
                      </div>
                    </div>

                    <p className="text-xs leading-relaxed" style={{ color: "var(--text-secondary)" }}>
                      {c.commentary}
                    </p>
                  </div>
                </div>
              );
            })}
          </div>
        </section>
      )}

      {/* ── Section: Açık Veri, API & MCP Geliştirici Terminali ── */}
      {(activeTab === "all" || activeTab === "api") && (
        <section className="space-y-6">
          <div className="flex items-center gap-2">
            <Terminal className="w-5 h-5 text-amber-400" />
            <h2 className="text-xl md:text-2xl font-display font-bold">
              Geliştiriciler & Analistler İçin Açık Veri & MCP Entegrasyonu
            </h2>
          </div>
          <p className="text-xs md:text-sm" style={{ color: "var(--text-secondary)" }}>
            Bu veri setini kendi finansal modellerinizde, botlarınızda veya Cursor / Claude Desktop üzerinde doğrudan MCP protokolüyle kullanabilirsiniz.
          </p>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* JSON API Endpoint */}
            <div
              className="rounded-xl border p-6 flex flex-col justify-between"
              style={{ background: "var(--surface)", borderColor: "var(--border)" }}
            >
              <div>
                <div className="flex items-center justify-between mb-3">
                  <h3 className="font-bold text-sm md:text-base text-zinc-100 flex items-center gap-2">
                    <Database className="w-4 h-4 text-emerald-400" />
                    Statik JSON Veri Erişimi
                  </h3>
                  <button
                    onClick={handleCopyUrl}
                    className="p-1.5 rounded hover:bg-zinc-800 text-zinc-400 hover:text-zinc-200 transition-colors cursor-pointer"
                    title="URL'i Kopyala"
                  >
                    {copiedUrl ? <Check className="w-4 h-4 text-emerald-400" /> : <Copy className="w-4 h-4" />}
                  </button>
                </div>
                <p className="text-xs text-zinc-400 mb-4">
                  Her gün piyasa taramasıyla otomatik güncellenen tam veri setine CORS engeli olmadan doğrudan GET isteği atabilirsiniz.
                </p>

                <div className="rounded-lg bg-zinc-950 p-4 font-mono text-xs text-zinc-300 border border-zinc-800 overflow-x-auto space-y-2">
                  <p className="text-zinc-400"># cURL ile indirme:</p>
                  <p className="text-amber-400">curl -s https://esham.pages.dev/data/turib-market.json</p>
                  <p className="text-zinc-400 pt-2"># Python ile okuma:</p>
                  <p className="text-zinc-400">
                    import requests<br />
                    data = requests.get(&quot;https://esham.pages.dev/data/turib-market.json&quot;).json()<br />
                    print(data[&quot;meatFeed&quot;][&quot;parities&quot;][0][&quot;ratio&quot;])
                  </p>
                </div>
              </div>

              <div className="mt-6 flex items-center gap-3">
                <a
                  href="/data/turib-market.json"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1.5 text-xs text-amber-400 hover:underline font-semibold"
                >
                  Tarayıcıda JSON&apos;ı Aç <ExternalLink className="w-3.5 h-3.5" />
                </a>
              </div>
            </div>

            {/* MCP Entegrasyonu */}
            <div
              className="rounded-xl border p-6 flex flex-col justify-between"
              style={{ background: "var(--surface)", borderColor: "var(--border)" }}
            >
              <div>
                <div className="flex items-center justify-between mb-3">
                  <h3 className="font-bold text-sm md:text-base text-zinc-100 flex items-center gap-2">
                    <Terminal className="w-4 h-4 text-amber-400" />
                    Claude Desktop & Cursor MCP Server
                  </h3>
                  <button
                    onClick={handleCopyMcp}
                    className="p-1.5 rounded hover:bg-zinc-800 text-zinc-400 hover:text-zinc-200 transition-colors cursor-pointer"
                    title="MCP Ayarını Kopyala"
                  >
                    {copiedMcp ? <Check className="w-4 h-4 text-emerald-400" /> : <Copy className="w-4 h-4" />}
                  </button>
                </div>
                <p className="text-xs text-zinc-400 mb-4">
                  `esham-market-mcp` ile 18 adet canlı aracı (TÜRİB, BIST, Et-Yem, TMO, Depolama) yapay zeka asistanınıza ekleyin.
                </p>

                <div className="rounded-lg bg-zinc-950 p-4 font-mono text-xs text-zinc-300 border border-zinc-800 overflow-x-auto">
                  <pre>{mcpConfigCode}</pre>
                </div>
              </div>

              <div className="mt-6 flex items-center gap-3">
                <button
                  onClick={handleCopyMcp}
                  className="inline-flex items-center gap-1.5 text-xs text-amber-400 hover:underline font-semibold cursor-pointer"
                >
                  {copiedMcp ? "Yapılandırma Kopyalandı!" : "MCP JSON Yapılandırmasını Kopyala"}
                </button>
              </div>
            </div>
          </div>
        </section>
      )}

      {/* ── SPK ve TÜRİB Yasal Çekince ── */}
      <div
        className="rounded-xl border p-5 text-xs leading-relaxed"
        style={{
          background: "var(--surface)",
          borderColor: "var(--border)",
          color: "var(--text-muted)",
        }}
      >
        <div className="flex items-start gap-3">
          <ShieldCheck className="w-5 h-5 text-zinc-400 shrink-0 mt-0.5" />
          <p>
            <strong>Yasal Uyarı (SPK & TÜRİB Çekincesi):</strong> Bu sayfada yer alan TÜRİB endeksleri,
            lisanslı depoculuk işlem verileri, et-yem pariteleri, TÜİK enflasyon hesaplamaları ve BIST hisse
            yansımaları yalnızca bilgi, araştırma ve veri analitiği amaçlıdır. Sermaye Piyasası Kurulu (SPK)
            mevzuatı kapsamında yatırım danışmanlığı veya alım-satım tavsiyesi niteliği taşımaz. Yatırım kararlarınızı
            yetkili aracı kurumlar ve portföy yönetim şirketleri aracılığıyla kendi risk profilinize göre vermeniz önerilir.
          </p>
        </div>
      </div>
    </div>
  );
}
