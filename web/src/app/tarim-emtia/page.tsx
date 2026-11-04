import type { Metadata } from "next";
import Link from "next/link";
import { promises as fs } from "fs";
import path from "path";
import { ChevronRight } from "lucide-react";
import { TuribMarketClient, type TuribMarketDataset } from "./client";

export const metadata: Metadata = {
  title: "Emtia, Petrol & Tanker Navlun Terminali | Esham",
  description:
    "Ham petrol göstergeleri (Brent, WTI, Urals, Crack Spread), VLCC/Aframax tanker kiralama ücretleri (TCE), Türk Boğazları demurraj süreleri ve TÜRİB tarımsal emtia terminali.",
  alternates: {
    canonical: "https://esham.pages.dev/tarim-emtia",
  },
  keywords: [
    "TÜRİB",
    "Tarımsal Emtia",
    "Ham Petrol",
    "Brent Petrol",
    "WTI",
    "Tanker Navlun",
    "VLCC Kiralama",
    "Boğaz Bekleme Süreleri",
    "TÜPRAŞ Crack Spread",
    "Buğday Fiyatları",
    "Et Yem Paritesi",
  ],
  openGraph: {
    title: "Emtia, Petrol & Tanker Navlun Terminali | Esham",
    description:
      "Ham petrol piyasaları, tanker kiralama ücretleri (TCE), Türk Boğazları transit süreleri, TÜRİB lisanslı depo ürün fiyatları ve BIST rafineri-denizcilik etkisi.",
    url: "https://esham.pages.dev/tarim-emtia",
  },
};

async function getTuribMarketData(): Promise<TuribMarketDataset> {
  try {
    const filePath = path.join(process.cwd(), "public", "data", "turib-market.json");
    const raw = await fs.readFile(filePath, "utf-8");
    return JSON.parse(raw) as TuribMarketDataset;
  } catch (err) {
    // Fallback veriler (dosya henüz oluşmadıysa)
    return {
      updatedAt: new Date().toISOString(),
      date: new Date().toISOString().split("T")[0],
      indices: [
        {
          code: "TRBHUB",
          name: "TÜRİB Hububat Endeksi",
          value: 7910.25,
          valueStr: "7.910,25",
          change: 164.06,
          changePct: 2.12,
          changeStr: "+2,12%",
          high: 7950.0,
          low: 7740.0,
          volumeTon: 12450.5,
          volumeStr: "12.450,5 Ton",
        },
        {
          code: "TRBBGD",
          name: "TÜRİB Buğday Endeksi",
          value: 8120.5,
          valueStr: "8.120,50",
          change: 142.1,
          changePct: 1.78,
          changeStr: "+1,78%",
          high: 8160.0,
          low: 7980.0,
          volumeTon: 8900.0,
          volumeStr: "8.900,0 Ton",
        },
      ],
      spotCommodities: [
        {
          name: "BUĞDAY EKMEKLİK",
          code: "BUĞDAY EKMEKLİK",
          avgPrice: 18.19,
          avgPriceStr: "18,19 ₺/kg",
          minPrice: 17.5,
          maxPrice: 19.2,
          changePct: 5.4,
          changeStr: "+5,40%",
          volumeTon: 312500.0,
          volumeStr: "312.500,0 Ton",
          volumeTl: 5684375000.0,
          volumeTlStr: "5.684.375.000 ₺",
        },
      ],
      bulletinSummary: {
        totalVolumeTon: 625021.1,
        totalVolumeTonStr: "625.021,1 Ton",
        totalValueTl: 11523450000.0,
        totalValueTlStr: "11.523.450.000 ₺",
        hububatIndex: 7910.25,
        summaryText: "TÜRİB Hububat Endeksi: 7.910,25 (+2,12%)",
      },
      meatFeed: {
        cpiDate: "2026-11",
        meatCpi: 1540.0,
        headlineCpi: 1210.0,
        meatCpiAnnualPct: 30.51,
        headlineCpiAnnualPct: 31.52,
        meatInflationSpread: -1.01,
        macroCommentary: "Yıllık Et TÜFE Enflasyonu %30.5 seviyesinde gerçekleşti.",
        bistSectorImpact: "BIST Et & Gıda Hisseleri için girdi maliyetleri takip ediliyor.",
        parities: [
          {
            title: "Dana Besi / Besi Yemi Paritesi",
            meatType: "Karkas Et",
            feedType: "Karma Rasyon",
            meatPrice: 445.0,
            feedPrice: 15.79,
            ratio: 28.18,
            threshold: 20.0,
            isProfitable: true,
            status: "KÂRLI BESI ALANI",
            interpretation: "Parite 20 eşiğinin üzerinde; besicilik kârlı ve ahır kapasite kullanımı pozitif.",
          },
        ],
      },
      tmoComparison: [],
      storageBacktest: {},
      regionalArbitrage: { opportunities: [] },
      agriBist: { companies: [] },
      realReturns: [],
    };
  }
}

export default async function TarimEmtiaPage() {
  const dataset = await getTuribMarketData();

  return (
    <div className="container mx-auto px-6 py-8 md:py-12">
      {/* ── Breadcrumb ── */}
      <nav className="flex items-center gap-2 text-xs mb-8" style={{ color: "var(--text-muted)" }}>
        <Link href="/" className="hover:text-zinc-200 transition-colors">
          Ana Sayfa
        </Link>
        <ChevronRight className="w-3.5 h-3.5" />
        <span style={{ color: "var(--text-primary)" }}>Emtia, Petrol & Tanker Navlun Terminali</span>
      </nav>

      {/* ── Client Terminal Component ── */}
      <TuribMarketClient dataset={dataset} />
    </div>
  );
}
