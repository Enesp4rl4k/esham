import type { MetadataRoute } from "next";
import { getAllReports, CATEGORIES, type CategorySlug } from "@/lib/content";

export const dynamic = "force-static";

const BASE_URL = "https://esham.pages.dev";

export default function sitemap(): MetadataRoute.Sitemap {
  const reports = getAllReports();

  // Statik sayfalar
  const staticRoutes: MetadataRoute.Sitemap = [
    {
      url: BASE_URL,
      lastModified: new Date(),
      changeFrequency: "daily",
      priority: 1,
    },
    {
      url: `${BASE_URL}/arsiv`,
      lastModified: new Date(),
      changeFrequency: "daily",
      priority: 0.8,
    },
  ];

  // Kategori sayfaları
  const categoryRoutes: MetadataRoute.Sitemap = (
    Object.keys(CATEGORIES) as CategorySlug[]
  ).map((slug) => ({
    url: `${BASE_URL}/kategori/${slug}`,
    lastModified: new Date(),
    changeFrequency: "daily" as const,
    priority: 0.8,
  }));

  // Rapor sayfaları
  const reportRoutes: MetadataRoute.Sitemap = reports.map((report) => ({
    url: `${BASE_URL}/rapor/${report.slug}`,
    lastModified: new Date(report.publishedAt),
    changeFrequency: "weekly" as const,
    priority: 0.6,
  }));

  return [...staticRoutes, ...categoryRoutes, ...reportRoutes];
}
