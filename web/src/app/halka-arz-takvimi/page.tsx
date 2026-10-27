import type { Metadata } from "next";
import Link from "next/link";
import { ArrowUpRight, TrendingUp, AlertCircle, Clock } from "lucide-react";
import { getAllReports, formatDate, type Report } from "@/lib/content";

export const metadata: Metadata = {
  title: "Halka Arz Takvimi",
  description:
    "KAP izahnameleri ve fiyat tespit raporları; yapay zeka destekli iskonto oranı ve risk analizi.",
  openGraph: {
    title: "Halka Arz Takvimi — Esham",
    description:
      "KAP izahnameleri ve fiyat tespit raporları; yapay zeka destekli iskonto oranı ve risk analizi.",
  },
};

// ─── Yardımcılar ─────────────────────────────────────────────────────────────

function extractIpoMeta(report: Report): {
  ticker: string;
  price: string;
  discount: string;
  verdict: string;
} {
  // Yapılandırılmış alan öncelikli (bot `ipo` bloğunu yazar); eski raporlarda
  // bu alan yok → body markdown'inden regex ile sökülür (yedek yol).
  const ipo = report.ipo;
  if (ipo) {
    return {
      ticker: ipo.ticker || "—",
      price: ipo.price ?? "—",
      discount: ipo.discountRate ?? "—",
      verdict: ipo.verdict ?? "",
    };
  }

  // Bot JSON alanları: tags içinde ticker, body içinde fiyat/iskonto
  const ticker = report.tags.find((t) => /^[A-Z]{3,6}$/.test(t)) ?? "—";

  // body'den fiyat satırını yakala: "| Halka Arz Fiyatı | 70,00 TL |" gibi
  const priceMatch = report.body.match(
    /[Hh]alka [Aa]rz [Ff]iyat[ıi]\s*\|?\s*([0-9.,]+\s*TL)/
  );
  const price = priceMatch ? priceMatch[1].trim() : "—";

  // İskonto: "| İskonto | %20 |" veya "%22,5"
  const discountMatch = report.body.match(
    /[Iİ]skonto[^|]*\|?\s*(%[0-9.,]+|[0-9.,]+\s*%)/
  );
  const discount = discountMatch ? discountMatch[1].trim() : "—";

  // Karar/Verdict satırı
  const verdictMatch = report.body.match(
    /\*\*(karar|verdict|değerlendirme)[:\s*]*([^*\n]{5,80})/i
  );
  const verdict = verdictMatch ? verdictMatch[2].trim() : "";

  return { ticker, price, discount, verdict };
}

function discountColor(discount: string): string {
  const num = parseFloat(discount.replace(/[%,]/g, "."));
  if (isNaN(num)) return "text-zinc-400";
  if (num >= 25) return "text-emerald-400";
  if (num >= 15) return "text-amber-400";
  return "text-red-400";
}

// ─── Bileşenler ──────────────────────────────────────────────────────────────

function IpoCard({ report }: { report: Report }) {
  const { ticker, price, discount, verdict } = extractIpoMeta(report);
  const dcColor = discountColor(discount);
  // Takvim için KAP bildirim tarihi esas (yoksa rapor yayın tarihi).
  const eventDate = report.ipo?.disclosureDate ?? report.publishedAt;

  return (
    <Link
      href={`/rapor/${report.slug}`}
      className="group flex flex-col gap-4 rounded-xl border border-zinc-800 bg-zinc-950 p-6
                 hover:border-emerald-800/60 hover:bg-zinc-900/60 transition-all duration-200"
    >
      {/* Üst satır */}
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-2">
            <span className="text-[10px] font-bold tracking-widest uppercase text-emerald-400 border border-emerald-900/50 rounded px-2 py-0.5">
              {ticker}
            </span>
            <span className="text-[10px] text-zinc-500">{formatDate(eventDate)}</span>
          </div>
          <h3 className="text-sm font-semibold leading-snug text-zinc-100 group-hover:text-white transition-colors line-clamp-2">
            {report.title}
          </h3>
        </div>
        <ArrowUpRight className="w-4 h-4 text-zinc-600 group-hover:text-emerald-400 flex-shrink-0 transition-colors" />
      </div>

      {/* Metrik satırı */}
      <div className="flex items-center gap-4 text-xs">
        <div className="flex flex-col">
          <span className="text-zinc-500 mb-0.5">Fiyat</span>
          <span className="font-semibold text-zinc-200">{price}</span>
        </div>
        <div className="w-px h-8 bg-zinc-800" />
        <div className="flex flex-col">
          <span className="text-zinc-500 mb-0.5">İskonto</span>
          <span className={`font-bold ${dcColor}`}>{discount}</span>
        </div>
        {verdict && (
          <>
            <div className="w-px h-8 bg-zinc-800" />
            <div className="flex-1 min-w-0">
              <span className="text-zinc-500 block mb-0.5">Karar</span>
              <span className="text-zinc-300 truncate block">{verdict}</span>
            </div>
          </>
        )}
      </div>

      {/* Özet */}
      {report.summary && (
        <p className="text-xs text-zinc-500 leading-relaxed line-clamp-2">
          {report.summary}
        </p>
      )}
    </Link>
  );
}

