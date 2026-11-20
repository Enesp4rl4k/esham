"use client";

import React, { useState, useMemo } from "react";
import {
  Fuel,
  Ship,
  Anchor,
  TrendingUp,
  TrendingDown,
  AlertTriangle,
  ShieldCheck,
  Compass,
  ArrowRight,
  Info,
  Sliders,
  DollarSign,
  Activity,
  Layers,
  Droplets,
  Gauge,
} from "lucide-react";
import type { PetrolTankerDataset } from "@/app/tarim-emtia/client";

interface PetrolTankerSectionProps {
  data?: PetrolTankerDataset;
}

// Fallback varsayılan veriler (veri henüz yüklenmediyse bile kesintisiz render)
const DEFAULT_DATA: NonNullable<PetrolTankerDataset> = {
  updatedAt: new Date().toISOString(),
  date: new Date().toISOString().split("T")[0],
  oilBenchmarks: {
    brent: { price: 74.8, priceStr: "$74.80", changePct: 0.45, changeStr: "+0,45%" },
    wti: { price: 71.2, priceStr: "$71.20", changePct: 0.35, changeStr: "+0,35%" },
    brentWtiSpread: 3.6,
    urals: { price: 62.5, discount: 12.3, priceStr: "$62.50", g7Cap: 60.0 },
    crackSpread321: { value: 18.4, valueStr: "$18.40 / varil", interpretation: "Akdeniz Rafineri Kârlılığı" },
  },
  freightIndices: {
    bdti: { value: 1085, change: 24, label: "Baltic Dirty Tanker Index (Ham Petrol)" },
    bcti: { value: 742, change: -8, label: "Baltic Clean Tanker Index (Ürün / Akaryakıt)" },
    vlsfoBunker: { value: 592.0, unit: "$/Ton (Singapur/Rotterdam Ortalama)" },
  },
  rates: [
    {
      ship_class: "VLCC",
      dwt_capacity: "300.000 DWT (~2.000.000 Varil)",
      route_code: "TD3C",
      route_desc: "Ras Tanura -> Ningbo (Arap Körfezi - Çin)",
      daily_rate_usd: 46200.0,
      daily_rate_str: "$46.200 / gün",
      change_usd: 2100.0,
      change_pct: 4.7,
      change_str: "+4,7%",
      worldscale: 56.5,
      fuel_consumption_ton: 48.0,
      cargo_type: "Ham Petrol",
      status: "Yüksek Talep",
      commentary: "Kızıldeniz güvenlik riskleri nedeniyle gemilerin Ümit Burnu rotasyonuna kayması ton-mil talebini ve kiralama ücretlerini artırıyor.",
    },
    {
      ship_class: "Suezmax",
      dwt_capacity: "150.000 DWT (~1.000.000 Varil)",
      route_code: "TD20",
      route_desc: "Batı Afrika -> Rotterdam / Akdeniz",
      daily_rate_usd: 39800.0,
      daily_rate_str: "$39.800 / gün",
      change_usd: 1400.0,
      change_pct: 3.6,
      change_str: "+3,6%",
      worldscale: 82.0,
      fuel_consumption_ton: 38.0,
      cargo_type: "Ham Petrol",
      status: "Dengeli / Pozitif",
      commentary: "Avrupa rafinerilerinin alternatif hafif tatlı ham petrol arayışları Batı Afrika-Avrupa rotasında navlun primini koruyor.",
    },
    {
      ship_class: "Aframax",
      dwt_capacity: "110.000 DWT (~700.000 Varil)",
      route_code: "TD19",
      route_desc: "Ceyhan (BTC Boru Hattı) -> Lavera / Akdeniz",
      daily_rate_usd: 34500.0,
      daily_rate_str: "$34.500 / gün",
      change_usd: -800.0,
      change_pct: -2.3,
      change_str: "-2,3%",
      worldscale: 128.0,
      fuel_consumption_ton: 32.0,
      cargo_type: "Ham Petrol",
      status: "Akdeniz / Ceyhan Canlı",
      commentary: "Bakü-Tiflis-Ceyhan ve Kerkük-Ceyhan akışlarının Doğu Akdeniz piyasasına arzı Aframax tanker talebini diri tutuyor.",
    },
    {
      ship_class: "Clean MR",
      dwt_capacity: "50.000 DWT (~350.000 Varil)",
      route_code: "TC6",
      route_desc: "Cezayir / Skikda -> Akdeniz (Dizel & Nafta)",
      daily_rate_usd: 27900.0,
      daily_rate_str: "$27.900 / gün",
      change_usd: 650.0,
      change_pct: 2.4,
      change_str: "+2,4%",
      worldscale: 165.0,
      fuel_consumption_ton: 24.0,
      cargo_type: "İşlenmiş Akaryakıt",
      status: "Sezonsal Stoklama",
      commentary: "Kış ayları öncesi kalorifer yakıtı, dizel ve sanayi naftası taşımacılığı clean tanker navlunlarını destekliyor.",
    },
  ],
  chokepoints: [
    {
      name: "Türk Boğazları (İstanbul & Çanakkale)",
      flow_mbpd: "~2,8 Mln Varil/Gün",
      wait_time_days: "Kuzey-Güney: 2,8 gün | Güney-Kuzey: 2,1 gün",
      demurrage_usd_day: "~$32.000 / gün",
      security_level: "Normal / Kış Yoğunluğu",
      impact: "Karadeniz (Novorossiysk / CPC Blend) yüklemelerinde bekleme süreleri ham petrol kargolarına varil başı $0.40-$0.60 demurraj maliyeti ekliyor.",
    },
    {
      name: "Kızıldeniz & Babülmendep Boğazı",
      flow_mbpd: "~6,5 Mln Varil/Gün (Normalde)",
      wait_time_days: "Ümit Burnu Geçişi: +12-14 gün",
      demurrage_usd_day: "Savaş Sigortası: %0,75 gemi değeri",
      security_level: "Yüksek Güvenlik Alarmı",
      impact: "Tanker filosunun %65'inden fazlası Süveyş yerine Afrika'yı dolanıyor. Bu durum küresel tanker arzını emerek navlun tabanını yükseltiyor.",
    },
    {
      name: "Hürmüz Boğazı",
      flow_mbpd: "~20,5 Mln Varil/Gün (%21 Küresel Tüketim)",
      wait_time_days: "Kesintisiz Transit",
      demurrage_usd_day: "Risk Primi: Dinamik",
      security_level: "Yüksek Jeopolitik Alarm",
      impact: "Orta Doğu geriliminde Hürmüz'deki herhangi bir aksama küresel Brent petrolünü $100+ seviyesine taşıyabilecek birincil risk faktörü.",
    },
  ],
  bistImpacts: [
    {
      ticker: "TUPRS",
      company: "Tüpraş - Türkiye Petrol Rafinerileri A.Ş.",
      driver: "Rafineri Çatlama Marjı & Ural-Brent Makası",
      impact_level: "Pozitif Çarpan",
      commentary: "Akdeniz kompleksi 3:2:1 crack spread'in $18+ seviyesinde güçlü kalması rafineri brüt kârlılığını desteklerken, Ceyhan ve bölgesel Aframax navlun maliyetleri kontrollü seyrediyor.",
    },
    {
      ticker: "DITAS",
      company: "Ditaş Denizcilik A.Ş.",
      driver: "Ham Petrol & Akaryakıt Tanker Kiralama",
      impact_level: "Yüksek Pozitif",
      commentary: "VLCC ve Aframax spot tanker kiralama ücretlerindeki her %10'luk artış, kontrat yenilemelerinde Ditaş'ın time-charter navlun gelirlerine ve FAVÖK marjına doğrudan çarpan etkisi yapar.",
    },
    {
      ticker: "PETKM",
      company: "Petkim Petrokimya Holding A.Ş.",
      driver: "Nafta Hammadde Taşımacılığı (Clean MR)",
      impact_level: "Nötr / Maliyet Takibi",
      commentary: "Clean tanker navlunlarının ılımlı seyri Akdeniz nafta tedarik maliyetlerini dengeliyor. Etilen-nafta marjı temel kârlılık çıpası olmaya devam ediyor.",
    },
  ],
};

