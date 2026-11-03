import React from "react";
import Link from "next/link";
import { promises as fs } from "fs";
import path from "path";
import {
  ArrowLeft,
  Gauge,
  ShieldCheck,
  Flame,
  AlertTriangle,
  History,
  BookOpen,
  Info,
  Scale,
  Landmark,
  Percent,
} from "lucide-react";
import { DevaluationRadarCard, DevaluationRadarData } from "@/components/DevaluationRadarCard";

export const metadata = {
  title: "TRY Kur Şoku & Devalüasyon Basınç Radarı | Esham Finansal İstihbarat",
  description:
    "TCMB swap hariç net rezerv yanma hızı, Kapalıçarşı ikili kur makası, VİOP ima edilen faiz oranı ve 5Y CDS ile Türkiye kur riski erken uyarı sistemi.",
};

async function loadDevaluationRadarData(): Promise<DevaluationRadarData | null> {
  try {
    const filePath = path.join(process.cwd(), "public", "data", "devaluation-radar.json");
    const raw = await fs.readFile(filePath, "utf-8");
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

export default async function DevaluationRadarPage() {
  const radarData = await loadDevaluationRadarData();

  if (!radarData) {
    return (
      <div className="container mx-auto px-6 py-20 text-center">
        <h1 className="text-xl font-bold text-white mb-2">Kur Radarı Verisi Yüklenemedi</h1>
        <p className="text-zinc-400 text-sm">Veri dosyası hazırlanıyor, lütfen sayfayı yenileyiniz.</p>
      </div>
    );
  }

  return (
    <div className="container mx-auto px-6 py-10 max-w-6xl">
      {/* Üst Navigasyon & Başlık */}
      <div className="flex items-center gap-2 mb-6">
        <Link
          href="/"
          className="text-xs text-zinc-400 hover:text-white inline-flex items-center gap-1 transition-colors"
        >
          <ArrowLeft className="w-3.5 h-3.5" /> Ana Sayfa
        </Link>
        <span className="text-zinc-600">/</span>
        <span className="text-xs text-zinc-400">Piyasalar</span>
        <span className="text-zinc-600">/</span>
        <span className="text-xs text-amber-400 font-medium">Kur Şoku & Devalüasyon Radarı</span>
      </div>

      <div className="mb-8">
        <div className="flex flex-wrap items-center gap-2.5 mb-2">
          <span className="p-2 rounded-xl bg-amber-500/10 text-amber-400 border border-amber-500/20">
            <Gauge className="w-6 h-6" />
          </span>
          <h1 className="text-2xl md:text-3xl font-black text-white tracking-tight">
            TRY Kur Şoku & Devalüasyon Basınç Radarı
          </h1>
          <span className="text-[11px] font-mono px-2.5 py-1 rounded bg-zinc-900 border border-zinc-800 text-zinc-400">
            Hazine Erken Uyarı Sistemi
          </span>
        </div>
        <p className="text-zinc-400 text-sm max-w-3xl leading-relaxed">
          Türkiye döviz piyasasında ani kur sıçramaları (devalüasyon) öncesinde tezgahüstü piyasada,
          vadeli türevlerde ve TCMB bilançosunda oluşan öncü sinyallerin (leading indicators)
          kurumsal düzeyde nicel takibi ve risk modellemesi.
        </p>
      </div>

      {/* Ana Radar Kartı */}
      <div className="mb-10">
        <DevaluationRadarCard data={radarData} />
      </div>

      {/* Tarihsel Kriz Stres Kıyaslamaları */}
      <section className="mb-12">
        <div className="flex items-center gap-2 mb-4">
          <History className="w-5 h-5 text-amber-400" />
          <h2 className="text-lg font-bold text-white tracking-tight">
            Tarihsel Kriz Kıyaslamaları & Stres Testi Backtest
          </h2>
        </div>
        <p className="text-xs text-zinc-400 mb-5">
          Aşağıdaki matris, Türkiye&apos;nin geçmişteki büyük kur atağı ve devalüasyon dönemlerindeki
          gösterge seviyeleri ile güncel piyasa durumunu aynı analitik model üzerinden kıyaslar.
        </p>

        <div className="overflow-x-auto rounded-xl border border-zinc-800 bg-zinc-950/80">
          <table className="w-full text-left text-xs font-mono">
            <thead className="bg-zinc-900/90 text-zinc-400 border-b border-zinc-800">
              <tr>
                <th className="py-3 px-4">Dönem & Kriz Adı</th>
                <th className="py-3 px-4">Kur Basınç Skoru</th>
                <th className="py-3 px-4">Dolar / TL</th>
                <th className="py-3 px-4">Kapalıçarşı Makası</th>
                <th className="py-3 px-4">Swap Hariç Rezerv</th>
                <th className="py-3 px-4">Piyasa Sonucu</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-800/60 text-zinc-300">
              {radarData.historical_benchmarks?.map((bm, idx) => (
                <tr
                  key={idx}
                  className={`hover:bg-zinc-900/50 transition-colors ${
                    bm.period === "Güncel Durum" ? "bg-amber-500/5 font-semibold" : ""
                  }`}
                >
                  <td className="py-3.5 px-4">
                    <span className="font-bold text-white block">{bm.period}</span>
                    <span className="text-[11px] text-zinc-400">{bm.label}</span>
                  </td>
                  <td className="py-3.5 px-4">
                    <span
                      className={`px-2 py-0.5 rounded text-[11px] font-bold ${
                        bm.score >= 80
                          ? "bg-rose-500/20 text-rose-400 border border-rose-500/30"
                          : bm.score >= 50
                          ? "bg-amber-500/20 text-amber-400 border border-amber-500/30"
                          : "bg-emerald-500/20 text-emerald-400 border border-emerald-500/30"
                      }`}
                    >
                      {bm.score} / 100
                    </span>
                  </td>
                  <td className="py-3.5 px-4 text-white">{bm.usd_try}</td>
                  <td className="py-3.5 px-4">
                    <span
                      className={
                        parseFloat(bm.spread_bazaar.replace("%", "")) > 1.5
                          ? "text-rose-400 font-bold"
                          : "text-emerald-400"
                      }
                    >
                      {bm.spread_bazaar}
                    </span>
                  </td>
                  <td className="py-3.5 px-4">
                    <span
                      className={
                        bm.net_reserves.includes("-") ? "text-rose-400" : "text-emerald-400"
                      }
                    >
                      {bm.net_reserves}
                    </span>
                  </td>
                  <td className="py-3.5 px-4 text-[11px] text-zinc-300">{bm.result}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {/* Kurumsal Hazine & Risk Yönetimi Rehberi */}
      <section className="mb-12">
        <div className="flex items-center gap-2 mb-4">
          <BookOpen className="w-5 h-5 text-indigo-400" />
          <h2 className="text-lg font-bold text-white tracking-tight">
            Kurumsal Hazine Masası ve Risk Yönetimi Rehberi
          </h2>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="p-5 rounded-xl border border-zinc-800 bg-zinc-950/70">
            <h3 className="text-sm font-bold text-white mb-2 flex items-center gap-1.5">
              <Scale className="w-4 h-4 text-amber-400" />
              1. Döviz Açık Pozisyonu Olan Şirketler (FX Hedging)
            </h3>
            <p className="text-xs text-zinc-300 leading-relaxed mb-3">
              VİOP Dolar/TL vadeli sözleşmelerinde ima edilen yıllık faiz (%28.9), banka TL kredi faizlerinin
              (%50-55) oldukça altındadır. Bu durum, döviz borcu veya hammadde ithalat yükümlülüğü bulunan
              şirketler için VİOP üzerinden kur riskini sabitlemeyi (long hedge) son derece avantajlı kılmaktadır.
            </p>
            <div className="text-[11px] font-mono text-zinc-400 bg-zinc-900/80 p-2.5 rounded border border-zinc-800">
              Strateji: Kredili spot döviz almak yerine VİOP USD/TRY vadeli kontratı ile forward sabitleme.
            </div>
          </div>

          <div className="p-5 rounded-xl border border-zinc-800 bg-zinc-950/70">
            <h3 className="text-sm font-bold text-white mb-2 flex items-center gap-1.5">
              <Landmark className="w-4 h-4 text-emerald-400" />
              2. Rezerv Eşiği ve Devalüasyon Tetikleyicisi
            </h3>
            <p className="text-xs text-zinc-300 leading-relaxed mb-3">
              TCMB&apos;nin swap hariç net rezervlerinin pozitif bölgede (+$30 Milyar+) kalması, spekülatif
              döviz ataklarına karşı birinci savunma kalkanıdır. Eğer rezervlerde haftalık $4-5 Milyar üzeri
              hızlı bir erime (burn rate) başlarsa, model riski otomatik olarak &quot;Yüksek Basınç&quot; seviyesine çeker.
            </p>
            <div className="text-[11px] font-mono text-zinc-400 bg-zinc-900/80 p-2.5 rounded border border-zinc-800">
              Kritik Eşik: Swap hariç rezervlerin $0 seviyesinin altına inmesi ve Kapalıçarşı makasının %1.5&apos;i aşması.
            </div>
          </div>
        </div>
      </section>

      {/* Model Metodolojisi ve Formüller */}
      <section className="mb-12 p-6 rounded-2xl border border-zinc-800 bg-zinc-900/40">
        <h3 className="text-sm font-bold text-white mb-3 flex items-center gap-2">
          <Info className="w-4 h-4 text-sky-400" />
          Endeks Metodolojisi ve Ağırlık Dağılımı
        </h3>
        <p className="text-xs text-zinc-400 leading-relaxed mb-4">
          TRY Kur Basınç Endeksi (0-100), aşağıdaki 5 bağımsız öncü makro göstergenin normalize edilmiş
          risk skorlarının ağırlıklı toplamıyla hesaplanır:
        </p>
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-5 gap-3 text-xs font-mono">
          <div className="p-3 rounded-lg bg-zinc-950/80 border border-zinc-800">
            <span className="text-[10px] text-zinc-500 block">Ağırlık: %25</span>
            <span className="font-bold text-white">VİOP FX Spread</span>
            <span className="text-[10px] text-zinc-400 block mt-1">
              İma Edilen Faiz vs TCMB Politika
            </span>
          </div>
          <div className="p-3 rounded-lg bg-zinc-950/80 border border-zinc-800">
            <span className="text-[10px] text-zinc-500 block">Ağırlık: %25</span>
            <span className="font-bold text-white">Rezerv Yanma Hızı</span>
            <span className="text-[10px] text-zinc-400 block mt-1">
              Swap Hariç Rezerv & &Delta; Rezerv
            </span>
          </div>
          <div className="p-3 rounded-lg bg-zinc-950/80 border border-zinc-800">
            <span className="text-[10px] text-zinc-500 block">Ağırlık: %20</span>
            <span className="font-bold text-white">Tahtakale Makası</span>
            <span className="text-[10px] text-zinc-400 block mt-1">
              Kapalıçarşı vs Banka Spotu
            </span>
          </div>
          <div className="p-3 rounded-lg bg-zinc-950/80 border border-zinc-800">
            <span className="text-[10px] text-zinc-500 block">Ağırlık: %15</span>
            <span className="font-bold text-white">Türkiye 5Y CDS</span>
            <span className="text-[10px] text-zinc-400 block mt-1">
              Kredi Temerrüt Takası Primi
            </span>
          </div>
          <div className="p-3 rounded-lg bg-zinc-950/80 border border-zinc-800">
            <span className="text-[10px] text-zinc-500 block">Ağırlık: %15</span>
            <span className="font-bold text-white">TÜFE REER</span>
            <span className="text-[10px] text-zinc-400 block mt-1">
              Reel Efektif Döviz Kuru
            </span>
          </div>
        </div>
      </section>

      {/* Yasal Uyarı */}
      <div className="p-4 rounded-xl border border-zinc-800/60 bg-zinc-950/40 text-[11px] text-zinc-500 leading-relaxed">
        <strong>Yasal Uyarı (SPK Mevzuatı):</strong> Bu sayfada yer alan Kur Şoku & Devalüasyon Basınç Radarı,
        piyasa göstergeleri ve nicel analizler yalnızca genel bilgilendirme ve analitik takip amacıyla
        üretilmiştir. Hiçbir surette yatırım tavsiyesi, portföy yöneticiliği veya döviz alım/satım önerisi
        niteliği taşımaz. Yatırım kararlarınızı kendi risk profilinize ve yetkili kuruluşların danışmanlığına
        dayandırınız.
      </div>
    </div>
  );
}
