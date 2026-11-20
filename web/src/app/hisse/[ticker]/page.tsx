import { DEFAULT_OG_IMAGE } from "@/lib/seo";
import Link from "next/link";
import { notFound } from "next/navigation";
import type { Metadata } from "next";
import { promises as fs } from "fs";
import path from "path";
import {
  ArrowLeft,
  TrendingUp,
  TrendingDown,
  Building2,
  FileText,
  Activity,
  Layers,
  ArrowUpRight,
  ShieldAlert,
} from "lucide-react";
import {
  getAllReports,
  getReportsByTicker,
  getAllTickers,
  formatDate,
  type Report,
} from "@/lib/content";
import { ReportCard } from "@/components/ReportCard";
import { DcfTerminalCard } from "@/components/DcfTerminalCard";
import { KeyLevelsCard } from "@/components/KeyLevelsCard";
import { FundamentalMetricsCard } from "@/components/FundamentalMetricsCard";
import { FinancialHealthCard } from "@/components/FinancialHealthCard";
import { WatchlistDrawer } from "@/components/WatchlistDrawer";
import { PriceChart } from "@/components/PriceChart";
import { DcfCalculator } from "@/components/DcfCalculator";
import { NavCalculator } from "@/components/NavCalculator";
import { SectorComparison } from "@/components/SectorComparison";
import { FinancialStatements } from "@/components/FinancialStatements";
import { Newsletter } from "@/components/Newsletter";
import { StockTabs, type TabDef } from "@/components/StockTabs";
import { StockCorporateActionsCard } from "@/components/StockCorporateActionsCard";
import { StockPeerComparisonCard } from "@/components/StockPeerComparisonCard";
import { RatiosCard, type StockRatiosData } from "@/components/RatiosCard";
import { getStockName, loadUniverse } from "@/lib/stocks";
import { SectorPeersCard } from "@/components/SectorPeersCard";
import { RatioTrendCharts } from "@/components/RatioTrendCharts";

type Params = { ticker: string };