export function PetrolTankerSection({ data }: PetrolTankerSectionProps) {
  const dataset = data && data.rates && data.rates.length > 0 ? data : DEFAULT_DATA;
  const oil = dataset.oilBenchmarks || DEFAULT_DATA.oilBenchmarks!;
  const freight = dataset.freightIndices || DEFAULT_DATA.freightIndices!;
  const rates = dataset.rates || DEFAULT_DATA.rates!;
  const chokepoints = dataset.chokepoints || DEFAULT_DATA.chokepoints!;
  const bistImpacts = dataset.bistImpacts || DEFAULT_DATA.bistImpacts!;

  // ── İnteraktif Sefer & Navlun Hesaplayıcı Durumu ──
  const [selectedClass, setSelectedClass] = useState<string>("Aframax");
  const [voyageDays, setVoyageDays] = useState<number>(20);
  const [bunkerPrice, setBunkerPrice] = useState<number>(freight.vlsfoBunker?.value || 592);

  const selectedRate = useMemo(() => {
    return rates.find((r) => r.ship_class === selectedClass) || rates[0];
  }, [rates, selectedClass]);

  const calculation = useMemo(() => {
    const dailyRate = selectedRate.daily_rate_usd;
    const charterTotal = dailyRate * voyageDays;
    const fuelCost = voyageDays * selectedRate.fuel_consumption_ton * bunkerPrice;
    const portAndCanalFees = selectedClass === "VLCC" ? 220000 : selectedClass === "Suezmax" ? 160000 : 95000;
    const totalVoyageCost = charterTotal + fuelCost + portAndCanalFees;

    // Varil kapasitesi
    const barrels =
      selectedClass === "VLCC"
        ? 2000000
        : selectedClass === "Suezmax"
        ? 1000000
        : selectedClass === "Aframax"
        ? 700000
        : 350000;

    const costPerBarrel = totalVoyageCost / barrels;

    return {
      charterTotal,
      fuelCost,
      portAndCanalFees,
      totalVoyageCost,
      barrels,
      costPerBarrel,
    };
  }, [selectedRate, voyageDays, bunkerPrice, selectedClass]);

  return (
    <section className="space-y-8 animate-in fade-in duration-300">
      {/* ── Başlık & Kimlik Banner ── */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 p-6 rounded-2xl border bg-gradient-to-br from-zinc-900/90 via-zinc-950 to-zinc-900/40 border-zinc-800 shadow-xl">
        <div>
          <div className="flex items-center gap-2 mb-2">
            <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-mono uppercase tracking-wider font-semibold bg-amber-500/10 text-amber-400 border border-amber-500/20">
              <span className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-pulse" />
              KÜRESEL ENERJİ & TANKER NAVLUN TERMİNALİ
            </span>
            <span className="text-xs text-zinc-400 font-mono">
              TCE & Baltic Exchange Benchmark
            </span>
          </div>
          <h2 className="text-xl md:text-3xl font-display font-bold text-white tracking-tight flex items-center gap-2.5">
            <Fuel className="w-6 h-6 text-amber-400" />
            Petrol Piyasası, Tanker Kiralama & Navlun Oranları
          </h2>
          <p className="text-xs md:text-sm text-zinc-400 mt-1 max-w-3xl">
            Ham petrol göstergeleri (Brent, WTI, Urals, Crack Spread), VLCC/Suezmax/Aframax spot tanker kiralama ücretleri (TCE), Türk Boğazları demurraj süreleri ve BIST rafineri-denizcilik etkisi.
          </p>
        </div>

        <div className="flex items-center gap-3 shrink-0">
          <div className="px-4 py-2.5 rounded-xl bg-zinc-900/80 border border-zinc-800 text-right">
            <span className="text-xs uppercase font-mono tracking-wider text-zinc-400 block">
              Gemi Yakıtı (VLSFO)
            </span>
            <span className="text-base font-bold text-zinc-200 font-mono">
              ${bunkerPrice.toFixed(0)} <span className="text-xs text-zinc-400 font-normal">/ton</span>
            </span>
          </div>
        </div>
      </div>

      {/* ── 1. Ham Petrol & Rafineri Çatlama Marjı KPI Grid ── */}
      <div>
        <div className="flex items-center gap-2 mb-3">
          <Droplets className="w-4 h-4 text-cyan-400" />
          <h3 className="text-xs uppercase font-mono font-bold tracking-wider text-zinc-400">
            Ham Petrol Göstergeleri & Rafineri Marjı
          </h3>
        </div>

        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 md:gap-4">
          {/* Brent */}
          <div className="p-4 rounded-xl border bg-zinc-950/60 border-zinc-800/80 hover:border-zinc-700 transition-all">
            <div className="flex items-center justify-between text-xs text-zinc-400 font-mono mb-1">
              <span>BRENT SPOT</span>
              <span className={oil.brent?.changePct && oil.brent.changePct >= 0 ? "text-emerald-400" : "text-rose-400"}>
                {oil.brent?.changeStr || "+0,45%"}
              </span>
            </div>
            <div className="text-xl md:text-2xl font-bold font-mono text-white">
              {oil.brent?.priceStr || "$74.80"}
            </div>
            <div className="text-xs text-zinc-400 mt-1">
              Küresel gösterge ham petrol
            </div>
          </div>

          {/* WTI */}
          <div className="p-4 rounded-xl border bg-zinc-950/60 border-zinc-800/80 hover:border-zinc-700 transition-all">
            <div className="flex items-center justify-between text-xs text-zinc-400 font-mono mb-1">
              <span>WTI HAM PETROL</span>
              <span className={oil.wti?.changePct && oil.wti.changePct >= 0 ? "text-emerald-400" : "text-rose-400"}>
                {oil.wti?.changeStr || "+0,35%"}
              </span>
            </div>
            <div className="text-xl md:text-2xl font-bold font-mono text-white">
              {oil.wti?.priceStr || "$71.20"}
            </div>
            <div className="text-xs text-zinc-400 mt-1">
              Brent-WTI Makası: <span className="font-mono text-zinc-300">${oil.brentWtiSpread?.toFixed(2) || "3.60"}</span>
            </div>
          </div>

          {/* Urals */}
          <div className="p-4 rounded-xl border bg-zinc-950/60 border-zinc-800/80 hover:border-zinc-700 transition-all">
            <div className="flex items-center justify-between text-xs text-zinc-400 font-mono mb-1">
              <span>URALS (RUSYA)</span>
              <span className="text-amber-400">G7 Tavanı: $60</span>
            </div>
            <div className="text-xl md:text-2xl font-bold font-mono text-white">
              {oil.urals?.priceStr || "$62.50"}
            </div>
            <div className="text-xs text-zinc-400 mt-1">
              Brent İskontosu: <span className="font-mono text-rose-400">-${oil.urals?.discount?.toFixed(2) || "12.30"}</span>
            </div>
          </div>

          {/* Crack Spread 3:2:1 */}
          <div className="p-4 rounded-xl border bg-zinc-950/60 border-zinc-800/80 hover:border-zinc-700 transition-all">
            <div className="flex items-center justify-between text-xs text-zinc-400 font-mono mb-1">
              <span>3:2:1 CRACK SPREAD</span>
              <span className="text-emerald-400 font-semibold">Tüpraş Marjı</span>
            </div>
            <div className="text-xl md:text-2xl font-bold font-mono text-emerald-400">
              {oil.crackSpread321?.valueStr || "$18.40 / varil"}
            </div>
            <div className="text-xs text-zinc-400 mt-1">
              Akdeniz kompleksi rafineri brüt kârı
            </div>
          </div>
        </div>
      </div>

      {/* ── 2. Baltic Navlun Endeksleri ── */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* BDTI */}
        <div className="p-4 rounded-xl border bg-zinc-900/40 border-zinc-800 flex items-center justify-between">
          <div>
            <div className="flex items-center gap-2">
              <Ship className="w-4 h-4 text-amber-400" />
              <span className="text-xs font-mono uppercase tracking-wider text-zinc-400 font-semibold">
                BDTI (Baltic Dirty Tanker Index)
              </span>
            </div>
            <p className="text-xs text-zinc-400 mt-0.5">
              Ham petrol tanker taşıma maliyeti küresel endeksi
            </p>
          </div>
          <div className="text-right">
            <span className="text-2xl font-bold font-mono text-white">
              {freight.bdti?.value || 1085}
            </span>
            <span className="text-xs text-emerald-400 block font-mono">
              +{freight.bdti?.change || 24} puan
            </span>
          </div>
        </div>

        {/* BCTI */}
        <div className="p-4 rounded-xl border bg-zinc-900/40 border-zinc-800 flex items-center justify-between">
          <div>
            <div className="flex items-center gap-2">
              <Anchor className="w-4 h-4 text-cyan-400" />
              <span className="text-xs font-mono uppercase tracking-wider text-zinc-400 font-semibold">
                BCTI (Baltic Clean Tanker Index)
              </span>
            </div>
            <p className="text-xs text-zinc-400 mt-0.5">
              İşlenmiş akaryakıt & nafta ürün tankeri navlun endeksi
            </p>
          </div>
          <div className="text-right">
            <span className="text-2xl font-bold font-mono text-white">
              {freight.bcti?.value || 742}
            </span>
            <span className="text-xs text-rose-400 block font-mono">
              {freight.bcti?.change || -8} puan
            </span>
          </div>
        </div>
      </div>

      {/* ── 3. Tanker Sınıfları & Günlük Kiralama Ücretleri Tablosu ── */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <Ship className="w-4 h-4 text-amber-400" />
            <h3 className="text-xs uppercase font-mono font-bold tracking-wider text-zinc-400">
              Tanker Sınıfları Spot Kiralama Ücretleri (TCE $/Gün)
            </h3>
          </div>
          <span className="text-xs font-mono text-zinc-400">
            Zaman Esaslı Kiralama Eşdeğeri (Time Charter Equivalent)
          </span>
        </div>

        <div className="rounded-2xl border border-zinc-800 bg-zinc-950/60 overflow-hidden shadow-lg">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs md:text-sm">
              <thead>
                <tr className="border-b text-xs uppercase tracking-wider font-mono text-zinc-400 bg-zinc-900/40 border-zinc-800">
                  <th className="py-3 px-4">Gemi Sınıfı & Kapasite</th>
                  <th className="py-3 px-4">Benchmark Rota</th>
                  <th className="py-3 px-4">Günlük Kiralama (TCE)</th>
                  <th className="py-3 px-4">Günlük Değişim</th>
                  <th className="py-3 px-4">Worldscale</th>
                  <th className="py-3 px-4">Yakıt / Gün</th>
                  <th className="py-3 px-4 text-right">Piyasa Görünümü</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-800/60">
                {rates.map((rate) => {
                  const isPositive = rate.change_pct >= 0;
                  return (
                    <tr
                      key={rate.ship_class}
                      className="hover:bg-zinc-900/30 transition-colors"
                    >
                      <td className="py-3.5 px-4">
                        <div className="font-bold text-zinc-200 text-sm flex items-center gap-1.5">
                          <span>{rate.ship_class}</span>
                          <span className="text-xs font-mono font-normal px-1.5 py-0.5 rounded bg-zinc-900 border border-zinc-800 text-zinc-400">
                            {rate.cargo_type}
                          </span>
                        </div>
                        <div className="text-xs text-zinc-400 font-mono mt-0.5">
                          {rate.dwt_capacity}
                        </div>
                      </td>
                      <td className="py-3.5 px-4 font-mono text-xs text-zinc-300">
                        <span className="px-1.5 py-0.5 rounded bg-zinc-900 text-amber-400 font-semibold mr-1.5">
                          {rate.route_code}
                        </span>
                        {rate.route_desc}
                      </td>
                      <td className="py-3.5 px-4 font-mono font-bold text-sm text-white">
                        {rate.daily_rate_str}
                      </td>
                      <td className="py-3.5 px-4 font-mono text-xs">
                        <span
                          className={`inline-flex items-center gap-0.5 font-semibold ${
                            isPositive ? "text-emerald-400" : "text-rose-400"
                          }`}
                        >
                          {isPositive ? (
                            <TrendingUp className="w-3.5 h-3.5" />
                          ) : (
                            <TrendingDown className="w-3.5 h-3.5" />
                          )}
                          {rate.change_str}
                        </span>
                      </td>
                      <td className="py-3.5 px-4 font-mono text-xs text-zinc-300">
                        WS {rate.worldscale.toFixed(1)}
                      </td>
                      <td className="py-3.5 px-4 font-mono text-xs text-zinc-400">
                        {rate.fuel_consumption_ton} Ton
                      </td>
                      <td className="py-3.5 px-4 text-right">
                        <span className="inline-block px-2.5 py-1 rounded-full text-xs font-semibold tracking-wide bg-zinc-900 border border-zinc-700/60 text-zinc-200">
                          {rate.status}
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          <div className="p-4 bg-zinc-900/30 border-t border-zinc-800/80 text-xs text-zinc-400 space-y-1">
            <p>
              * <strong>Worldscale (WS):</strong> Denizcilikte standartlaştırılmış navlun puan sistemidir; 100 baz puan üzerinden rotanın teorik başabaş maliyetini temsil eder.
            </p>
            <p>
              * <strong>TCE (Time Charter Equivalent):</strong> Toplam sefer gelirinden yakıt ve liman masrafları düşüldükten sonra gemi sahibinin net günlük kazancıdır.
            </p>
          </div>
        </div>
      </div>

      {/* ── 4. İnteraktif Tanker Sefer Maliyeti & Varil Başı Taşıma Hesaplayıcı ── */}
      <div className="p-6 rounded-2xl border bg-gradient-to-br from-zinc-900/60 via-zinc-950 to-zinc-900/30 border-zinc-800 shadow-xl">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-6 pb-4 border-b border-zinc-800">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <Sliders className="w-4 h-4 text-amber-400" />
              <h3 className="text-base font-bold text-white">
                İnteraktif Sefer & Varil Başı Taşıma Maliyeti Simülatörü
              </h3>
            </div>
            <p className="text-xs text-zinc-400">
              Gemi sınıfı, sefer süresi ve yakıt parametrelerini değiştirerek kargonun varil başına düşen net navlun maliyetini hesaplayın.
            </p>
          </div>

          <div className="flex items-center gap-2">
            {["VLCC", "Suezmax", "Aframax", "Clean MR"].map((cls) => (
              <button
                key={cls}
                onClick={() => setSelectedClass(cls)}
                className={`px-3 py-1.5 rounded-lg text-xs font-semibold font-mono transition-all cursor-pointer ${
                  selectedClass === cls
                    ? "bg-amber-400 text-zinc-950 shadow-md shadow-amber-400/20"
                    : "bg-zinc-900 text-zinc-400 hover:text-white border border-zinc-800"
                }`}
              >
                {cls}
              </button>
            ))}
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-center">
          {/* Kontroller */}
          <div className="lg:col-span-5 space-y-4">
            <div>
              <div className="flex justify-between items-center text-xs font-mono mb-1.5">
                <span className="text-zinc-400">Sefer Süresi (Gün):</span>
                <span className="text-amber-400 font-bold">{voyageDays} Gün</span>
              </div>
              <input
                type="range"
                min="5"
                max="60"
                step="1"
                value={voyageDays}
                onChange={(e) => setVoyageDays(parseInt(e.target.value))}
                className="w-full accent-amber-400 cursor-pointer h-1.5 bg-zinc-800 rounded-lg"
              />
              <div className="flex justify-between text-xs text-zinc-400 font-mono mt-1">
                <span>5 Gün (Kısa Akdeniz)</span>
                <span>25 Gün (Süveyş)</span>
                <span>50+ Gün (Ümit Burnu)</span>
              </div>
            </div>

            <div>
              <div className="flex justify-between items-center text-xs font-mono mb-1.5">
                <span className="text-zinc-400">VLSFO Bunker Yakıt Fiyatı ($/Ton):</span>
                <span className="text-cyan-400 font-bold">${bunkerPrice}</span>
              </div>
              <input
                type="range"
                min="450"
                max="850"
                step="10"
                value={bunkerPrice}
                onChange={(e) => setBunkerPrice(parseInt(e.target.value))}
                className="w-full accent-cyan-400 cursor-pointer h-1.5 bg-zinc-800 rounded-lg"
              />
            </div>

            <div className="p-3 rounded-xl bg-zinc-900/60 border border-zinc-800/80 text-xs text-zinc-400 space-y-1">
              <div className="flex justify-between">
                <span>Seçili Sınıf Günlük TCE:</span>
                <span className="font-mono text-zinc-200">${selectedRate.daily_rate_usd.toLocaleString("tr-TR")}</span>
              </div>
              <div className="flex justify-between">
                <span>Günlük Yakıt Tüketimi:</span>
                <span className="font-mono text-zinc-200">{selectedRate.fuel_consumption_ton} Ton VLSFO</span>
              </div>
              <div className="flex justify-between">
                <span>Toplam Kargo Kapasitesi:</span>
                <span className="font-mono text-zinc-200">{calculation.barrels.toLocaleString("tr-TR")} Varil</span>
              </div>
            </div>
          </div>

          {/* Sonuç Kartı */}
          <div className="lg:col-span-7 grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="p-5 rounded-2xl bg-zinc-950/80 border border-amber-500/20 shadow-lg relative overflow-hidden">
              <span className="text-xs uppercase font-mono tracking-wider text-zinc-400 block mb-1">
                VARİL BAŞINA TAŞIMA MALİYETİ
              </span>
              <div className="text-3xl font-bold font-mono text-amber-400 tracking-tight">
                ${calculation.costPerBarrel.toFixed(2)}
                <span className="text-xs font-normal text-zinc-400 ml-1">/ varil</span>
              </div>
              <p className="text-xs text-zinc-400 mt-2 leading-relaxed">
                Tüpraş veya rafinerinin ham petrol maliyetine eklenen toplam deniz navlun primi.
              </p>
            </div>

            <div className="p-5 rounded-2xl bg-zinc-950/80 border border-zinc-800 shadow-lg space-y-2.5">
              <span className="text-xs uppercase font-mono tracking-wider text-zinc-400 block">
                TOPLAM SEFER GİDERLERİ
              </span>
              <div className="text-2xl font-bold font-mono text-white">
                ${calculation.totalVoyageCost.toLocaleString("tr-TR")}
              </div>
              <div className="space-y-1 text-xs font-mono text-zinc-400 pt-1 border-t border-zinc-800">
                <div className="flex justify-between">
                  <span>Tanker Kirası:</span>
                  <span className="text-zinc-200">${calculation.charterTotal.toLocaleString("tr-TR")}</span>
                </div>
                <div className="flex justify-between">
                  <span>Bunker Yakıt:</span>
                  <span className="text-zinc-200">${calculation.fuelCost.toLocaleString("tr-TR")}</span>
                </div>
                <div className="flex justify-between">
                  <span>Boğaz & Liman:</span>
                  <span className="text-zinc-200">${calculation.portAndCanalFees.toLocaleString("tr-TR")}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* ── 5. Kritik Boğazlar, Demurraj & Jeopolitik Koridor Radarı ── */}
      <div>
        <div className="flex items-center gap-2 mb-3">
          <Compass className="w-4 h-4 text-amber-400" />
          <h3 className="text-xs uppercase font-mono font-bold tracking-wider text-zinc-400">
            Kritik Deniz Boğazları & Transit Durumu
          </h3>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {chokepoints.map((cp) => (
            <div
              key={cp.name}
              className="p-5 rounded-2xl border bg-zinc-950/60 border-zinc-800 hover:border-zinc-700 transition-all flex flex-col justify-between"
            >
              <div>
                <div className="flex items-center justify-between mb-2">
                  <h4 className="text-sm font-bold text-zinc-200">{cp.name}</h4>
                  <span className="px-2 py-0.5 rounded text-xs font-mono font-semibold bg-zinc-900 border border-zinc-800 text-amber-400">
                    {cp.security_level}
                  </span>
                </div>

                <div className="space-y-1.5 text-xs font-mono text-zinc-400 mb-3">
                  <div className="flex justify-between">
                    <span className="text-zinc-400">Petrol Akışı:</span>
                    <span className="text-zinc-200 font-semibold">{cp.flow_mbpd}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-zinc-400">Bekleme / Rota:</span>
                    <span className="text-zinc-200">{cp.wait_time_days}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-zinc-400">Demurraj / Risk:</span>
                    <span className="text-rose-400 font-semibold">{cp.demurrage_usd_day}</span>
                  </div>
                </div>
              </div>

              <p className="text-xs text-zinc-400 bg-zinc-900/40 p-3 rounded-xl border border-zinc-800/80 leading-relaxed">
                {cp.impact}
              </p>
            </div>
          ))}
        </div>
      </div>

      {/* ── 6. BIST Enerji & Denizcilik Hisseleri Etki Analizi ── */}
      <div>
        <div className="flex items-center gap-2 mb-3">
          <Activity className="w-4 h-4 text-emerald-400" />
          <h3 className="text-xs uppercase font-mono font-bold tracking-wider text-zinc-400">
            BIST Şirketleri Navlun & Petrol Duyarlılık Matrisi
          </h3>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {bistImpacts.map((bist) => (
            <div
              key={bist.ticker}
              className="p-5 rounded-2xl border bg-zinc-950/60 border-zinc-800 hover:border-zinc-700 transition-all flex flex-col justify-between"
            >
              <div>
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <span className="px-2 py-1 rounded-lg bg-zinc-900 border border-zinc-800 font-mono font-bold text-sm text-white">
                      ${bist.ticker}
                    </span>
                    <span className="text-xs text-zinc-400 font-medium truncate max-w-[160px]">
                      {bist.company.split("-")[0]}
                    </span>
                  </div>
                  <span className="px-2 py-0.5 rounded text-xs font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                    {bist.impact_level}
                  </span>
                </div>

                <div className="text-xs font-mono text-zinc-400 mb-2">
                  <span className="text-zinc-400">Kritik İtici Güç: </span>
                  <span className="text-zinc-300 font-semibold">{bist.driver}</span>
                </div>
              </div>

              <p className="text-xs text-zinc-400 bg-zinc-900/40 p-3 rounded-xl border border-zinc-800/80 leading-relaxed mt-2">
                {bist.commentary}
              </p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
