import type { MetadataRoute } from "next";
import { loadUniverse } from "@/lib/stocks";
import { MIN_INDEXABLE, SCANS, runScan, sectorGroups } from "@/lib/programmatic";
import { getAllReports, getAllTickers, CATEGORIES, type CategorySlug } from "@/lib/content";

export const dynamic = "force-static";

const BASE_URL = "https://esham.pages.dev";

export default function sitemap(): MetadataRoute.Sitemap {
  const reports = getAllReports();
  const tickers = getAllTickers();

  // 1. Ana & Statik Hub Sayfaları
  const staticRoutes: MetadataRoute.Sitemap = [
    {
      url: BASE_URL,
      lastModified: new Date(),
      changeFrequency: "hourly",
      priority: 1.0,
    },
    {
      url: `${BASE_URL}/hisseler`,
      lastModified: new Date(),
      changeFrequency: "daily",
      priority: 0.95,
    },
    {
      url: `${BASE_URL}/tarim-emtia`,
      lastModified: new Date(),
      changeFrequency: "daily",
      priority: 0.9,
    },
    {
      url: `${BASE_URL}/halka-arz-takvimi`,
      lastModified: new Date(),
      changeFrequency: "daily",
      priority: 0.9,
    },
    {
      url: `${BASE_URL}/piyasa/devaluasyon-radari`,
      lastModified: new Date(),
      changeFrequency: "daily",
      priority: 0.85,
    },
    {
      url: `${BASE_URL}/piyasa/geri-alimlar`,
      lastModified: new Date(),
      changeFrequency: "daily",
      priority: 0.85,
    },
    {
      url: `${BASE_URL}/piyasa/temettu-takvimi`,
      lastModified: new Date(),
      changeFrequency: "daily",
      priority: 0.85,
    },
    {
      url: `${BASE_URL}/arsiv`,
      lastModified: new Date(),
      changeFrequency: "daily",
      priority: 0.8,
    },
    {
      url: `${BASE_URL}/arama`,
      lastModified: new Date(),
      changeFrequency: "monthly",
      priority: 0.4,
    },
  ];

  // 2. Kategori Sayfaları
  const categoryRoutes: MetadataRoute.Sitemap = (
    Object.keys(CATEGORIES) as CategorySlug[]
  ).map((slug) => ({
    url: `${BASE_URL}/kategori/${slug}`,
    lastModified: new Date(),
    changeFrequency: "daily" as const,
    priority: 0.8,
  }));

  // 3. Tekil Hisse Analiz Sayfaları (BIST-30 ve Yıldız Pazar)
  const stockRoutes: MetadataRoute.Sitemap = tickers.map((ticker) => ({
    url: `${BASE_URL}/hisse/${ticker.toUpperCase()}`,
    lastModified: new Date(),
    changeFrequency: "daily" as const,
    priority: 0.85,
  }));

  // 4. Analiz ve KAP Rapor Sayfaları
  const reportRoutes: MetadataRoute.Sitemap = reports.map((report) => ({
    url: `${BASE_URL}/rapor/${report.slug}`,
    lastModified: new Date(report.publishedAt),
    changeFrequency: "weekly" as const,
    priority: 0.7,
  }));

  // 5. Programatik sayfalar: yalnızca indekslenebilir (yeterli veri) olanlar
  const u = loadUniverse();
  const dataDate = u ? new Date(u.updated_at) : new Date();
  const sectorRoutes: MetadataRoute.Sitemap = u
    ? sectorGroups(u)
        .filter((g) => g.stocks.length >= MIN_INDEXABLE)
        .map((g) => ({ url: `${BASE_URL}/hisseler/sektor/${g.slug}`, lastModified: dataDate, changeFrequency: "daily" as const, priority: 0.8 }))
    : [];
  const scanRoutes: MetadataRoute.Sitemap = u
    ? SCANS.filter((sc) => runScan(u, sc).length >= MIN_INDEXABLE).map((sc) => ({
        url: `${BASE_URL}/hisseler/tarama/${sc.slug}`,
        lastModified: dataDate,
        changeFrequency: "daily" as const,
        priority: 0.8,
      }))
    : [];

  return [...staticRoutes, ...categoryRoutes, ...stockRoutes, ...sectorRoutes, ...scanRoutes, ...reportRoutes];
}
