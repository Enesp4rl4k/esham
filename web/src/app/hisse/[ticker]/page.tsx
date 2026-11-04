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
import { InteractiveStockChart } from "@/components/InteractiveStockChart";
import { StockCorporateActionsCard } from "@/components/StockCorporateActionsCard";
import { StockPeerComparisonCard } from "@/components/StockPeerComparisonCard";

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

  return {
    title: `$${clean} Hisse Analizi & KAP Bildirimleri | Esham Terminal`,
    description: `Borsa İstanbul $${clean} hissesine ait en son KAP bildirimleri, teknik görünüm, sözleşmeler ve şirket haberleri arşivi.`,
    openGraph: {
      title: `$${clean} Hisse Analizi | Esham Piyasa İstihbaratı`,
      description: `$${clean} hisse analizi, teknik seviyeler ve KAP bildirim geçmişi.`,
      url: `https://esham.pages.dev/hisse/${clean}`,
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

const BIST30_PILLS = [
  "THYAO", "ASELS", "GARAN", "EREGL", "KCHOL", "TUPRS",
  "BIMAS", "AKBNK", "ISCTR", "SISE", "SAHOL", "YKBNK",
];

export default async function TickerPage({
  params,
}: {
  params: Promise<Params>;
}) {
  const { ticker } = await params;
  const cleanTicker = ticker.toUpperCase();

  const reports = getReportsByTicker(cleanTicker);
  const [tickerData, quantData, buybacksData, dividendsData] = await Promise.all([
    loadMarketTickerData(),
    loadQuantValuationData(),
    loadBuybacksData(),
    loadDividendsData(),
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

  const companyName = COMPANY_NAMES[cleanTicker] || `${cleanTicker} Pay Piyasası`;

  return (
    <div className="container mx-auto px-6 py-12 max-w-6xl">
      {/* Breadcrumb Navigation */}
      <div className="flex items-center gap-3 mb-8 text-xs text-zinc-500">
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

      {/* Şirket Başlık & Finansal Özet Kartı */}
      <div
        className="rounded-2xl border p-6 md:p-8 mb-10 relative overflow-hidden"
        style={{
          background: "linear-gradient(145deg, var(--surface) 0%, rgba(15, 23, 42, 0.4) 100%)",
          borderColor: "var(--border)",
        }}
      >
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-6">
          <div>
            <div className="flex items-center gap-3 mb-2">
              <span className="text-2xl md:text-3xl font-mono font-bold tracking-tight text-white">
                ${cleanTicker}
              </span>
              <span className="text-[11px] font-semibold tracking-wider uppercase px-2.5 py-1 rounded bg-sky-500/10 text-sky-400 border border-sky-500/20">
                BIST Yıldız Pazar
              </span>
              <span className="text-[11px] font-semibold tracking-wider uppercase px-2.5 py-1 rounded bg-zinc-800 text-zinc-400 border border-zinc-700">
                Takasbank Saklama
              </span>
              <WatchlistDrawer currentTicker={cleanTicker} />
            </div>
            <h1 className="text-base md:text-lg font-medium text-zinc-300">
              {companyName}
            </h1>
          </div>

          {/* Canlı Fiyat Kutusu */}
          <div className="flex items-center gap-4 bg-zinc-900/80 border border-zinc-800 rounded-xl p-4 self-start lg:self-auto min-w-[200px]">
            <div>
              <p className="text-[10px] uppercase font-bold tracking-wider text-zinc-500">
                Anlık Seans Fiyatı
              </p>
              <p className="text-2xl font-mono font-bold text-white mt-0.5">
                {liveQuote?.value ? `${liveQuote.value} ₺` : "—"}
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
                {liveQuote.up ? (
                  <TrendingUp className="w-3.5 h-3.5" />
                ) : (
                  <TrendingDown className="w-3.5 h-3.5" />
                )}
                {liveQuote.change}
              </div>
            )}
          </div>
        </div>

        {/* Kurumsal Bilgi Şeridi */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mt-8 pt-6 border-t border-zinc-800/80 text-xs">
          <div>
            <span className="text-zinc-500 block mb-1">Kapsamdaki Rapor</span>
            <span className="font-mono font-semibold text-zinc-200">
              {reports.length} Analiz & Bildirim
            </span>
          </div>
          <div>
            <span className="text-zinc-500 block mb-1">İşlem Para Birimi</span>
            <span className="font-mono font-semibold text-zinc-200">TRY (Türk Lirası)</span>
          </div>
          <div>
            <span className="text-zinc-500 block mb-1">Takas Süresi</span>
            <span className="font-mono font-semibold text-zinc-200">T+2 Valör</span>
          </div>
          <div>
            <span className="text-zinc-500 block mb-1">Veri Kaynağı</span>
            <span className="font-mono font-semibold text-zinc-200">KAP + Borsa İstanbul</span>
          </div>
        </div>
      </div>

      {/* Diğer BIST 30 Hisseleri Hızlı Geçiş Barı */}
      <div className="mb-10">
        <p className="text-xs uppercase font-bold tracking-[0.15em] text-zinc-500 mb-3">
          Hızlı Hisse Terminali
        </p>
        <div className="flex flex-wrap gap-2">
          {BIST30_PILLS.map((p) => (
            <Link
              key={p}
              href={`/hisse/${p}`}
              className={`px-3 py-1.5 rounded-lg text-xs font-mono font-semibold border transition-all ${
                p === cleanTicker
                  ? "bg-cyan-500/10 border-cyan-500 text-cyan-400 shadow-sm"
                  : "bg-zinc-900 border-zinc-800 text-zinc-400 hover:border-zinc-700 hover:text-white"
              }`}
            >
              ${p}
            </Link>
          ))}
        </div>
      </div>

      {/* ── Etkileşimli Fiyat Grafiği & Trend Görünümü ── */}
      <div className="mb-10">
        <InteractiveStockChart
          ticker={cleanTicker}
          currentPrice={
            liveQuote?.value
              ? parseFloat(liveQuote.value.replace("₺", "").replace(".", "").replace(",", ".")) || (keyLevelsData?.son_fiyat || 100)
              : (keyLevelsData?.son_fiyat || 100)
          }
          changePct={
            liveQuote?.change
              ? parseFloat(liveQuote.change.replace("%", "").replace("+", "").replace(",", ".")) || (keyLevelsData?.gunluk_degisim_yuzde || 0)
              : (keyLevelsData?.gunluk_degisim_yuzde || 0)
          }
          sma20={keyLevelsData?.hareketli_ortalamalar?.sma_20}
          sma50={keyLevelsData?.hareketli_ortalamalar?.sma_50}
        />
      </div>

      {/* İndirgenmiş Nakit Akışı (İNA / DCF) Değerleme Modeli */}
      {dcfData && (
        <div className="mb-10">
          <DcfTerminalCard dcf={dcfData} />
        </div>
      )}

      {/* Kurumsal Finansal Sağlık & Skor Kartı (Piotroski, Altman Z, DuPont) */}
      {financialHealthData && (
        <div className="mb-10">
          <FinancialHealthCard health={financialHealthData} />
        </div>
      )}

      {/* Teknik Eşikler & Temel Çarpanlar Grid */}
      {(keyLevelsData || fundamentalData) && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 mb-10">
          {keyLevelsData && <KeyLevelsCard data={keyLevelsData} />}
          {fundamentalData && <FundamentalMetricsCard data={fundamentalData} />}
        </div>
      )}

      {/* Kurumsal Sermaye Eylemleri (Pay Geri Alımı & Nakit Kâr Payı) */}
      <div className="mb-10">
        <StockCorporateActionsCard
          ticker={cleanTicker}
          buyback={companyBuyback}
          dividend={companyDividend}
        />
      </div>

      {/* Sektörel Akran Değerleme & Çarpan Karşılaştırması */}
      {companyQuant?.fundamental?.sektor && quantData && (
        <div className="mb-10">
          <StockPeerComparisonCard
            currentTicker={cleanTicker}
            currentSector={companyQuant.fundamental.sektor}
            quantData={quantData}
          />
        </div>
      )}

      {/* Şirkete Ait Raporlar & Bildirim Arşivi */}
      <div>
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-2">
            <Activity className="w-4 h-4 text-cyan-400" />
            <h2 className="text-lg font-display font-bold text-white">
              {cleanTicker} İstihbarat & Analiz Arşivi
            </h2>
          </div>
          <span className="text-xs text-zinc-500">
            Toplam {reports.length} kayıt listeleniyor
          </span>
        </div>

        {reports.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {reports.map((report) => (
              <ReportCard key={report.slug} report={report} />
            ))}
          </div>
        ) : (
          <div className="rounded-2xl border border-zinc-800 bg-zinc-900/40 p-12 text-center">
            <Building2 className="w-10 h-10 text-zinc-600 mx-auto mb-3" />
            <h3 className="text-sm font-semibold text-zinc-300">
              Bu hisse için henüz arşiv kaydı bulunmuyor
            </h3>
            <p className="text-xs text-zinc-500 mt-1 max-w-md mx-auto">
              ${cleanTicker} kodlu şirkete ait yeni bir KAP bildirimi, iş sözleşmesi veya teknik fiyat hareketi gerçekleştiğinde otomatik olarak analiz edilerek burada listelenecektir.
            </p>
            <div className="mt-6">
              <Link
                href="/kategori/bist"
                className="inline-flex items-center gap-1.5 text-xs text-cyan-400 hover:underline"
              >
                Tüm BIST analizlerini incele <ArrowUpRight className="w-3.5 h-3.5" />
              </Link>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
