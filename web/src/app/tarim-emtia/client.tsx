"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import {
  Wheat,
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
  tmoComparison: Array<{
    commodity: string;
    tmoProductName: string;
    year: number;
    asOf?: string;
    stale?: boolean;
    tmoSeason?: string;
    tmoSource?: string | null;
    tmoAsOf?: string | null;
    tmoVerified?: boolean;
    tmoPurchasePrice: number | null;
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
    asOf?: string;
    stale?: boolean;
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
    asOf?: string;
    stale?: boolean;
    tradingDays: number;
    startPriceTl: number;
    endPriceTl: number;
    nominalReturnPct: number;
    usdReturnPct: number;
    eurReturnPct: number;
    fxDateStart?: string;
    fxDateEnd?: string;
    usdTryStart?: number;
    usdTryEnd?: number;
    eurTryStart?: number;
    eurTryEnd?: number;
    source?: string;
    sourceUrl?: string;
    fetchedAt?: string;
    commentary: string;
  }>;
  /** Bot'un her bölüm için yazdığı kaynak / veri tarihi / durum damgası (bkz. bot/esham/freshness.py). */
  sections?: Record<string, SectionMeta>;
  petrolTanker?: PetrolTankerDataset;
}

export interface SectionMeta {
  label: string;
  source: string;
  sourceUrl: string;
  asOf: string | null;
  fetchedAt: string | null;
  stale: boolean;
  status: "fresh" | "stale" | "missing";
}

const NO_DATA = "Veri yok";
const isNum = (v: unknown): v is number => typeof v === "number" && Number.isFinite(v);
const isPos = (v: unknown): v is number => isNum(v) && v > 0;
const NoSource = ({ what }: { what: string }) => (
  <p className="text-xs md:text-sm rounded-xl border p-4" style={{ borderColor: "var(--border)", color: "var(--text-muted)" }}>
    {what}: veri kaynağı şu an yok. Eski veya örnek değer gösterilmez.
  </p>
);
const StaleNote = ({ asOf }: { asOf?: string }) => (
  <p className="text-xs" style={{ color: "var(--text-muted)" }}>
    Son geçerli veri{asOf ? ` (${asOf})` : ""}; güncel değil.
  </p>
);

const STATUS_LABEL: Record<SectionMeta["status"], string> = { fresh: "güncel", stale: "güncel değil", missing: "veri yok" };

