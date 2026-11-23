import { SITE_URL } from "@/lib/config";
import type { MetadataRoute } from "next";
import { loadUniverse } from "@/lib/stocks";
import { MIN_INDEXABLE, SCANS, comparePairs, runScan, sectorGroups } from "@/lib/programmatic";
import { MIN_CATEGORY_FUNDS, categoryGroups } from "@/lib/funds";
import { loadFundUniverse } from "@/lib/funds-data";
import { getAllReports, getAllTickers, isIndexableReport, CATEGORIES, type CategorySlug } from "@/lib/content";

export const dynamic = "force-static";


export default function sitemap(): MetadataRoute.Sitemap {
  const reports = getAllReports();
  const tickers = getAllTickers();

  // 1. Ana & Statik Hub Sayfaları
  const staticRoutes: MetadataRoute.Sitemap = [
    {
      url: SITE_URL,
      lastModified: new Date(),
      changeFrequency: "hourly",
      priority: 1.0,
    },
    {
      url: `${SITE_URL}/hisseler`,
      lastModified: new Date(),
      changeFrequency: "daily",
      priority: 0.95,
    },
    {
      url: `${SITE_URL}/tarim-emtia`,
      lastModified: new Date(),
      changeFrequency: "daily",
      priority: 0.9,
    },
    {
      url: `${SITE_URL}/halka-arz-takvimi`,
      lastModified: new Date(),
      changeFrequency: "daily",
      priority: 0.9,
    },
    {
      url: `${SITE_URL}/piyasa/temettu-takvimi`,
      lastModified: new Date(),
      changeFrequency: "daily",
      priority: 0.7,
    },
    {
      url: `${SITE_URL}/piyasa/geri-alimlar`,
      lastModified: new Date(),
      changeFrequency: "daily",
      priority: 0.7,
    },
    {
      url: `${SITE_URL}/piyasa/makro-gostergeler`,
      lastModified: new Date(),
      changeFrequency: "daily",
      priority: 0.7,
    },
    {
      url: `${SITE_URL}/arsiv`,
      lastModified: new Date(),
      changeFrequency: "daily",
      priority: 0.8,
    },
    {
      url: `${SITE_URL}/yontem`,
      lastModified: new Date(),
      changeFrequency: "monthly",
      priority: 0.6,
    },
    {
      url: `${SITE_URL}/gizlilik`,
      lastModified: new Date(),
      changeFrequency: "yearly",
      priority: 0.2,
    },
    {
      url: `${SITE_URL}/kullanim-sartlari`,
      lastModified: new Date(),
      changeFrequency: "yearly",
      priority: 0.2,
    },
    {
      url: `${SITE_URL}/iletisim`,
      lastModified: new Date(),
      changeFrequency: "yearly",
      priority: 0.2,
    },
    {
      url: `${SITE_URL}/arama`,
      lastModified: new Date(),
      changeFrequency: "monthly",
      priority: 0.4,
    },
  ];

  // 2. Kategori Sayfaları
  const categoryRoutes: MetadataRoute.Sitemap = (
    Object.keys(CATEGORIES) as CategorySlug[]
  ).map((slug) => ({
    url: `${SITE_URL}/kategori/${slug}`,
    lastModified: new Date(),
    changeFrequency: "daily" as const,
    priority: 0.8,
  }));

  // 3. Tekil Hisse Analiz Sayfaları (BIST-30 ve Yıldız Pazar)
  const stockRoutes: MetadataRoute.Sitemap = tickers.map((ticker) => ({
    url: `${SITE_URL}/hisse/${ticker.toUpperCase()}`,
    lastModified: new Date(),
    changeFrequency: "daily" as const,
    priority: 0.85,
  }));

  // 4. Analiz ve KAP Rapor Sayfaları
  const indexable = reports.filter(isIndexableReport);
  console.log(`[ince-icerik] ${indexable.length} rapor indeksli, ${reports.length - indexable.length} rapor noindex (sitemap/RSS dışı)`);
  const reportRoutes: MetadataRoute.Sitemap = indexable.map((report) => ({
    url: `${SITE_URL}/rapor/${report.slug}`,
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
        .map((g) => ({ url: `${SITE_URL}/hisseler/sektor/${g.slug}`, lastModified: dataDate, changeFrequency: "daily" as const, priority: 0.8 }))
    : [];
  const scanRoutes: MetadataRoute.Sitemap = u
    ? SCANS.filter((sc) => runScan(u, sc).length >= MIN_INDEXABLE).map((sc) => ({
        url: `${SITE_URL}/hisseler/tarama/${sc.slug}`,
        lastModified: dataDate,
        changeFrequency: "daily" as const,
        priority: 0.8,
      }))
    : [];

  const compareRoutes: MetadataRoute.Sitemap = u
    ? comparePairs(u).map((p) => ({ url: `${SITE_URL}/karsilastir/${p.slug}`, lastModified: dataDate, changeFrequency: "weekly" as const, priority: 0.6 }))
    : [];

  // 6. Fonlar: tarayıcı + kategori sıralamaları (yeterli fonlu) + fon sayfaları
  const fu = loadFundUniverse();
  const fundDate = fu ? new Date(fu.updated_at) : new Date();
  const fundRoutes: MetadataRoute.Sitemap = fu
    ? [
        { url: `${SITE_URL}/fonlar`, lastModified: fundDate, changeFrequency: "daily" as const, priority: 0.9 },
        ...categoryGroups(fu.funds)
          .filter((c) => c.funds.length >= MIN_CATEGORY_FUNDS)
          .map((c) => ({ url: `${SITE_URL}/fonlar/kategori/${c.slug}`, lastModified: fundDate, changeFrequency: "daily" as const, priority: 0.75 })),
        ...fu.funds.map((f) => ({ url: `${SITE_URL}/fon/${f.code}`, lastModified: fundDate, changeFrequency: "daily" as const, priority: 0.7 })),
      ]
    : [];

  return [...staticRoutes, ...categoryRoutes, ...stockRoutes, ...sectorRoutes, ...scanRoutes, ...compareRoutes, ...fundRoutes, ...reportRoutes];
}