function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center py-24 text-center">
      <div className="mb-4 rounded-full bg-zinc-900 p-4 border border-zinc-800">
        <Clock className="h-8 w-8 text-zinc-600" />
      </div>
      <h3 className="text-lg font-semibold text-zinc-300">Henüz halka arz analizi yok</h3>
      <p className="mt-2 text-sm text-zinc-500 max-w-sm">
        KAP&apos;ta yeni bir fiyat tespit raporu yayınlandığında bot otomatik olarak
        analiz üretir ve burada görüntülenir.
      </p>
      <code className="mt-4 text-xs text-amber-400 bg-zinc-900 px-3 py-1.5 rounded border border-zinc-800">
        py -m esham.main news-stream --once
      </code>
    </div>
  );
}

// ─── Sayfa ───────────────────────────────────────────────────────────────────

export default function HalkaArzTakvimiPage() {
  const allReports = getAllReports();
  const ipoReports = allReports.filter((r) => r.category === "ipo");

  // KAP bildirim tarihine göre sırala (yoksa yayın tarihi) — en yeni önce
  const eventTime = (r: Report) =>
    new Date(r.ipo?.disclosureDate ?? r.publishedAt).getTime() || 0;
  const sorted = [...ipoReports].sort((a, b) => eventTime(b) - eventTime(a));

  const recent = sorted.slice(0, 30);

  return (
    <div className="container mx-auto px-6 py-12 max-w-5xl">

      {/* Header */}
      <header className="relative mb-12 overflow-hidden rounded-2xl border border-zinc-800 border-t-2 border-t-emerald-500 bg-zinc-950 px-8 py-12">
        {/* Dekoratif belge SVG */}
        <svg
          className="pointer-events-none absolute right-8 top-6 h-40 w-32 opacity-10"
          viewBox="0 0 128 160"
          aria-hidden="true"
        >
          <path d="M0 0 L96 0 L128 32 L128 160 L0 160 Z" stroke="#34d399" strokeWidth="1.5" fill="none" />
          <path d="M96 0 L96 32 L128 32" stroke="#34d399" strokeWidth="1.5" fill="none" />
          <line x1="16" y1="60" x2="112" y2="60" stroke="#34d399" strokeWidth="1" strokeOpacity="0.6" />
          <line x1="16" y1="80" x2="112" y2="80" stroke="#34d399" strokeWidth="1" strokeOpacity="0.4" />
          <line x1="16" y1="100" x2="80" y2="100" stroke="#34d399" strokeWidth="1" strokeOpacity="0.3" />
        </svg>
        {/* Glow */}
        <div className="pointer-events-none absolute -right-24 -top-24 h-64 w-64 rounded-full blur-3xl bg-emerald-500/15" aria-hidden="true" />

        <div className="relative z-10 max-w-2xl">
          <span className="inline-block mb-4 text-xs font-bold tracking-widest uppercase text-emerald-400">
            Halka Arz & KAP
          </span>
          <h1 className="text-4xl md:text-5xl font-display font-bold tracking-tight text-white mb-4 leading-tight">
            Halka Arz Takvimi
          </h1>
          <p className="text-lg text-zinc-400 leading-relaxed">
            KAP izahnameleri ve fiyat tespit raporları yapay zeka tarafından otomatik analiz edilir.
            İskonto oranları, fon kullanımı ve risk faktörleri özetlenir.
          </p>
        </div>
      </header>

      {/* İstatistik şeridi */}
      {ipoReports.length > 0 && (
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-4 mb-10">
          <div className="rounded-xl border border-zinc-800 bg-zinc-950 p-5">
            <p className="text-xs text-zinc-500 mb-1">Toplam Analiz</p>
            <p className="text-3xl font-bold text-emerald-400">{ipoReports.length}</p>
          </div>
          <div className="rounded-xl border border-zinc-800 bg-zinc-950 p-5">
            <p className="text-xs text-zinc-500 mb-1">Son 30 Gün</p>
            <p className="text-3xl font-bold text-zinc-100">
              {ipoReports.filter((r) => {
                const d = new Date(r.publishedAt);
                const now = new Date();
                return (now.getTime() - d.getTime()) < 30 * 24 * 60 * 60 * 1000;
              }).length}
            </p>
          </div>
          <div className="rounded-xl border border-zinc-800 bg-zinc-950 p-5 col-span-2 sm:col-span-1">
            <div className="flex items-center gap-2 mb-2">
              <AlertCircle className="w-3.5 h-3.5 text-amber-400" />
              <p className="text-xs text-zinc-500">Not</p>
            </div>
            <p className="text-xs text-zinc-400 leading-relaxed">
              Tüm analizler AI tarafından üretilir ve yatırım tavsiyesi niteliği taşımaz.
            </p>
          </div>
        </div>
      )}

      {/* Açıklama — iskonto renkleri */}
      {ipoReports.length > 0 && (
        <div className="flex flex-wrap items-center gap-4 mb-8 px-1">
          <span className="text-xs text-zinc-500">İskonto rengi:</span>
          <span className="flex items-center gap-1.5 text-xs">
            <span className="w-2 h-2 rounded-full bg-emerald-400" />
            <span className="text-zinc-400">&gt;%25 — cazip</span>
          </span>
          <span className="flex items-center gap-1.5 text-xs">
            <span className="w-2 h-2 rounded-full bg-amber-400" />
            <span className="text-zinc-400">%15-25 — orta</span>
          </span>
          <span className="flex items-center gap-1.5 text-xs">
            <span className="w-2 h-2 rounded-full bg-red-400" />
            <span className="text-zinc-400">&lt;%15 — düşük</span>
          </span>
        </div>
      )}

      {/* Kart listesi veya boş durum */}
      {recent.length === 0 ? (
        <EmptyState />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {recent.map((report) => (
            <IpoCard key={report.slug} report={report} />
          ))}
        </div>
      )}

      {/* Tüm IPO raporlarına link */}
      {ipoReports.length > 30 && (
        <div className="mt-10 text-center">
          <Link
            href="/kategori/ipo"
            className="inline-flex items-center gap-2 text-sm text-emerald-400 hover:text-white transition-colors"
          >
            Tüm halka arz analizlerini gör
            <ArrowUpRight className="w-4 h-4" />
          </Link>
        </div>
      )}

      {/* KAP kategorisine link */}
      <div className="mt-12 rounded-xl border border-zinc-800 bg-zinc-900/40 p-6 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <TrendingUp className="w-4 h-4 text-emerald-400" />
            <span className="text-sm font-semibold text-zinc-200">Yeni halka arz bildirimlerini takip et</span>
          </div>
          <p className="text-xs text-zinc-500">
            Bot KAP&apos;ı sürekli tarar; yeni fiyat tespit raporu yayınlandığında otomatik analiz üretir.
          </p>
        </div>
        <Link
          href="/kategori/ipo"
          className="flex-shrink-0 flex items-center gap-2 text-xs font-medium text-emerald-400 border border-emerald-900/50 rounded-lg px-4 py-2 hover:bg-emerald-950/40 transition-colors"
        >
          Tüm IPO raporları <ArrowUpRight className="w-3.5 h-3.5" />
        </Link>
      </div>
    </div>
  );
}