/** Her bölümün kaynağı, veri tarihi ve çekiliş zamanı: eski/eksik veri sessiz kalmaz. */
function SectionStamps({ sections }: { sections?: Record<string, SectionMeta> }) {
  const rows = Object.entries(sections ?? {});
  if (rows.length === 0) return null;
  return (
    <details className="rounded-xl border p-4 text-xs" style={{ borderColor: "var(--border)", color: "var(--text-secondary)" }}>
      <summary className="cursor-pointer font-semibold">Bölüm bazında veri tarihleri ve kaynaklar</summary>
      <div className="overflow-x-auto mt-3">
        <table className="w-full text-left">
          <thead>
            <tr style={{ color: "var(--text-muted)" }}>
              <th className="py-1 pr-4">Bölüm</th>
              <th className="py-1 pr-4">Veri tarihi</th>
              <th className="py-1 pr-4">Durum</th>
              <th className="py-1 pr-4">Kaynak</th>
              <th className="py-1">Çekiliş</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(([key, m]) => (
              <tr key={key}>
                <td className="py-1 pr-4">{m.label}</td>
                <td className="py-1 pr-4">{m.asOf ?? "—"}</td>
                <td className="py-1 pr-4">{STATUS_LABEL[m.status] ?? m.status}</td>
                <td className="py-1 pr-4">
                  <a href={m.sourceUrl} target="_blank" rel="noopener noreferrer" className="underline">
                    {m.source}
                  </a>
                </td>
                <td className="py-1">
                  {m.fetchedAt ? new Date(m.fetchedAt).toLocaleString("tr-TR", { timeZone: "Europe/Istanbul" }) : "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </details>
  );
}

export function TuribMarketClient({
  dataset,
  initialTab,
}: {
  dataset: TuribMarketDataset;
  initialTab?: string;
}) {
  const [activeTab, setActiveTab] = useState<
    "all" | "petrolTanker" | "indices" | "tmoStorage" | "arbitrage" | "agriBist" | "api"
  >((initialTab as any) || "all");

  useEffect(() => {
    if (typeof window !== "undefined") {
      const params = new URLSearchParams(window.location.search);
      const tabParam = params.get("tab");
      if (
        tabParam &&
        ["all", "petrolTanker", "indices", "tmoStorage", "arbitrage", "agriBist", "api"].includes(
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
      "cwd": "<proje-klasörü>/bot"
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

  const filteredSpot = (dataset.spotCommodities || []).filter((p) =>
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
                TÜRİB & ELÜS VERİ SETİ
              </span>
              <span className="text-xs" style={{ color: "var(--text-muted)" }}>
                Son Güncelleme:{" "}
                {dataset.updatedAt
                  ? new Date(dataset.updatedAt).toLocaleString("tr-TR", { timeZone: "Europe/Istanbul" })
                  : NO_DATA}
              </span>
            </div>
            <h1 className="text-2xl md:text-4xl font-display font-bold tracking-tight mb-2">
              Tarımsal Emtia & TÜRİB Terminali
            </h1>
            <p className="text-sm md:text-base max-w-2xl leading-relaxed" style={{ color: "var(--text-secondary)" }}>
              Türkiye Ürün İhtisas Borsası (TÜRİB) lisanslı depo işlem fiyatları, TMO alım fiyatları,
              Brent petrol ve BIST tarım-gıda entegrasyonu. Her bölümün kaynağı ve veri tarihi aşağıda yazılıdır.
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
        <div className="grid grid-cols-2 gap-4 mt-8 pt-6 border-t" style={{ borderColor: "var(--border)" }}>
          <div>
            <p className="text-xs uppercase tracking-wider font-semibold" style={{ color: "var(--text-muted)" }}>
              Toplam Günlük Hacim
            </p>
            <p className="text-lg md:text-xl font-bold mt-1" style={{ color: "var(--text-primary)" }}>
              {dataset.bulletinSummary?.totalVolumeTonStr || NO_DATA}
            </p>
          </div>
          <div>
            <p className="text-xs uppercase tracking-wider font-semibold" style={{ color: "var(--text-muted)" }}>
              İşlem Tutarı
            </p>
            <p className="text-lg md:text-xl font-bold mt-1" style={{ color: "var(--accent)" }}>
              {dataset.bulletinSummary?.totalValueTlStr || NO_DATA}
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

      {/* ── Bölüm veri damgaları: kaynak · veri tarihi · çekiliş · durum ── */}
      <SectionStamps sections={dataset.sections} />

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

          {(dataset.indices || []).length === 0 && (dataset.spotCommodities || []).length === 0 ? (
            <NoSource what="TÜRİB endeks ve spot bülteni" />
          ) : (
          <>
          {dataset.date && (
            <p className="text-xs" style={{ color: "var(--text-muted)" }}>
              Veri tarihi: {dataset.date}
            </p>
          )}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {(dataset.indices || []).map((idx) => {
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
                      {idx.low > 0 ? `${idx.low.toFixed(1)} - ${idx.high.toFixed(1)}` : "—"}
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
          </>
          )}
        </section>
      )}

      {/* ── Section: Döviz cinsinden getiri (TCMB kurları) ── */}
      {(activeTab === "all" || activeTab === "indices") && (dataset.realReturns || []).length > 0 && (
        <section className="space-y-4">
          <h2 className="text-xl md:text-2xl font-display font-bold">Buğday Fiyatı: TL, USD ve EUR Bazında Değişim</h2>
          <p className="text-xs md:text-sm" style={{ color: "var(--text-secondary)" }}>
            TÜRİB fiyat serisinin son 12 aylık değişimi; dolar ve euro karşılığı TCMB döviz alış kuruyla hesaplanır.
            TÜFE ile arındırılmış getiri bu sayfada yoktur.
          </p>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {dataset.realReturns.map((r) => (
              <div key={r.commodityGroup} className="rounded-xl border p-4 space-y-2" style={{ background: "var(--surface)", borderColor: "var(--border)" }}>
                <h3 className="font-semibold">{r.commodityGroup}</h3>
                <p className="text-xs" style={{ color: "var(--text-muted)" }}>
                  {r.startDate} → {r.endDate}
                  {r.stale ? " (güncel değil, son iyi değer)" : ""}
                </p>
                <dl className="grid grid-cols-3 gap-2 text-sm">
                  <div>
                    <dt className="text-xs" style={{ color: "var(--text-muted)" }}>TL</dt>
                    <dd className="font-bold">{isNum(r.nominalReturnPct) ? `%${r.nominalReturnPct.toFixed(1)}` : NO_DATA}</dd>
                  </div>
                  <div>
                    <dt className="text-xs" style={{ color: "var(--text-muted)" }}>USD</dt>
                    <dd className="font-bold">{isNum(r.usdReturnPct) ? `%${r.usdReturnPct.toFixed(1)}` : NO_DATA}</dd>
                  </div>
                  <div>
                    <dt className="text-xs" style={{ color: "var(--text-muted)" }}>EUR</dt>
                    <dd className="font-bold">{isNum(r.eurReturnPct) ? `%${r.eurReturnPct.toFixed(1)}` : NO_DATA}</dd>
                  </div>
                </dl>
                <p className="text-xs" style={{ color: "var(--text-muted)" }}>
                  Veri tarihi: {r.asOf ?? r.endDate}
                  {r.fxDateEnd ? ` · kur bülteni: ${r.fxDateStart} ve ${r.fxDateEnd}` : ""}
                  {" · Kaynak: "}
                  {r.sourceUrl ? (
                    <a href={r.sourceUrl} target="_blank" rel="noopener noreferrer" className="underline">
                      {r.source ?? "TCMB"}
                    </a>
                  ) : (
                    (r.source ?? "TCMB")
                  )}
                  {r.fetchedAt ? ` · çekiliş: ${new Date(r.fetchedAt).toLocaleString("tr-TR", { timeZone: "Europe/Istanbul" })}` : ""}
                </p>
              </div>
            ))}
          </div>
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
          {(dataset.tmoComparison || []).length === 0 ? (
            <NoSource what="TMO alım fiyatı karşılaştırması" />
          ) : (
          <div className="rounded-xl border overflow-hidden" style={{ background: "var(--surface)", borderColor: "var(--border)" }}>
            <div className="p-4 md:p-6 border-b" style={{ borderColor: "var(--border)" }}>
              <h3 className="font-display font-bold text-base md:text-lg">
                TMO Taban Alım Fiyatı vs. Serbest Piyasa ELÜS Kıyaslaması
              </h3>
              <p className="text-xs" style={{ color: "var(--text-muted)" }}>
                Üreticinin TMO yerine serbest piyasayı tercih etme prim oranları (TL/kg ve %).
              </p>
              <p className="text-xs mt-1" style={{ color: "var(--text-muted)" }}>
                TMO sütunları, sezonu satırda belirtilen açıklanan alım fiyatlarıdır (güncel piyasa fiyatı değildir).
                {(dataset.tmoComparison || []).some((t) => t.tmoVerified !== true) &&
                  " Resmî duyurusu doğrulanamayan satırlarda TMO değeri gösterilmez."}
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
                    const hasFree = isPos(tmo.turibFreePrice) && isNum(tmo.spreadTl) && isNum(tmo.spreadPct);
                    const isPremium = hasFree && tmo.spreadTl >= 0;
                    return (
                      <tr key={tmo.commodity} className="hover:bg-zinc-900/50 transition-colors">
                        <td className="py-3.5 px-4 md:px-6 font-semibold" style={{ color: "var(--text-primary)" }}>
                          {tmo.commodity}
                          <span className="block text-xs font-normal" style={{ color: "var(--text-muted)" }}>
                            TMO açıklanan alım fiyatı, {tmo.tmoSeason || tmo.year} sezonu
                            {tmo.tmoVerified === true && tmo.tmoSource ? (
                              <>
                                {" · "}
                                <a href={tmo.tmoSource} target="_blank" rel="noopener noreferrer" className="underline">
                                  resmî duyuru{tmo.tmoAsOf ? `, ${tmo.tmoAsOf}` : ""}
                                </a>
                              </>
                            ) : (
                              " · doğrulanamadı"
                            )}
                          </span>
                        </td>
                        <td className="py-3.5 px-4 font-mono">{isNum(tmo.tmoPurchasePrice) ? `${tmo.tmoPurchasePrice.toFixed(2)} ₺` : "doğrulanamadı"}</td>
                        <td className="py-3.5 px-4 font-mono text-emerald-400">{isNum(tmo.farmerPremium) ? `+${tmo.farmerPremium.toFixed(2)} ₺` : NO_DATA}</td>
                        <td className="py-3.5 px-4 font-mono font-semibold">{isNum(tmo.totalFarmerIncome) ? `${tmo.totalFarmerIncome.toFixed(2)} ₺` : NO_DATA}</td>
                        <td className="py-3.5 px-4 font-mono font-bold" style={{ color: "var(--accent)" }}>
                          {isPos(tmo.turibFreePrice) ? `${tmo.turibFreePrice.toFixed(2)} ₺` : NO_DATA}
                          {tmo.asOf && (
                            <span className="block text-xs font-normal" style={{ color: "var(--text-muted)" }}>
                              {tmo.stale ? "Son geçerli: " : ""}
                              {tmo.asOf}
                            </span>
                          )}
                        </td>
                        <td className="py-3.5 px-4">
                          {hasFree ? (
                            <span className={`font-semibold ${isPremium ? "text-emerald-400" : "text-red-400"}`}>
                              {isPremium ? "+" : ""}
                              {tmo.spreadTl.toFixed(2)} ₺ (%{tmo.spreadPct.toFixed(1)})
                            </span>
                          ) : (
                            NO_DATA
                          )}
                        </td>
                        <td className="py-3.5 px-4 md:px-6 text-right">
                          <span
                            className={`px-2 py-0.5 rounded text-xs font-semibold border ${
                              isPremium
                                ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-400"
                                : "bg-red-500/10 border-red-500/30 text-red-400"
                            }`}
                          >
                            {hasFree ? tmo.status.replace(/_/g, " ") : NO_DATA}
                          </span>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
          )}

          {/* LİDAŞ Depolama Backtest Simülasyonu */}
          {dataset.storageBacktest?.stale && <StaleNote asOf={dataset.storageBacktest.asOf} />}
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
                    Hasat dönemi spot satış vs. 3, 6 ve 9 ay LİDAŞ'ta saklama. Alternatif faiz (model varsayımı): %
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

          {(dataset.regionalArbitrage?.opportunities || []).length === 0 ? (
            <NoSource what="Bölgesel arbitraj taraması" />
          ) : (
          <div className="rounded-xl border overflow-hidden" style={{ background: "var(--surface)", borderColor: "var(--border)" }}>
            <div className="p-4 md:p-6 border-b" style={{ borderColor: "var(--border)" }}>
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                <h3 className="font-display font-bold text-base md:text-lg">
                  En Yüksek Net Arbitraj Fırsatları
                </h3>
                <span className="text-xs text-zinc-400 font-mono">
                  {dataset.regionalArbitrage.date ? `Veri tarihi: ${dataset.regionalArbitrage.date} · ` : ""}
                  Nakliye (model varsayımı):{" "}
                  {isNum(filteredArb[0]?.freightCost) ? `${filteredArb[0].freightCost.toFixed(2).replace(".", ",")} ₺/kg` : NO_DATA}
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
          )}
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
              <strong className="text-zinc-200">{dataset.agriBist?.xgidaPrice || NO_DATA}</strong>
              {dataset.agriBist?.xgidaChange && (
                <span className="text-emerald-400 font-semibold">{dataset.agriBist.xgidaChange}</span>
              )}
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {(dataset.agriBist?.companies || []).length === 0 && <NoSource what="Agri-BIST hisse radarı" />}
            {(dataset.agriBist?.companies || []).filter((c) => Number(c.commodityPrice) > 0).map((c) => {
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
                    print(data[&quot;sections&quot;][&quot;indices&quot;][&quot;asOf&quot;])
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
                  `esham-market-mcp` ile 18 adet aracı (TÜRİB, BIST, TMO, Depolama) yapay zeka asistanınıza ekleyin.
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
            lisanslı depoculuk işlem verileri, TCMB kurlarıyla yapılan hesaplamalar ve BIST hisse
            yansımaları yalnızca bilgi, araştırma ve veri analitiği amaçlıdır. Sermaye Piyasası Kurulu (SPK)
            mevzuatı kapsamında yatırım danışmanlığı veya alım-satım tavsiyesi niteliği taşımaz. Yatırım kararlarınızı
            yetkili aracı kurumlar ve portföy yönetim şirketleri aracılığıyla kendi risk profilinize göre vermeniz önerilir.
          </p>
        </div>
      </div>
    </div>
  );
}
