import { SITE_URL } from "@/lib/config";
import { getIndexableReports, categoryLabel, getReportImageUrl } from "@/lib/content";

export const dynamic = "force-static";

// Tek kaynak — layout.tsx ve sitemap.ts ile senkron.

function escapeXml(value: string): string {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&apos;");
}

/** Göreli yolu mutlak URL'e çevirir. */
function absoluteUrl(path: string): string {
  return path.startsWith("http") ? path : `${SITE_URL}${path}`;
}

// RSS beslemesi — bülten/okuyucu entegrasyonu ve organik dağıtım için.
export async function GET() {
  const reports = getIndexableReports().slice(0, 50);

  const items = reports
    .map((r) => {
      const url = `${SITE_URL}/rapor/${r.slug}`;
      const imageUrl = absoluteUrl(getReportImageUrl(r));
      // Kart görseli RSS okuyucularında küçük resim olarak görünür (<enclosure>).
      const enclosure = `<enclosure url="${escapeXml(imageUrl)}" type="image/png" length="0" />`;
      // <content:encoded> tam makale gövdesini feed okuyuculara iletir.
      const fullContent = `<content:encoded><![CDATA[${r.body}]]></content:encoded>`;

      return `    <item>
      <title>${escapeXml(r.title)}</title>
      <link>${url}</link>
      <guid isPermaLink="true">${url}</guid>
      <pubDate>${new Date(r.publishedAt).toUTCString()}</pubDate>
      <description>${escapeXml(r.summary)}</description>
      <category>${escapeXml(categoryLabel(r.category))}</category>
      ${enclosure}
      ${fullContent}
      ${r.author ? `<dc:creator>${escapeXml(r.author)}</dc:creator>` : ""}
    </item>`;
    })
    .join("\n");

  const lastBuildDate = reports[0]
    ? new Date(reports[0].publishedAt).toUTCString()
    : new Date().toUTCString();

  const xml = `<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"
  xmlns:content="http://purl.org/rss/1.0/modules/content/"
  xmlns:dc="http://purl.org/dc/elements/1.1/"
  xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>Esham — Kamuya Açık Bildirim ve Veri Özetleri</title>
    <link>${SITE_URL}</link>
    <atom:link href="${SITE_URL}/feed.xml" rel="self" type="application/rss+xml" />
    <description>BIST, küresel makro ve halka arz raporları her gün yapay zeka ile analiz edilir.</description>
    <language>tr</language>
    <lastBuildDate>${lastBuildDate}</lastBuildDate>
    <ttl>60</ttl>
    <image>
      <url>${SITE_URL}/cards/default-bist.png</url>
      <title>Esham</title>
      <link>${SITE_URL}</link>
    </image>
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
