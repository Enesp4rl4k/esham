import { SITE_URL } from "@/lib/config";
import type { Metadata } from "next";
import Link from "next/link";
import { Inter, Outfit } from "next/font/google";
import "./globals.css";
import { CATEGORIES, type CategorySlug } from "@/lib/content";
import { MobileMenu } from "@/components/MobileMenu";
import { DesktopNav } from "@/components/DesktopNav";
import { SearchCommandPalette } from "@/components/SearchCommandPalette";
import { loadUniverse } from "@/lib/stocks";
import { ThemeToggle } from "@/components/ThemeToggle";
import { WatchlistDrawer } from "@/components/WatchlistDrawer";

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin", "latin-ext"],
  display: "swap",
});

const outfit = Outfit({
  variable: "--font-outfit",
  subsets: ["latin", "latin-ext"],
  display: "swap",
});

const CF_ANALYTICS_TOKEN = process.env.NEXT_PUBLIC_CF_ANALYTICS_TOKEN;
const GSC_VERIFICATION = process.env.NEXT_PUBLIC_GSC_VERIFICATION;

export const metadata: Metadata = {
  metadataBase: new URL(`${SITE_URL}`),
  ...(GSC_VERIFICATION ? { verification: { google: GSC_VERIFICATION } } : {}),
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
  authors: [{ name: "Esham Finansal İstihbarat", url: `${SITE_URL}` }],
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
    url: `${SITE_URL}`,
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
      suppressHydrationWarning
    >
      <head>
        <script
          dangerouslySetInnerHTML={{
            __html: `try{var t=localStorage.getItem("esham-theme");if(t!=="light"&&t!=="dark")t=matchMedia("(prefers-color-scheme: light)").matches?"light":"dark";document.documentElement.dataset.theme=t}catch(e){document.documentElement.dataset.theme="dark"}`,
          }}
        />
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{
            __html: JSON.stringify({
              "@context": "https://schema.org",
              "@graph": [
                {
                  "@type": "Organization",
                  "@id": `${SITE_URL}/#organization`,
                  "name": "Esham",
                  "url": `${SITE_URL}`,
                  "logo": {
                    "@type": "ImageObject",
                    "url": `${SITE_URL}/cards/default-bist.png`,
                    "width": 1200,
                    "height": 630
                  },
                  "description": "Borsa İstanbul, VİOP, KAP bildirimleri, TÜRİB tarımsal emtia ve makroekonomik veriler için yapay zeka destekli finansal istihbarat platformu."
                },
                {
                  "@type": "WebSite",
                  "@id": `${SITE_URL}/#website`,
                  "url": `${SITE_URL}`,
                  "name": "Esham",
                  "publisher": { "@id": `${SITE_URL}/#organization` },
                  "potentialAction": {
                    "@type": "SearchAction",
                    "target": `${SITE_URL}/arama?q={search_term_string}`,
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
        <a
          href="#icerik"
          className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-[200] focus:px-3 focus:py-2 focus:rounded-lg focus:bg-zinc-900 focus:text-white focus:border focus:border-amber-500"
        >
          Ana içeriğe geç
        </a>
        {/* ── Header ──────────────────────────────────────────── */}
        <header
          className="sticky top-0 z-50 w-full backdrop-blur-md"
          style={{ borderBottom: "1px solid var(--border)", background: "var(--header-bg)" }}
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
            </div>

            <DesktopNav />

            <div className="flex items-center gap-2">
              <SearchCommandPalette stocks={loadUniverse()?.stocks.map((s) => ({ ticker: s.ticker, name: s.name, sector: s.sector })) ?? []} />
              <WatchlistDrawer />
              <ThemeToggle />
              <MobileMenu />
            </div>
          </div>
        </header>

        {CF_ANALYTICS_TOKEN ? (
          <script
            defer
            src="https://static.cloudflareinsights.com/beacon.min.js"
            data-cf-beacon={JSON.stringify({ token: CF_ANALYTICS_TOKEN })}
          />
        ) : null}

        {/* ── Main ─────────────────────────────────────────────── */}
        <main id="icerik" className="flex-1 w-full">{children}</main>

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
                  className="text-xs font-bold tracking-[0.15em] uppercase self-center mr-2"
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
                <Link
                  href="/yontem"
                  className="text-sm transition-opacity hover:opacity-70"
                  style={{ color: "var(--text-secondary)" }}
                >
                  Yöntem ve Kaynaklar
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
                className="text-xs font-mono tracking-[0.22em] text-zinc-600/80 hover:text-zinc-400 transition-colors duration-300 select-none cursor-default"
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
