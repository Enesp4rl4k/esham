import type { Metadata } from "next";
import Link from "next/link";
import { Inter, Outfit } from "next/font/google";
import "./globals.css";
import { CATEGORIES, type CategorySlug } from "@/lib/content";
import { MobileMenu } from "@/components/MobileMenu";
import { DesktopNav } from "@/components/DesktopNav";
import { SearchCommandPalette } from "@/components/SearchCommandPalette";
import { loadUniverse } from "@/lib/stocks";
import { WatchlistDrawer } from "@/components/WatchlistDrawer";

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
  display: "swap",
});

const outfit = Outfit({
  variable: "--font-outfit",
  subsets: ["latin"],
  display: "swap",
});

export const metadata: Metadata = {
  metadataBase: new URL("https://esham.pages.dev"),
  title: {
    default: "Esham — BIST & Piyasa İstihbarat Platformu",
    template: "%s | Esham",
  },
  description:
    "Borsa İstanbul (BIST), VİOP, KAP bildirimleri, TÜRİB tarımsal emtia, temettü takvimi ve kur şoku radarı yapay zeka destekli kantitatif modellerle analiz edilir.",
  keywords: [
    "BIST 100",
    "Borsa İstanbul",
    "Hisse Analizi",
    "KAP Bildirimleri",
    "VİOP",
    "TÜRİB Tarımsal Emtia",
    "Et-Yem Paritesi",
    "Halka Arz Takvimi",
    "Temettü Takvimi",
    "Pay Geri Alımları",
    "Devalüasyon Radarı",
    "DCF Değerleme",
    "Finansal İstihbarat",
    "BIST 30",
    "Takasbank Teminat",
    "Ham Petrol ve Tanker Navlun"
  ],
  authors: [{ name: "Esham Finansal İstihbarat", url: "https://esham.pages.dev" }],
  creator: "Esham",
  publisher: "Esham",
  formatDetection: {
    email: false,
    address: false,
    telephone: false,
  },
  alternates: {
    canonical: "/",
    types: { "application/rss+xml": "/feed.xml" },
  },
  openGraph: {
    title: "Esham — BIST & Piyasa İstihbarat Platformu",
    description:
      "Borsa İstanbul, VİOP, KAP bildirimleri, TÜRİB emtia ve makro piyasa analizleri.",
    url: "https://esham.pages.dev",
    siteName: "Esham",
    locale: "tr_TR",
    type: "website",
    images: [
      {
        url: "/cards/default-bist.png",
        width: 1200,
        height: 630,
        alt: "Esham Piyasa İstihbaratı",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: "Esham — BIST & Piyasa İstihbarat Platformu",
    description:
      "Borsa İstanbul, VİOP, KAP ve TÜRİB piyasalarında yapay zeka destekli finansal istihbarat.",
    images: ["/cards/default-bist.png"],
    creator: "@eshamcomtr",
  },
  robots: {
    index: true,
    follow: true,
    googleBot: {
      index: true,
      follow: true,
      "max-video-preview": -1,
      "max-image-preview": "large",
      "max-snippet": -1,
    },
  },
  category: "finance",
};

const navItems: { href: string; label: string }[] = [
  { href: "/", label: "Ana Sayfa" },
  { href: "/tarim-emtia", label: "Tarımsal Emtia & Et-Yem" },
  { href: "/piyasa/geri-alimlar", label: "Pay Geri Alımları" },
  { href: "/piyasa/temettu-takvimi", label: "Temettü Takvimi" },
  { href: "/piyasa/devaluasyon-radari", label: "Kur Şoku Radarı" },
  ...(Object.keys(CATEGORIES) as CategorySlug[]).map((slug) => ({
    href: `/kategori/${slug}`,
    label: CATEGORIES[slug].label,
  })),
  { href: "/halka-arz-takvimi", label: "Halka Arz Takvimi" },
  { href: "/arsiv", label: "Arşiv" },
];

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="tr"
      className={`${inter.variable} ${outfit.variable} antialiased`}
    >
      <head>
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{
            __html: JSON.stringify({
              "@context": "https://schema.org",
              "@graph": [
                {
                  "@type": "Organization",
                  "@id": "https://esham.pages.dev/#organization",
                  "name": "Esham",
                  "url": "https://esham.pages.dev",
                  "logo": {
                    "@type": "ImageObject",
                    "url": "https://esham.pages.dev/cards/default-bist.png",
                    "width": 1200,
                    "height": 630
                  },
                  "description": "Borsa İstanbul, VİOP, KAP bildirimleri, TÜRİB tarımsal emtia ve makroekonomik veriler için yapay zeka destekli finansal istihbarat platformu."
                },
                {
                  "@type": "WebSite",
                  "@id": "https://esham.pages.dev/#website",
                  "url": "https://esham.pages.dev",
                  "name": "Esham",
                  "publisher": { "@id": "https://esham.pages.dev/#organization" },
                  "potentialAction": {
                    "@type": "SearchAction",
                    "target": "https://esham.pages.dev/arama?q={search_term_string}",
                    "query-input": "required name=search_term_string"
                  }
                }
              ]
            }),
          }}
        />
      </head>
      <body
        className="min-h-screen flex flex-col font-sans"
        style={{ background: "var(--background)", color: "var(--text-primary)" }}
      >
        {/* ── Header ──────────────────────────────────────────── */}
        <header
          className="sticky top-0 z-50 w-full backdrop-blur-md"
          style={{ borderBottom: "1px solid var(--border)", background: "rgba(10,10,10,0.85)" }}
        >
          <div className="container mx-auto px-6 h-14 flex items-center justify-between">
            {/* Wordmark */}
            <div className="flex items-center shrink-0 mr-4">
              <Link
                href="/"
                className="font-display font-bold text-lg tracking-tight flex items-center"
                style={{ color: "var(--text-primary)" }}
              >
                <span style={{ color: "var(--accent)" }}>Es</span>ham
              </Link>
              <span className="text-[10px] font-mono tracking-wider uppercase px-2 py-0.5 rounded bg-zinc-900 border border-zinc-800 text-zinc-400 hidden xl:inline ml-2.5">
                Finansal İstihbarat
              </span>
            </div>

            <DesktopNav />

            <div className="flex items-center gap-2">
              <SearchCommandPalette stocks={loadUniverse()?.stocks.map((s) => ({ ticker: s.ticker, name: s.name, sector: s.sector })) ?? []} />
              <WatchlistDrawer />
              <MobileMenu />
            </div>
          </div>
        </header>

        {/* ── Main ─────────────────────────────────────────────── */}
        <main className="flex-1 w-full">{children}</main>

        {/* ── Footer ───────────────────────────────────────────── */}
        <footer
          className="mt-24"
          style={{ borderTop: "1px solid var(--border)" }}
        >
          {/* Kategori linkleri */}
          <div
            className="border-b py-8"
            style={{ borderColor: "var(--border)" }}
          >
            <div className="container mx-auto px-6">
              <div className="flex flex-wrap gap-x-8 gap-y-3">
                <span
                  className="text-[10px] font-bold tracking-[0.15em] uppercase self-center mr-2"
                  style={{ color: "var(--text-muted)" }}
                >
                  Piyasalar & Veri
                </span>
                <Link
                  href="/tarim-emtia"
                  className="text-sm font-semibold transition-opacity hover:opacity-70"
                  style={{ color: "var(--accent)" }}
                >
                  Tarımsal Emtia & Et-Yem (TÜRİB)
                </Link>
                {(Object.keys(CATEGORIES) as CategorySlug[]).map((slug) => (
                  <Link
                    key={slug}
                    href={`/kategori/${slug}`}
                    className="text-sm transition-opacity hover:opacity-70"
                    style={{ color: "var(--text-secondary)" }}
                  >
                    {CATEGORIES[slug].label}
                  </Link>
                ))}
                <Link
                  href="/halka-arz-takvimi"
                  className="text-sm transition-opacity hover:opacity-70"
                  style={{ color: "var(--text-secondary)" }}
                >
                  Halka Arz Takvimi
                </Link>
                <Link
                  href="/arsiv"
                  className="text-sm transition-opacity hover:opacity-70"
                  style={{ color: "var(--text-secondary)" }}
                >
                  Arşiv
                </Link>
              </div>
            </div>
          </div>

          {/* Alt satır */}
          <div className="py-6">
            <div className="container mx-auto px-6 flex flex-col sm:flex-row items-center justify-between gap-3">
              <p className="text-xs" style={{ color: "var(--text-muted)" }}>
                © {new Date().getFullYear()}{" "}
                <span style={{ color: "var(--accent)" }} className="font-semibold">Esham</span>.
                {" "}Buradaki içerikler yatırım tavsiyesi değildir.
              </p>

              {/* Easter Egg */}
              <span
                className="text-[10px] font-mono tracking-[0.22em] text-zinc-600/80 hover:text-zinc-400 transition-colors duration-300 select-none cursor-default"
                title="OODA Loop"
              >
                observe orient decide act
              </span>

              <div className="flex items-center gap-6">
                <Link
                  href="/feed.xml"
                  className="text-xs transition-opacity hover:opacity-70"
                  style={{ color: "var(--text-muted)" }}
                >
                  RSS
                </Link>
                <Link
                  href="/sitemap.xml"
                  className="text-xs transition-opacity hover:opacity-70"
                  style={{ color: "var(--text-muted)" }}
                >
                  Sitemap
                </Link>
              </div>
            </div>
          </div>
        </footer>
      </body>
    </html>
  );
}
