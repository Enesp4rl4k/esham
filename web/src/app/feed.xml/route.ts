import { getAllReports } from "@/lib/content";

export const dynamic = 'force-static';
const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL ?? "https://esham.com.tr";

function escapeXml(value: string): string {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&apos;");
}

// RSS beslemesi — bülten/okuyucu entegrasyonu ve organik dağıtım için.
export async function GET() {
  const reports = getAllReports().slice(0, 50);

  const items = reports
    .map(
      (r) => `    <item>
      <title>${escapeXml(r.title)}</title>
      <link>${SITE_URL}/rapor/${r.slug}</link>
      <guid>${SITE_URL}/rapor/${r.slug}</guid>
      <pubDate>${new Date(r.publishedAt).toUTCString()}</pubDate>
      <description>${escapeXml(r.summary)}</description>
    </item>`,
    )
    .join("\n");

  const xml = `<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Esham — Yapay Zeka Destekli Ekonomi Analizi</title>
    <link>${SITE_URL}</link>
    <description>BIST, küresel makro ve halka arz raporları</description>
    <language>tr</language>
    <lastBuildDate>${
      reports[0] ? new Date(reports[0].publishedAt).toUTCString() : new Date().toUTCString()
    }</lastBuildDate>
${items}
  </channel>
</rss>`;

  return new Response(xml, {
    headers: {
      "Content-Type": "application/rss+xml; charset=utf-8",
      "Cache-Control": "public, max-age=3600",
    },
  });
}
