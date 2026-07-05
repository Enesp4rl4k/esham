import type { Metadata } from "next";
import Link from "next/link";
import { Inter, Outfit } from "next/font/google";
import "./globals.css";
import { CATEGORIES, type CategorySlug } from "@/lib/content";

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
});

const outfit = Outfit({
  variable: "--font-outfit",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  metadataBase: new URL("https://esham.com.tr"),
  title: {
    default: "Esham — Yapay Zeka Destekli Ekonomi & Piyasa Analizi",
    template: "%s — Esham",
  },
  description:
    "BIST, küresel makro veriler ve KAP halka arz raporları her gün yapay zeka tarafından analiz edilir. Sıfır gürültü, maksimum içgörü.",
  alternates: {
    types: { "application/rss+xml": "/feed.xml" },
  },
  openGraph: {
    title: "Esham — Yapay Zeka Destekli Ekonomi & Piyasa Analizi",
    description:
      "BIST, küresel makro ve halka arz raporları her gün yapay zeka ile analiz edilir.",
    type: "website",
    locale: "tr_TR",
  },
};

const navItems: { href: string; label: string }[] = [
  { href: "/", label: "Ana Sayfa" },
  ...(Object.keys(CATEGORIES) as CategorySlug[]).map((slug) => ({
    href: `/kategori/${slug}`,
    label: CATEGORIES[slug].label,
  })),
];

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="tr"
      className={`${inter.variable} ${outfit.variable} dark antialiased`}
    >
      <body className="min-h-screen bg-black text-zinc-100 flex flex-col font-sans selection:bg-cyan-500/30 selection:text-cyan-200">
        <header className="sticky top-0 z-50 w-full border-b border-zinc-800 bg-black/50 backdrop-blur-md">
          <div className="container mx-auto px-6 h-16 flex items-center justify-between">
            <Link
              href="/"
              className="font-outfit font-bold text-xl tracking-tight text-white flex items-center gap-2"
            >
              <span><span className="text-cyan-400">Es</span>ham</span>
            </Link>
            <nav className="hidden md:flex items-center gap-8 text-sm font-medium text-zinc-400">
              {navItems.map((item) => (
                <Link
                  key={item.href}
                  href={item.href}
                  className="hover:text-white transition-colors"
                >
                  {item.label}
                </Link>
              ))}
            </nav>
          </div>
        </header>
        <main className="flex-1 w-full">{children}</main>
        <footer className="py-10 border-t border-zinc-900 mt-20">
          <div className="container mx-auto px-6 flex flex-col gap-4 text-center text-sm text-zinc-600">
            <p>
              <span className="text-cyan-400 font-semibold">Esham</span> — Yapay zeka ile üretilen günlük ekonomi
              içeriği.
            </p>
            <p className="max-w-2xl mx-auto text-xs text-zinc-700 leading-relaxed">
              Burada yer alan içerikler yatırım tavsiyesi niteliği taşımaz; genel
              bilgilendirme amaçlıdır. © {new Date().getFullYear()} Esham.
            </p>
          </div>
        </footer>
      </body>
    </html>
  );
}
