import type { Metadata } from "next";
import { promises as fs } from "fs";
import path from "path";
import { getAllReports } from "@/lib/content";
import { TraderTerminalClient } from "./client";

export const metadata: Metadata = {
  title: "Trader Terminali — Modüler Seans Kokpiti & BIST İstihbarat Masası",
  description:
    "Borsa İstanbul yatırımcıları ve trader'lar için Bloomberg tarzı yapılandırılabilir seans öncesi ve gün içi işlem terminali. VİOP makası, pivot seviyeleri, canlı KAP akışı ve quant değerleme.",
  openGraph: {
    title: "Trader Terminali — Esham Finansal İstihbarat",
    description:
      "VİOP basis spread, BIST-30 teknik pivot masası, canlı KAP filtreleri, pay geri alımları ve kantitatif değerleme matrisi tek ekranda.",
  },
};

async function loadJsonFile(filename: string) {
  try {
    const filePath = path.join(process.cwd(), "public", "data", filename);
    const raw = await fs.readFile(filePath, "utf-8");
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

export default async function TerminalPage() {
  const [
    tickerData,
    quantData,
    viopData,
    macroData,
    devalData,
    buybacksData,
    dividendsData,
    turibData,
  ] = await Promise.all([
    loadJsonFile("market-ticker.json"),
    loadJsonFile("bist-quant-valuation.json"),
    loadJsonFile("viop-basis.json"),
    loadJsonFile("macro-barometer.json"),
    loadJsonFile("devaluation-radar.json"),
    loadJsonFile("bist-buybacks.json"),
    loadJsonFile("bist-dividends.json"),
    loadJsonFile("turib-market.json"),
  ]);

  const allReports = getAllReports();
  const recentReports = allReports.slice(0, 40);

  return (
    <TraderTerminalClient
      tickerData={tickerData}
      quantData={quantData}
      viopData={viopData}
      macroData={macroData}
      devalData={devalData}
      buybacksData={buybacksData}
      dividendsData={dividendsData}
      turibData={turibData}
      recentReports={recentReports}
    />
  );
}
