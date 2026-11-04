import type { Metadata } from "next";
import Link from "next/link";
import { Inter, Outfit } from "next/font/google";
import "./globals.css";
import { CATEGORIES, type CategorySlug } from "@/lib/content";
import { MobileMenu } from "@/components/MobileMenu";
import { DesktopNav } from "@/components/DesktopNav";
import { SearchCommandPalette } from "@/components/SearchCommandPalette";
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
    default: "Esham — Yapay Zeka Destekli Piyasa Analizi",
    template: "%s — Esham",
  },
  description:
    "BIST, küresel makro veriler, TÜRİB tarımsal emtia endeksleri ve KAP halka arz raporları her gün yapay zeka tarafından analiz edilir.",
  alternates: {
    types: { "application/rss+xml": "/feed.xml" },
  },
  openGraph: {
    title: "Esham — Yapay Zeka Destekli Piyasa Analizi",
    description:
      "BIST, küresel makro, TÜRİB emtia ve halka arz raporları her gün yapay zeka ile analiz edilir.",
    type: "website",
    locale: "tr_TR",
  },
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
              <SearchCommandPalette />
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
