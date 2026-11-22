import Link from "next/link";
import { promises as fs } from "fs";
import path from "path";
import {
  ArrowUpRight,
  Wheat,
  Beef,
  TrendingUp,
  TrendingDown,
  Warehouse,
  ArrowRight,
  Database,
} from "lucide-react";
import {
  getAllReports,
  formatDate,
  CATEGORIES,
  type CategorySlug,
} from "@/lib/content";
import { ReportCard } from "@/components/ReportCard";
import { Newsletter } from "@/components/Newsletter";
import { TickerBand } from "@/components/TickerBand";
import { MacroBarometerCard } from "@/components/MacroBarometerCard";
import { ViopBasisCard } from "@/components/ViopBasisCard";
import { MorningCockpit } from "@/components/MorningCockpit";
import { SectorCards, StockLeaderboards } from "@/components/HomeDiscovery";
import { HomeHero } from "@/components/HomeHero";
import { HomeSections, type HomePreset, type HomeSection } from "@/components/HomeSections";
import { loadUniverse } from "@/lib/stocks";

// Kategori etiket renkleri — CSS değişkenleriyle
const catColors: Record<CategorySlug, string> = {
  bist:      "text-sky-400   border-sky-400/30   bg-sky-400/8",
  global:    "text-violet-400 border-violet-400/30 bg-violet-400/8",
  ipo:       "text-emerald-400 border-emerald-400/30 bg-emerald-400/8",
  viop:      "text-orange-400 border-orange-400/30 bg-orange-400/8",
  gundem:    "text-teal-300   border-teal-300/30   bg-teal-300/8",
  kripto:    "text-orange-300 border-orange-300/30 bg-orange-300/8",
  teknoloji: "text-pink-400   border-pink-400/30   bg-pink-400/8",
};

