"use client";

import React, { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { fold } from "@/lib/fold";
import {
  Search,
  Command,
  TrendingUp,
  FileText,
  PieChart,
  ShieldCheck,
  Wheat,
  Activity,
  Layers,
  ArrowRight,
  X,
} from "lucide-react";

interface SearchItem {
  id: string;
  title: string;
  subtitle: string;
  category: "hisse" | "kategori" | "arac";
  href: string;
  badge?: string;
}

const DEFAULT_ITEMS: SearchItem[] = [
  // BIST Hisseleri
  { id: "THYAO", title: "THYAO", subtitle: "Türk Hava Yolları — DCF, Key Levels & Bilanço", category: "hisse", href: "/hisse/THYAO", badge: "BIST 30" },
  { id: "ASELS", title: "ASELS", subtitle: "Aselsan Elektronik — Savunma Sanayi & Bilanço", category: "hisse", href: "/hisse/ASELS", badge: "BIST 30" },
  { id: "BIMAS", title: "BIMAS", subtitle: "BİM Birleşik Mağazalar — Perakende & TÜRİB Korelasyonu", category: "hisse", href: "/hisse/BIMAS", badge: "BIST 30" },
  { id: "TUPRS", title: "TUPRS", subtitle: "Tüpraş Rafinerileri — Rafineri Marjları & DCF", category: "hisse", href: "/hisse/TUPRS", badge: "BIST 30" },
  { id: "EREGL", title: "EREGL", subtitle: "Ereğli Demir Çelik — Çelik Fiyatları & Bilanço", category: "hisse", href: "/hisse/EREGL", badge: "BIST 30" },
  { id: "KCHOL", title: "KCHOL", subtitle: "Koç Holding — Net Aktif Değer (NAD) İskontosu", category: "hisse", href: "/hisse/KCHOL", badge: "BIST 30" },
  { id: "GARAN", title: "GARAN", subtitle: "Garanti BBVA — Bankacılık Endeksi & Çarpanlar", category: "hisse", href: "/hisse/GARAN", badge: "BIST 30" },
  { id: "PGSUS", title: "PGSUS", subtitle: "Pegasus Hava Taşımacılığı — Yolcu Verileri & DCF", category: "hisse", href: "/hisse/PGSUS", badge: "BIST 30" },
  { id: "FROTO", title: "FROTO", subtitle: "Ford Otomotiv — İhracat & Elektrikli Araç", category: "hisse", href: "/hisse/FROTO", badge: "BIST 30" },
  { id: "SISE", title: "SISE", subtitle: "Şişecam — Global Cam Talebi & Soda Külü", category: "hisse", href: "/hisse/SISE", badge: "BIST 30" },
  { id: "SAHOL", title: "SAHOL", subtitle: "Sabancı Holding — Enerji, Finans & Bilanço", category: "hisse", href: "/hisse/SAHOL", badge: "BIST 30" },
  { id: "ULUUN", title: "ULUUN", subtitle: "Ulusoy Un — Buğday & TÜRİB Tarım Sanayisi", category: "hisse", href: "/hisse/ULUUN", badge: "BIST 100" },

  // Analitik Araçlar & Sayfalar
  { id: "DEVAL", title: "Kur Şoku & Devalüasyon Radarı", subtitle: "TCMB Rezerv Yanma Hızı, Tahtakale Makası & VİOP İma Edilen Faiz", category: "arac", href: "/piyasa/devaluasyon-radari", badge: "0-100 Radar" },
  { id: "BUYBACKS", title: "Pay Geri Alımları", subtitle: "BIST Şirketlerinin Aktif Hisse Geri Alım Fonları & Maliyetleri", category: "arac", href: "/piyasa/geri-alimlar", badge: "Radar" },
  { id: "DIVIDENDS", title: "Temettü Takvimi", subtitle: "2026 Nakit Kâr Payı Dağıtımları & Temettü Verimleri", category: "arac", href: "/piyasa/temettu-takvimi", badge: "Takvim" },
  { id: "TARIM", title: "Tarımsal Emtia & Et-Yem", subtitle: "TÜRİB Hububat Fiyatları, Karkas Et ve Yem Rasyosu", category: "arac", href: "/tarim-emtia", badge: "Canlı Veri" },
  { id: "TANKER", title: "Petrol & Tanker Navlun Terminali", subtitle: "Brent, WTI, VLCC/Aframax kiralama ücretleri (TCE) ve boğaz bekleme süreleri", category: "arac", href: "/tarim-emtia?tab=petrolTanker", badge: "Terminal" },
  { id: "IPO", title: "Halka Arz & KAP Radarı", subtitle: "Son Taslak İzahnameler ve BIST Halka Arz Takvimi", category: "arac", href: "/halka-arz-takvimi", badge: "Takvim" },
  { id: "ARSIV", title: "Rapor Arşivi", subtitle: "Tüm Tarihsel Analizler, Seans Açılış & Kapanış Raporları", category: "arac", href: "/arsiv", badge: "Arşiv" },

  // Kategoriler
  { id: "KAT_BIST", title: "BIST & Sektör", subtitle: "Borsa İstanbul, Sektör Rotasyonları ve Şirketler", category: "kategori", href: "/kategori/bist", badge: "Kategori" },
  { id: "KAT_VIOP", title: "VİOP & Türev", subtitle: "Vadeli İşlemler, Margin Call ve Kaldıraç Verileri", category: "kategori", href: "/kategori/viop", badge: "Kategori" },
  { id: "KAT_GLOBAL", title: "Küresel Makro", subtitle: "Fed, Faiz, CDS Primi ve Dolar Endeksi", category: "kategori", href: "/kategori/global", badge: "Kategori" },
];

const TOOL_ITEMS: SearchItem[] = [
  { id: "SCREENER", title: "Hisse Tarayıcı", subtitle: "F/K, PD/DD, ROE, temettü filtreleri ile tüm BIST hisseleri", category: "arac", href: "/hisseler", badge: "Tarayıcı" },
];

export interface PaletteStock {
  ticker: string;
  name: string;
  sector: string;
}

export function SearchCommandPalette({ stocks = [] }: { stocks?: PaletteStock[] }) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [selectedIndex, setSelectedIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const router = useRouter();

  // Klavye Kısayolu (Cmd+K / Ctrl+K) Dinleme
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen((prev) => !prev);
      } else if (e.key === "Escape" && open) {
        e.preventDefault();
        setOpen(false);
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [open]);

  // Modal açıldığında input'a odaklan
  useEffect(() => {
    if (open) {
      setTimeout(() => inputRef.current?.focus(), 50);
      setSelectedIndex(0);
    } else {
      setQuery("");
    }
  }, [open]);

  // Filtreleme
  // Evren varsa tüm hisseleri ara; boş sorguda kısa varsayılan liste göster
  const stockItems: SearchItem[] = stocks.map((s) => ({
    id: s.ticker,
    title: s.ticker,
    subtitle: `${s.name} — ${s.sector}`,
    category: "hisse",
    href: `/hisse/${s.ticker}`,
    badge: "BIST",
  }));
  const allItems = [...TOOL_ITEMS, ...DEFAULT_ITEMS.filter((i) => i.category !== "hisse" || !stocks.length), ...stockItems];
  const cleanQuery = fold(query.trim());
  const filteredItems = cleanQuery
    ? allItems
        .filter((item) => fold(item.title).includes(cleanQuery) || fold(item.subtitle).includes(cleanQuery))
        .sort((a, b) => Number(fold(b.title).startsWith(cleanQuery)) - Number(fold(a.title).startsWith(cleanQuery)))
        .slice(0, 12)
    : [...TOOL_ITEMS, ...DEFAULT_ITEMS];

  // Seçim değiştirme ve Enter ile yönlendirme
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setSelectedIndex((prev) => (prev + 1) % Math.max(1, filteredItems.length));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setSelectedIndex((prev) =>
        prev - 1 < 0 ? Math.max(0, filteredItems.length - 1) : prev - 1
      );
    } else if (e.key === "Enter" && filteredItems[selectedIndex]) {
      e.preventDefault();
      const target = filteredItems[selectedIndex].href;
      setOpen(false);
      router.push(target);
    }
  };

  const handleSelect = (href: string) => {
    setOpen(false);
    router.push(href);
  };

  return (
    <>
      {/* Header Hızlı Arama Butonu Tetikleyicisi */}
      <button
        onClick={() => setOpen(true)}
        className="flex items-center gap-2 px-2.5 py-1.5 rounded-lg bg-zinc-900 border border-zinc-800 text-zinc-400 hover:text-white hover:border-zinc-700 transition-all text-xs"
        title="Hızlı Komut Paleti (Ctrl + K)"
      >
        <Search className="w-3.5 h-3.5 text-zinc-400" />
        <span className="hidden sm:inline">Hisse / Rapor Ara...</span>
        <kbd className="hidden md:inline-flex items-center gap-0.5 px-1.5 py-0.5 text-[10px] font-mono bg-zinc-800 border border-zinc-700 rounded text-zinc-400">
          <span className="text-xs">⌘</span>K
        </kbd>
      </button>

      {/* Modal Backdrop & Dialog */}
      {open && (
        <div className="fixed inset-0 z-[100] flex items-start justify-center pt-20 p-4 bg-black/75 backdrop-blur-sm animate-in fade-in duration-150">
          <div
            className="w-full max-w-xl rounded-2xl border border-zinc-800 bg-zinc-950 shadow-2xl overflow-hidden flex flex-col"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Input Bar */}
            <div className="flex items-center px-4 py-3 border-b border-zinc-800 gap-3">
              <Search className="w-5 h-5 text-cyan-400 shrink-0" />
              <input
                ref={inputRef}
                type="text"
                value={query}
                onChange={(e) => {
                  setQuery(e.target.value);
                  setSelectedIndex(0);
                }}
                onKeyDown={handleKeyDown}
                placeholder="Hisse kodu (THYAO), emtia, kategori veya analiz ara..."
                className="w-full bg-transparent text-sm text-white placeholder-zinc-500 focus:outline-none"
              />
              {query && (
                <button
                  onClick={() => setQuery("")}
                  className="p-1 rounded text-zinc-500 hover:text-white"
                >
                  <X className="w-4 h-4" />
                </button>
              )}
              <kbd className="hidden sm:inline-block px-1.5 py-0.5 text-[10px] font-mono bg-zinc-900 border border-zinc-800 rounded text-zinc-500">
                ESC
              </kbd>
            </div>

            {/* Sonuç Listesi */}
            <div className="max-h-[380px] overflow-y-auto p-2 divide-y divide-zinc-900">
              {filteredItems.length === 0 ? (
                <div className="py-12 text-center text-xs text-zinc-500">
                  <p>Aramanızla eşleşen hisse veya modül bulunamadı.</p>
                  <p className="mt-1 text-[11px] text-zinc-600">
                    Örnek: "THYAO", "ASELS", "Tarım", "VİOP", "Halka Arz"
                  </p>
                </div>
              ) : (
                filteredItems.map((item, idx) => {
                  const isSelected = idx === selectedIndex;
                  return (
                    <div
                      key={item.id}
                      onClick={() => handleSelect(item.href)}
                      onMouseEnter={() => setSelectedIndex(idx)}
                      className={`flex items-center justify-between px-3.5 py-2.5 rounded-xl cursor-pointer transition-all ${
                        isSelected
                          ? "bg-cyan-500/10 border border-cyan-500/30 text-white"
                          : "hover:bg-zinc-900/60 text-zinc-300 border border-transparent"
                      }`}
                    >
                      <div className="flex items-center gap-3 min-w-0">
                        <span
                          className={`p-2 rounded-lg shrink-0 ${
                            item.category === "hisse"
                              ? "bg-cyan-500/10 text-cyan-400"
                              : item.category === "arac"
                              ? "bg-emerald-500/10 text-emerald-400"
                              : "bg-amber-500/10 text-amber-400"
                          }`}
                        >
                          {item.category === "hisse" ? (
                            <TrendingUp className="w-4 h-4" />
                          ) : item.category === "arac" ? (
                            <Activity className="w-4 h-4" />
                          ) : (
                            <Layers className="w-4 h-4" />
                          )}
                        </span>
                        <div className="min-w-0">
                          <div className="flex items-center gap-2">
                            <span className="font-mono font-bold text-sm text-white">
                              {item.title}
                            </span>
                            {item.badge && (
                              <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-zinc-900 text-zinc-400 border border-zinc-800">
                                {item.badge}
                              </span>
                            )}
                          </div>
                          <p className="text-xs text-zinc-400 truncate mt-0.5">
                            {item.subtitle}
                          </p>
                        </div>
                      </div>

                      <ArrowRight
                        className={`w-4 h-4 shrink-0 transition-transform ${
                          isSelected
                            ? "text-cyan-400 translate-x-0.5"
                            : "text-zinc-600"
                        }`}
                      />
                    </div>
                  );
                })
              )}
            </div>

            {/* Alt Bilgi */}
            <div className="px-4 py-2.5 bg-zinc-900/50 border-t border-zinc-800/80 flex items-center justify-between text-[11px] text-zinc-500">
              <div className="flex items-center gap-3">
                <span className="flex items-center gap-1">
                  <kbd className="px-1 py-0.5 bg-zinc-800 rounded font-mono text-[9px]">↑</kbd>
                  <kbd className="px-1 py-0.5 bg-zinc-800 rounded font-mono text-[9px]">↓</kbd> Gezin
                </span>
                <span className="flex items-center gap-1">
                  <kbd className="px-1 py-0.5 bg-zinc-800 rounded font-mono text-[9px]">↵</kbd> Seç
                </span>
              </div>
              <span className="font-mono text-[10px] text-zinc-400">Esham Terminal v2.1</span>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