export async function generateStaticParams(): Promise<Params[]> {
  const tickers = getAllTickers();
  return tickers.map((ticker) => ({ ticker: ticker.toUpperCase() }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<Params>;
}): Promise<Metadata> {
  const { ticker } = await params;
  const clean = ticker.toUpperCase();
  const companyName = COMPANY_NAMES[clean] || getStockName(clean) || `${clean} Pay Piyasası`;

  return {
    title: `$${clean} Hisse Analizi, Hedef Fiyat & KAP Bildirimleri`,
    description: `Borsa İstanbul $${clean} (${companyName}) hissesine ait canlı teknik pivot seviyeleri, İNA (DCF) hedef fiyatı, KAP sözleşmeleri, temettü verimi ve bilanço çarpanları.`,
    keywords: [
      `$${clean}`,
      `${clean} hisse`,
      `${clean} hedef fiyat`,
      `${clean} analiz`,
      `${clean} kap`,
      `${clean} bilanço`,
      `${clean} temettü`,
      companyName,
      "BIST 100",
      "Borsa İstanbul",
    ],
    alternates: {
      canonical: `https://esham.pages.dev/hisse/${clean}`,
    },
    openGraph: {
      title: `$${clean} Hisse Analizi & Hedef Değerleme | Esham`,
      description: `$${clean} (${companyName}) teknik seviyeler, DCF değerlemesi, KAP geçmişi ve temettü takvimi.`,
      url: `https://esham.pages.dev/hisse/${clean}`,
      siteName: "Esham",
      locale: "tr_TR",
      type: "website",
      images: [DEFAULT_OG_IMAGE],
    },
    twitter: {
      card: "summary_large_image",
      title: `$${clean} Hisse Analizi & Hedef Fiyat | Esham`,
      description: `${companyName} hissesi için teknik pivotlar, DCF adil değer ve güncel KAP haberleri.`,
      creator: "@eshamcomtr",
      images: [DEFAULT_OG_IMAGE.url],
    },
  };
}

async function loadMarketTickerData() {
  try {
    const filePath = path.join(process.cwd(), "public", "data", "market-ticker.json");
    const raw = await fs.readFile(filePath, "utf-8");
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

async function loadQuantValuationData() {
  try {
    const filePath = path.join(process.cwd(), "public", "data", "bist-quant-valuation.json");
    const raw = await fs.readFile(filePath, "utf-8");
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

async function loadBuybacksData() {
  try {
    const filePath = path.join(process.cwd(), "public", "data", "bist-buybacks.json");
    const raw = await fs.readFile(filePath, "utf-8");
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

async function loadDividendsData() {
  try {
    const filePath = path.join(process.cwd(), "public", "data", "bist-dividends.json");
    const raw = await fs.readFile(filePath, "utf-8");
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

async function loadNav(ticker: string): Promise<{ source: string; fetched_at: string; stakes: { title: string; pct: number; relation: string; ticker: string | null }[] } | null> {
  try {
    const raw = await fs.readFile(path.join(process.cwd(), "public", "data", "nav", `${ticker}.json`), "utf-8");
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

async function loadPrices(ticker: string): Promise<[string, number][] | null> {
  try {
    const raw = await fs.readFile(path.join(process.cwd(), "public", "data", "prices", `${ticker}.json`), "utf-8");
    const d = JSON.parse(raw);
    return Array.isArray(d) && d.length > 4 ? d : null;
  } catch {
    return null;
  }
}

async function loadStockRatios(ticker: string): Promise<StockRatiosData | null> {
  try {
    const filePath = path.join(process.cwd(), "public", "data", "stocks", `${ticker}.json`);
    return JSON.parse(await fs.readFile(filePath, "utf-8"));
  } catch {
    return null;
  }
}

// BIST Popüler Şirket Adları Sözlüğü
const COMPANY_NAMES: Record<string, string> = {
  THYAO: "Türk Hava Yolları A.O.",
  ASELS: "Aselsan Elektronik Sanayi",
  GARAN: "T. Garanti Bankası A.Ş.",
  EREGL: "Ereğli Demir ve Çelik Fabrikaları",
  KCHOL: "Koç Holding A.Ş.",
  TUPRS: "Tüpraş Türkiye Petrol Rafinerileri",
  BIMAS: "BİM Birleşik Mağazalar A.Ş.",
  AKBNK: "Akbank T.A.Ş.",
  ISCTR: "Türkiye İş Bankası C Grubu",
  SISE:  "Türkiye Şişe ve Cam Fabrikaları",
  SAHOL: "Hacı Ömer Sabancı Holding",
  YKBNK: "Yapı ve Kredi Bankası A.Ş.",
  PGSUS: "Pegasus Hava Taşımacılığı",
  FROTO: "Ford Otomotiv Sanayi A.Ş.",
  TOASO: "Tofaş Türk Otomobil Fabrikası",
  ENKAI: "Enka İnşaat ve Sanayi A.Ş.",
  PETKM: "Petkim Petrokimya Holding",
  KOZAL: "Koza Altın İşletmeleri A.Ş.",
  GUBRF: "Gübre Fabrikaları T.A.Ş.",
  TCELL: "Turkcell İletişim Hizmetleri",
  TTKOM: "Türk Telekomünikasyon A.Ş.",
  EKGYO: "Emlak Konut Gayrimenkul Yatırım",
  HEKTS: "Hektaş Ticaret T.A.Ş.",
  SASA:  "Sasa Polyester Sanayi A.Ş.",
  ULUUN: "Ulusoy Un Sanayi ve Ticaret",
  BANVT: "Banvit Bandırma Vitaminli Yem",
  TATGD: "Tat Gıda Sanayi A.Ş.",
};


/** Başlık imzası: fiyatın 52 haftalık kapanış aralığındaki yeri (metin karşılığı ekran okuyucuya verilir). */
function RangeBar({ lo, hi, cur }: { lo: number; hi: number; cur: number }) {
  const pos = hi > lo ? Math.max(0, Math.min(1, (cur - lo) / (hi - lo))) : 0.5;
  const pct = Math.round(pos * 100);
  return (
    <div className="mt-2">
      <div className="relative h-1.5 rounded-full bg-zinc-800" aria-hidden="true">
        <div className="absolute inset-y-0 left-0 rounded-full bg-zinc-600" style={{ width: `${pct}%` }} />
        <span
          className="absolute top-1/2 h-3.5 w-1 -translate-y-1/2 -translate-x-1/2 rounded-full"
          style={{ left: `${pct}%`, background: "var(--accent)" }}
        />
      </div>
      <p className="sr-only">Güncel fiyat 52 haftalık aralığın %{pct} noktasında.</p>
      <p className="mt-1 text-xs text-zinc-400" aria-hidden="true">Aralığın %{pct} noktasında</p>
    </div>
  );
}

export default async function TickerPage({
  params,
}: {
  params: Promise<Params>;
}) {
  const { ticker } = await params;
  const cleanTicker = ticker.toUpperCase();

  const reports = getReportsByTicker(cleanTicker);
  const universe = loadUniverse();
  const [tickerData, quantData, buybacksData, dividendsData, stockRatios] = await Promise.all([
    loadMarketTickerData(),
    loadQuantValuationData(),
    loadBuybacksData(),
    loadDividendsData(),
    loadStockRatios(cleanTicker),
  ]);
  const companyQuant = quantData ? quantData[cleanTicker] : null;
  const companyBuyback = buybacksData?.programs?.find((p: any) => p.ticker === cleanTicker) || null;
  const companyDividend = dividendsData?.records?.find((d: any) => d.ticker === cleanTicker) || null;
  const dcfData = companyQuant?.dcf;
  const keyLevelsData = companyQuant?.key_levels;
  const fundamentalData = companyQuant?.fundamental;
  const financialHealthData = companyQuant?.financial_health;

  const liveQuote = tickerData?.tickers?.find(
    (t: any) => t.label.toUpperCase() === cleanTicker
  );

  const companyName = COMPANY_NAMES[cleanTicker] || getStockName(cleanTicker) || `${cleanTicker} Pay Piyasası`;

  // Canlı bant metni "₺395.50" gibi gelir (işaret + nokta ondalık): sayıya çevir, Türkçe biçimle tek "₺" bas
  const livePrice: number | null = (() => {
    const raw = liveQuote?.value;
    if (!raw) return null;
    const t = String(raw).replace(/[₺\s]/g, "");
    const n = t.includes(",") ? parseFloat(t.replace(/\./g, "").replace(",", ".")) : parseFloat(t);
    return Number.isFinite(n) ? n : null;
  })();
  const prices = await loadPrices(cleanTicker);
  const navData = await loadNav(cleanTicker);
  const r = stockRatios?.ratios;
  const fmtX = (v: number | null | undefined) => (v === null || v === undefined ? "—" : `${v.toLocaleString("tr-TR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}x`);
  const fmtP = (v: number | null | undefined) => (v === null || v === undefined ? "—" : `%${v.toLocaleString("tr-TR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`);
  const fmtMcap = (v: number | null | undefined) => (!v ? "—" : v >= 1e9 ? `${(v / 1e9).toLocaleString("tr-TR", { maximumFractionDigits: 1 })} Mr ₺` : `${(v / 1e6).toLocaleString("tr-TR", { maximumFractionDigits: 0 })} Mn ₺`);
  const last52 = prices ? prices.slice(-52).map((p) => p[1]) : [];
  const headerPrice: number | null = stockRatios?.price ?? (prices ? prices[prices.length - 1][1] : null);
  const summary: { label: string; value: string; range?: { lo: number; hi: number; cur: number } }[] = stockRatios && r
    ? [
        { label: "Piyasa Değeri", value: fmtMcap(r.market_cap) },
        { label: "F/K", value: fmtX(r.pe) },
        { label: "PD/DD", value: fmtX(r.pb) },
        { label: "FD/FAVÖK", value: stockRatios.financial ? "—" : fmtX(r.ev_ebitda) },
        { label: "Temettü Verimi", value: fmtP(r.dividend_yield) },
        {
          label: "52 Hafta (kapanış)",
          value: last52.length ? `${Math.min(...last52).toLocaleString("tr-TR", { maximumFractionDigits: 2 })} – ${Math.max(...last52).toLocaleString("tr-TR", { maximumFractionDigits: 2 })} ₺` : "—",
          range: last52.length && headerPrice !== null ? { lo: Math.min(...last52), hi: Math.max(...last52), cur: headerPrice } : undefined,
        },
      ]
    : [{ label: "Kapsamdaki Rapor", value: `${reports.length} Analiz & Bildirim` }];

  const stockRow = universe?.stocks.find((s) => s.ticker === cleanTicker) ?? null;
  const peersNode =
    stockRatios && universe ? (
      <SectorPeersCard ticker={cleanTicker} sector={stockRatios.sector} stocks={universe.stocks} median={universe.sector_median[stockRatios.sector]} />
    ) : companyQuant?.fundamental?.sektor && quantData ? (
      <StockPeerComparisonCard currentTicker={cleanTicker} currentSector={companyQuant.fundamental.sektor} quantData={quantData} />
    ) : null;

  const navStakes =
    navData && universe
      ? navData.stakes.map((st) => ({
          title: st.title,
          pct: st.pct,
          relation: st.relation,
          ticker: st.ticker,
          mcap: (st.ticker && universe.stocks.find((u) => u.ticker === st.ticker)?.market_cap) || null,
        }))
      : [];
  const navHoldingMcap = stockRow?.market_cap ?? null;

  const tabs: TabDef[] = [
    {
      id: "ozet",
      label: "Özet",
      content: (
        <>
          <PriceChart ticker={cleanTicker} />
          <StockCorporateActionsCard ticker={cleanTicker} buyback={companyBuyback} dividend={companyDividend} />
        </>
      ),
    },
    ...(stockRatios && stockRatios.annual?.length
      ? [
          {
            id: "finansallar",
            label: "Finansallar",
            content: (
              <FinancialStatements annual={stockRatios.annual} quarterly={stockRatios.quarterly ?? []} currency={stockRatios.currency} asOf={stockRatios.as_of} />
            ),
          },
        ]
      : []),
    ...(stockRatios || fundamentalData
      ? [
          {
            id: "oranlar",
            label: "Oranlar",
            content: (
              <>
                {stockRatios ? <RatiosCard data={stockRatios} /> : fundamentalData && <FundamentalMetricsCard data={fundamentalData} />}
                {stockRatios?.quarterly_history && <RatioTrendCharts data={stockRatios.quarterly_history} sector={stockRatios.sector} />}
              </>
            ),
          },
        ]
      : []),
    ...(peersNode || stockRow
      ? [
          {
            id: "sektor",
            label: "Sektör",
            content: (
              <>
                {stockRow && universe && <SectorComparison stock={stockRow} universe={universe.stocks} />}
                {peersNode}
              </>
            ),
          },
        ]
      : []),
    ...(stockRatios || dcfData || financialHealthData
      ? [
          {
            id: "degerleme",
            label: "Değerleme",
            content: (
              <>
                {stockRatios && !stockRatios.financial ? (
                  <DcfCalculator
                    ticker={cleanTicker}
                    currency={stockRatios.currency}
                    fxToTry={stockRatios.fx_to_try ?? null}
                    price={stockRatios.price ?? null}
                    shares={stockRatios.ttm.shares ?? null}
                    netDebt={stockRatios.ratios.net_debt ?? null}
                    fcf={
                      stockRatios.ttm.cfo !== null && stockRatios.ttm.cfo !== undefined && stockRatios.ttm.capex !== null && stockRatios.ttm.capex !== undefined
                        ? stockRatios.ttm.cfo - Math.abs(stockRatios.ttm.capex)
                        : null
                    }
                    netIncome={stockRatios.ttm.net_income ?? null}
                  />
                ) : stockRatios?.financial ? (
                  <div className="rounded-2xl border border-zinc-800 bg-zinc-950/80 p-6">
                    <h3 className="text-base font-bold text-white mb-2">DCF Değerleme</h3>
                    <p className="text-sm text-zinc-300">
                      Bankalar ve sigorta şirketlerinde borç operasyonun ham maddesidir; serbest nakit akışı ve firma değeri anlamlı değildir. Bu şirketler için
                      PD/DD, F/K ve ROE birlikte değerlendirilir (Oranlar sekmesi).
                    </p>
                  </div>
                ) : (
                  dcfData && <DcfTerminalCard dcf={dcfData} />
                )}
                {navStakes.length > 0 && navHoldingMcap && headerPrice !== null && navData && (
                  <NavCalculator
                    ticker={cleanTicker}
                    price={headerPrice}
                    holdingMcap={navHoldingMcap}
                    stakes={navStakes}
                    source={navData.source}
                    fetchedAt={navData.fetched_at}
                  />
                )}
                {financialHealthData && <FinancialHealthCard health={financialHealthData} />}
              </>
            ),
          },
        ]
      : []),
    ...(keyLevelsData ? [{ id: "teknik", label: "Teknik", content: <KeyLevelsCard data={keyLevelsData} /> }] : []),
    {
      id: "haberler",
      label: `KAP & Haberler (${reports.length})`,
      content: (
        <div>
          <div className="flex items-center gap-2 mb-6">
            <Activity className="w-4 h-4 text-cyan-400" />
            <h2 className="text-lg font-display font-bold text-white">{cleanTicker} İstihbarat & Analiz Arşivi</h2>
          </div>
          {reports.length > 0 ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {reports.map((report) => (
                <ReportCard key={report.slug} report={report} />
              ))}
            </div>
          ) : (
            <div className="rounded-2xl border border-zinc-800 bg-zinc-900/40 p-12 text-center">
              <Building2 className="w-10 h-10 text-zinc-400 mx-auto mb-3" />
              <h3 className="text-sm font-semibold text-zinc-300">Bu hisse için henüz arşiv kaydı bulunmuyor</h3>
              <p className="text-xs text-zinc-400 mt-1 max-w-md mx-auto">
                ${cleanTicker} için yeni bir KAP bildirimi geldiğinde analiz edilerek burada listelenecektir.
              </p>
              <Link href="/kategori/bist" className="inline-flex items-center gap-1.5 text-xs text-cyan-400 hover:underline mt-6">
                Tüm BIST analizlerini incele <ArrowUpRight className="w-3.5 h-3.5" />
              </Link>
            </div>
          )}
        </div>
      ),
    },
  ];

  const financialProductJsonLd = {
    "@context": "https://schema.org",
    "@type": "FinancialProduct",
    name: `${cleanTicker} - ${companyName}`,
    tickerSymbol: cleanTicker,
    exchange: "BIST",
    currency: "TRY",
    description: `Borsa İstanbul $${cleanTicker} (${companyName}) hisse senedi teknik analizi, KAP bildirimleri, DCF hedef fiyatı ve finansal çarpanları.`,
    url: `https://esham.pages.dev/hisse/${cleanTicker}`,
  };

  const breadcrumbJsonLd = {
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    itemListElement: [
      {
        "@type": "ListItem",
        position: 1,
        name: "Ana Sayfa",
        item: "https://esham.pages.dev",
      },
      {
        "@type": "ListItem",
        position: 2,
        name: "BIST Piyasaları",
        item: "https://esham.pages.dev/kategori/bist",
      },
      {
        "@type": "ListItem",
        position: 3,
        name: `$${cleanTicker} Analizi`,
        item: `https://esham.pages.dev/hisse/${cleanTicker}`,
      },
    ],
  };

  return (
    <div className="container mx-auto px-6 py-12 max-w-6xl">
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(financialProductJsonLd) }}
      />
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(breadcrumbJsonLd) }}
      />
      {/* Breadcrumb Navigation */}
      <div className="flex items-center gap-3 mb-8 text-xs text-zinc-400">
        <Link
          href="/"
          className="inline-flex items-center gap-1.5 hover:text-white transition-colors"
        >
          <ArrowLeft className="w-3.5 h-3.5" /> Ana Sayfa
        </Link>
        <span>/</span>
        <Link href="/kategori/bist" className="hover:text-white transition-colors">
          BIST Piyasaları
        </Link>
        <span>/</span>
        <span className="text-zinc-300 font-mono font-semibold">${cleanTicker}</span>
      </div>

      {/* Şirket başlığı: yalnızca veriden gelen bilgiler (sektör, fiyat, çarpanlar) */}
      <div
        className="rounded-2xl border p-6 md:p-8 mb-8"
        style={{ background: "linear-gradient(145deg, var(--surface) 0%, rgba(15, 23, 42, 0.4) 100%)", borderColor: "var(--border)" }}
      >
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-6">
          <div>
            <div className="flex flex-wrap items-center gap-3 mb-2">
              <span className="text-2xl md:text-3xl font-mono font-bold tracking-tight text-white">${cleanTicker}</span>
              {stockRatios && (
                <Link
                  href={`/hisseler?sector=${encodeURIComponent(stockRatios.sector)}`}
                  className="text-xs font-semibold tracking-wider uppercase px-2.5 py-1 rounded bg-sky-500/10 text-sky-400 border border-sky-500/20 hover:border-sky-400/50"
                >
                  {stockRatios.sector}
                </Link>
              )}
              <WatchlistDrawer currentTicker={cleanTicker} />
            </div>
            <h1 className="text-base md:text-lg font-medium text-zinc-300">{companyName}</h1>
          </div>

          <div className="flex items-center gap-4 bg-zinc-900/80 border border-zinc-800 rounded-xl p-4 self-start lg:self-auto min-w-[200px]">
            <div>
              <p className="text-xs uppercase font-bold tracking-wider text-zinc-400">
                {liveQuote?.value ? "Anlık Fiyat" : "Son Fiyat"}
              </p>
              <p className="text-2xl font-mono font-bold text-white mt-0.5 tabular-nums">
                {livePrice !== null
                  ? `${livePrice.toLocaleString("tr-TR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} ₺`
                  : headerPrice !== null
                    ? `${headerPrice.toLocaleString("tr-TR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} ₺`
                    : "—"}
              </p>
            </div>
            {liveQuote?.change && (
              <div
                className={`flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-mono font-bold ${
                  liveQuote.up
                    ? "bg-emerald-500/15 text-emerald-400 border border-emerald-500/30"
                    : "bg-rose-500/15 text-rose-400 border border-rose-500/30"
                }`}
              >
                {liveQuote.up ? <TrendingUp className="w-3.5 h-3.5" /> : <TrendingDown className="w-3.5 h-3.5" />}
                {liveQuote.change}
              </div>
            )}
          </div>
        </div>

        <dl className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-4 mt-8 pt-6 border-t border-zinc-800/80 text-sm">
          {summary.map((m) => (
            <div key={m.label}>
              <dt className="text-zinc-400 mb-1 text-xs">{m.label}</dt>
              <dd className="font-mono font-semibold text-zinc-100 tabular-nums">{m.value}</dd>
              {m.range && <RangeBar {...m.range} />}
            </div>
          ))}
        </dl>
      </div>

      <StockTabs tabs={tabs} />

      <div className="mt-10">
        <Newsletter />
      </div>
    </div>
  );
}