async function loadTuribSnapshot() {
  try {
    const filePath = path.join(process.cwd(), "public", "data", "turib-market.json");
    const raw = await fs.readFile(filePath, "utf-8");
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

async function loadMacroBarometer() {
  try {
    const filePath = path.join(process.cwd(), "public", "data", "macro-barometer.json");
    const raw = await fs.readFile(filePath, "utf-8");
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

async function loadViopBasis() {
  try {
    const filePath = path.join(process.cwd(), "public", "data", "viop-basis.json");
    const raw = await fs.readFile(filePath, "utf-8");
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

async function loadMarketTickerData() {
  try {
    const filePath = path.join(process.cwd(), "public", "data", "market-ticker.json");
    const raw = await fs.readFile(filePath, "utf-8");
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

async function loadEconomicCalendar() {
  try {
    const filePath = path.join(process.cwd(), "public", "data", "economic-calendar.json");
    const raw = await fs.readFile(filePath, "utf-8");
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

async function loadQuantValuation() {
  try {
    const filePath = path.join(process.cwd(), "public", "data", "bist-quant-valuation.json");
    const raw = await fs.readFile(filePath, "utf-8");
    const parsed = JSON.parse(raw);
    // Tarihsiz (updated_at yok) hesaplanmış seviye/oran dosyası yayınlanmaz: kaynak ve tarih zorunlu.
    return parsed && typeof parsed.updated_at === "string" ? parsed : null;
  } catch {
    return null;
  }
}

export default async function Home() {
  const universe = loadUniverse();
  const reports = getAllReports();
  const more = reports.slice(7, 13);
  const featured = reports[0];
  const [
    turibData,
    tickerData,
    macroData,
    viopData,
    calendarData,
    quantData,
  ] = await Promise.all([
    loadTuribSnapshot(),
    loadMarketTickerData(),
    loadMacroBarometer(),
    loadViopBasis(),
    loadEconomicCalendar(),
    loadQuantValuation(),
  ]);

  const trbHub = turibData?.indices?.find((i: any) => i.code === "TRBHUB");
  const bugdaySpot = turibData?.spotCommodities?.find((p: any) =>
    p.name.includes("BUĞDAY")
  );
  // Son iyi değer taşındıysa (stale) özgün veri tarihini göster; "güncel" gibi sunma.
  const staleNote = (o: any) => (o?.stale && o?.asOf ? ` · ${o.asOf} tarihli` : "");
  const NO_DATA = "Veri yok";

  const latestNode = more.length > 0 && (
    <section className="py-20">
      <div className="container mx-auto px-6">
        <div className="flex items-baseline justify-between mb-10">
          <h2 className="text-lg font-display font-semibold text-white">
            Son Yayınlar
          </h2>
          <Link
            href="/arsiv"
            className="text-xs flex items-center gap-1 transition-opacity hover:opacity-70"
            style={{ color: "var(--text-secondary)" }}
          >
            Arşiv <ArrowUpRight className="w-3 h-3" />
          </Link>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
          {more.map((report) => (
            <ReportCard key={report.slug} report={report} />
          ))}
        </div>
      </div>
    </section>
  );

  const radarNode = (macroData || viopData) && (
    <section className="py-12 border-b bg-zinc-950/20" style={{ borderColor: "var(--border)" }}>
      <div className="container mx-auto px-6 space-y-6">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {macroData && <MacroBarometerCard data={macroData} />}
          {viopData && <ViopBasisCard data={viopData} />}
        </div>
      </div>
    </section>
  );

  const commodityNode = (
  <section className="py-12 border-b" style={{ borderColor: "var(--border)", background: "rgba(232, 160, 48, 0.02)" }}>
    <div className="container mx-auto px-6">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-8">
        <div>
          <div className="flex items-center gap-2 mb-2">
            <span
              className="text-xs font-bold tracking-[0.15em] uppercase px-2 py-0.5 rounded border"
              style={{ color: "var(--accent)", borderColor: "var(--accent-dim)", background: "var(--accent-glow)" }}
            >
              <Database className="w-3 h-3 inline mr-1" />
              Piyasa Veri Seti
            </span>
            <span className="text-xs" style={{ color: "var(--text-muted)" }}>
              TÜRİB + LİDAŞ + TMO
            </span>
          </div>
          <h2 className="text-xl md:text-2xl font-display font-bold">
            Tarımsal Emtia & TÜRİB Terminali
          </h2>
        </div>

        <Link
          href="/tarim-emtia"
          className="inline-flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold border transition-all hover:scale-[1.02] self-start md:self-auto"
          style={{
            borderColor: "var(--accent)",
            color: "var(--accent)",
            background: "var(--accent-glow)",
          }}
        >
          Tüm Veri Terminalini İncele <ArrowRight className="w-4 h-4" />
        </Link>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-2 gap-4">
        {/* TRBHUB */}
        <Link
          href="/tarim-emtia"
          className="p-5 rounded-xl border transition-all hover:border-[var(--accent)] group"
          style={{ background: "var(--surface)", borderColor: "var(--border)" }}
        >
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-mono font-bold text-amber-400">TRBHUB</span>
            {trbHub?.changeStr && (
              <span className={`text-xs font-semibold flex items-center gap-0.5 ${(trbHub.changePct ?? 0) >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                {(trbHub.changePct ?? 0) >= 0 ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
                {trbHub.changeStr}
              </span>
            )}
          </div>
          <p className="text-2xl font-bold font-display">{trbHub?.valueStr ?? NO_DATA}</p>
          <p className="text-xs mt-1 text-zinc-400">TÜRİB Hububat Endeksi{staleNote(trbHub)}</p>
        </Link>

        {/* Buğday Spot */}
        <Link
          href="/tarim-emtia"
          className="p-5 rounded-xl border transition-all hover:border-[var(--accent)] group"
          style={{ background: "var(--surface)", borderColor: "var(--border)" }}
        >
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-semibold text-zinc-300">Buğday Ekmeklik</span>
            {bugdaySpot?.changeStr && (
              <span className={`text-xs font-semibold flex items-center gap-0.5 ${(bugdaySpot.changePct ?? 0) >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                {(bugdaySpot.changePct ?? 0) >= 0 ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
                {bugdaySpot.changeStr}
              </span>
            )}
          </div>
          <p className="text-2xl font-bold font-display" style={{ color: "var(--accent)" }}>
            {bugdaySpot?.avgPriceStr ?? NO_DATA}
          </p>
          <p className="text-xs mt-1 text-zinc-400">Lisanslı Depo (ELÜS) Spot{staleNote(bugdaySpot)}</p>
        </Link>
      </div>
    </div>
  </section>
  );

  const categoriesNode = (
  <section className="py-14 border-b" style={{ borderColor: "var(--border)" }}>
    <div className="container mx-auto px-6">
      <div className="flex items-baseline justify-between mb-8">
        <h2 className="text-lg font-display font-semibold text-white">
          Kapsama Alanları
        </h2>
      </div>
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3">
        {(Object.keys(CATEGORIES) as CategorySlug[]).map((slug) => (
          <Link
            key={slug}
            href={`/kategori/${slug}`}
            className="group p-5 rounded-xl border transition-all duration-200 hover:scale-[1.02]"
            style={{
              borderColor: "var(--border)",
              background: "var(--surface)",
            }}
          >
            <div className="mb-3">
              <span className={`text-xs font-bold tracking-wider uppercase px-2 py-0.5 rounded border ${catColors[slug]}`}>
                {slug.toUpperCase()}
              </span>
            </div>
            <p className="text-sm font-semibold leading-snug mb-1 group-hover:opacity-75 transition-opacity">
              {CATEGORIES[slug].label}
            </p>
            <p className="text-xs leading-relaxed line-clamp-2" style={{ color: "var(--text-muted)" }}>
              {CATEGORIES[slug].description}
            </p>
          </Link>
        ))}
      </div>
    </div>
  </section>
  );

  // ── Haberler: kompakt, ilk ekranda (öne çıkan + 6 son rapor) ──
  const newsNode = featured ? (
    <section className="py-5 border-b" style={{ borderColor: "var(--border)" }}>
      <div className="container mx-auto px-6">
        <div className="flex items-center justify-between gap-3 mb-4">
          <div className="flex items-center gap-3 min-w-0">
            <h2 className="text-lg font-display font-semibold text-white whitespace-nowrap">Haberler ve analizler</h2>
            <span className="text-xs whitespace-nowrap hidden sm:inline" style={{ color: "var(--text-muted)" }}>{formatDate(featured.publishedAt)}</span>
          </div>
          <Link href="/arsiv" className="flex items-center gap-1 text-xs hover:opacity-70 whitespace-nowrap" style={{ color: "var(--text-secondary)" }}>
            Tüm raporlar <ArrowUpRight className="w-3 h-3" />
          </Link>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          <Link href={`/rapor/${featured.slug}`} className="group block lg:col-span-5">
            <div className="aspect-[16/9] rounded-xl overflow-hidden mb-3 relative" style={{ background: "var(--surface)" }}>
              <img
                src={featured.image ?? `/cards/default-${featured.category}.png`}
                alt=""
                className="w-full h-full object-cover opacity-80 group-hover:opacity-100 transition-opacity duration-500"
              />
              <div className="absolute inset-0" style={{ background: "linear-gradient(to top, var(--overlay-strong) 0%, transparent 60%)" }} />
              <span className={`absolute bottom-3 left-3 text-xs font-bold tracking-wider uppercase px-2 py-1 rounded border ${catColors[featured.category]}`}>
                {CATEGORIES[featured.category].label}
              </span>
            </div>
            <h2 className="text-xl font-display font-bold leading-snug mb-1.5 group-hover:opacity-75 transition-opacity" style={{ letterSpacing: "-0.02em" }}>
              {featured.title}
            </h2>
            <p className="text-sm leading-relaxed line-clamp-3" style={{ color: "var(--text-secondary)" }}>{featured.summary}</p>
          </Link>

          <ul className="lg:col-span-7 grid sm:grid-cols-2 gap-x-6 content-start">
            {reports.slice(1, 7).map((report) => (
              <li key={report.slug} className="border-b" style={{ borderColor: "var(--border)" }}>
                <Link href={`/rapor/${report.slug}`} className="group flex gap-3 py-3 hover:opacity-75 transition-opacity">
                  <div className="w-16 h-12 rounded-md overflow-hidden flex-shrink-0" style={{ background: "var(--surface-2)" }}>
                    <img src={report.image ?? `/cards/default-${report.category}.png`} alt="" className="w-full h-full object-cover opacity-80" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <span className={`text-xs font-semibold ${catColors[report.category].split(" ")[0]}`}>
                      {CATEGORIES[report.category].label}
                    </span>
                    <h3 className="text-sm font-semibold leading-snug line-clamp-2">{report.title}</h3>
                    <p className="text-xs mt-0.5" style={{ color: "var(--text-muted)" }}>{formatDate(report.publishedAt)}</p>
                  </div>
                </Link>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </section>
  ) : (
    <section className="py-8 border-b" style={{ borderColor: "var(--border)" }}>
      <div className="container mx-auto px-6">
        <div className="rounded-xl border p-10 text-center" style={{ borderColor: "var(--border)", background: "var(--surface)" }}>
          <p className="text-sm" style={{ color: "var(--text-secondary)" }}>Henüz rapor yayınlanmadı.</p>
        </div>
      </div>
    </section>
  );

  // ── Piyasa kokpiti (seans açılışı, VİOP, takvim) ──
  const marketNode = (
    <section className="py-6 border-b" style={{ borderColor: "var(--border)" }}>
      <div className="container mx-auto px-6">
        <MorningCockpit viopData={viopData} tickerData={tickerData} quantData={quantData} calendarData={calendarData} reports={reports} />
      </div>
    </section>
  );

  const stocksNode = universe ? <StockLeaderboards u={universe} /> : null;
  const sectorsNode = universe ? <SectorCards u={universe} /> : null;
  const newsletterNode = <Newsletter />;

  const sections: HomeSection[] = [
    { id: "haberler", label: "Haberler & analizler", description: "Öne çıkan haber ve son 6 rapor", node: newsNode },
    { id: "piyasa", label: "Piyasa kokpiti", description: "Seans açılışı, VİOP, ekonomik takvim", node: marketNode },
    { id: "hisseler", label: "Hisse liderlik tabloları", description: "En düşük F/K, en yüksek ROE, temettü, FD/FAVÖK", node: stocksNode },
    { id: "sektorler", label: "Sektör kartları", description: "Sektörlere göre hisse sayısı, medyan F/K ve ROE", node: sectorsNode },
    { id: "yayinlar", label: "Daha fazla yayın", description: "Haber bloğunun devamı: önceki raporlar", node: latestNode },
    { id: "radar", label: "Kur riski & makro radar", description: "Devalüasyon radarı, makro barometre, VİOP baz", node: radarNode },
    { id: "emtia", label: "Tarım emtia (TÜRİB)", description: "Buğday, mısır, TMO verileri", node: commodityNode },
    { id: "kategoriler", label: "Kapsama alanları", description: "Kategori kısayolları", node: categoriesNode },
    { id: "bulten", label: "E-posta bülteni", description: "Sabah bültenine abone ol", node: newsletterNode },
  ].filter((x) => x.node);

  const ALL_IDS = sections.map((x) => x.id);
  const only = (ids: string[]) => ({ order: [...ids, ...ALL_IDS.filter((x) => !ids.includes(x))], hidden: ALL_IDS.filter((x) => !ids.includes(x)) });
  const DEFAULT_LAYOUT = {
    order: ["haberler", "piyasa", "hisseler", "yayinlar", "radar", "emtia", "sektorler", "kategoriler", "bulten"].filter((x) => ALL_IDS.includes(x)),
    hidden: ["sektorler", "kategoriler"].filter((x) => ALL_IDS.includes(x)),
  };
  const PRESETS: HomePreset[] = [
    { id: "haber", label: "Haber odaklı", hint: "Haberler en üstte (varsayılan)", layout: DEFAULT_LAYOUT },
    {
      id: "piyasa",
      label: "Piyasa odaklı",
      hint: "Kokpit, hisseler ve radar önce",
      layout: {
        order: ["piyasa", "hisseler", "radar", "haberler", "emtia", "sektorler", "yayinlar", "kategoriler", "bulten"].filter((x) => ALL_IDS.includes(x)),
        hidden: ["yayinlar", "kategoriler"].filter((x) => ALL_IDS.includes(x)),
      },
    },
    { id: "minimal", label: "Minimal", hint: "Yalnızca haberler, hisseler ve bülten", layout: only(["haberler", "hisseler", "bulten"]) },
  ];

  return (
    <div className="flex flex-col min-h-screen">
      {/* Canlı fiyat bandı (bot tarafından güncellenen JSON) */}
      <TickerBand />

      {/* İlk ekran: vaat + arama + önizleme + hazır taramalar; bölümler kullanıcının düzeniyle */}
      <HomeHero u={universe} />
      <HomeSections sections={sections} defaults={DEFAULT_LAYOUT} presets={PRESETS} />
    </div>
  );
}
