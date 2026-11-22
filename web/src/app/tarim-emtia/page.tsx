import { SITE_URL } from "@/lib/config";
import { DEFAULT_OG_IMAGE } from "@/lib/seo";
import type { Metadata } from "next";
import Link from "next/link";
import { promises as fs } from "fs";
import path from "path";
import { ChevronRight } from "lucide-react";
import { TuribMarketClient, type TuribMarketDataset } from "./client";

export const metadata: Metadata = {
  title: "Emtia, Petrol & Boğaz Geçişleri",
  description:
    "Brent petrol, İstanbul Boğazı haftalık gemi geçiş sayıları (IMF PortWatch), TÜRİB lisanslı depo fiyatları, TMO alım fiyatları ve TCMB kurlarıyla döviz cinsinden getiri. Her bölümde kaynak ve veri tarihi yazılıdır.",
  alternates: {
    canonical: `${SITE_URL}/tarim-emtia`,
  },
  keywords: [
    "TÜRİB",
    "Tarımsal Emtia",
    "Ham Petrol",
    "Brent Petrol",
    "Boğaz Geçişleri",
    "TMO Alım Fiyatları",
    "Buğday Fiyatları",
  ],
  openGraph: {
    title: "Emtia, Petrol & Boğaz Geçişleri | Esham",
    description:
      "Brent petrol, İstanbul Boğazı geçiş sayıları, TÜRİB lisanslı depo ürün fiyatları ve TMO alım fiyatları; kaynak ve veri tarihiyle.",
    url: `${SITE_URL}/tarim-emtia`,
    images: [DEFAULT_OG_IMAGE],
  },
};

async function getTuribMarketData(): Promise<TuribMarketDataset> {
  try {
    const filePath = path.join(process.cwd(), "public", "data", "turib-market.json");
    const raw = await fs.readFile(filePath, "utf-8");
    return JSON.parse(raw) as TuribMarketDataset;
  } catch (err) {
    // Dosya yoksa/okunamazsa sayı uydurmayız: boş veri seti, bölümler "veri yok" notuna dönüşür.
    return {
      updatedAt: "",
      date: "",
      indices: [],
      spotCommodities: [],
      bulletinSummary: {},
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
        <span style={{ color: "var(--text-primary)" }}>Emtia, Petrol & Boğaz Geçişleri</span>
      </nav>

      {/* ── Client Terminal Component ── */}
      <TuribMarketClient dataset={dataset} />
    </div>
  );
}
