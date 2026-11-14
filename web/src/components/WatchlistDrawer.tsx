"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import {
  Star,
  Bookmark,
  Trash2,
  TrendingUp,
  TrendingDown,
  X,
  ExternalLink,
  Plus,
} from "lucide-react";

const STORAGE_KEY = "esham_user_watchlist";

interface TickerPrice {
  label: string;
  value: string;
  change: string;
  up: boolean;
}

interface WatchlistDrawerProps {
  currentTicker?: string;
}

export function WatchlistDrawer({ currentTicker }: WatchlistDrawerProps) {
  const [watchlist, setWatchlist] = useState<string[]>([]);
  const [isOpen, setIsOpen] = useState(false);
  const [marketPrices, setMarketPrices] = useState<Record<string, TickerPrice>>({});

  // 1. LocalStorage'dan takip listesini yükle
  useEffect(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved) {
        setWatchlist(JSON.parse(saved));
      } else {
        // Varsayılan BIST favorileri
        const defaults = ["THYAO", "ASELS", "BIMAS"];
        setWatchlist(defaults);
        localStorage.setItem(STORAGE_KEY, JSON.stringify(defaults));
      }
    } catch {
      // Hata durumunda varsayılan
    }
  }, []);

  // 2. Canlı Ticker Verilerini Çek
  useEffect(() => {
    async function fetchPrices() {
      try {
        const res = await fetch("/data/market-ticker.json");
        if (!res.ok) return;
        const data = await res.json();
        const map: Record<string, TickerPrice> = {};
        for (const t of data.tickers || []) {
          map[t.label] = t;
        }
        setMarketPrices(map);
      } catch {
        // Sessiz hata
      }
    }
    fetchPrices();
  }, [isOpen]);

  // Takip Listesine Ekle / Çıkar
  const toggleTicker = (ticker: string) => {
    const clean = ticker.toUpperCase();
    let updated: string[];
    if (watchlist.includes(clean)) {
      updated = watchlist.filter((t) => t !== clean);
    } else {
      updated = [...watchlist, clean];
    }
    setWatchlist(updated);
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(updated));
    } catch {
      // ignore
    }
  };

  const isCurrentFollowed = currentTicker ? watchlist.includes(currentTicker.toUpperCase()) : false;

  return (
    <>
      {/* Eğer bir hisse sayfasındaysak "Takip Listeme Ekle / Çıkar" Butonu */}
      {currentTicker && (
        <button
          onClick={() => toggleTicker(currentTicker)}
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold border transition-all ${
            isCurrentFollowed
              ? "bg-amber-500/10 border-amber-500/40 text-amber-400 hover:bg-amber-500/20"
              : "bg-zinc-900 border-zinc-800 text-zinc-400 hover:border-zinc-700 hover:text-white"
          }`}
          title={isCurrentFollowed ? "Takip Listesinden Çıkar" : "Takip Listesine Ekle"}
        >
          <Star className={`w-3.5 h-3.5 ${isCurrentFollowed ? "fill-amber-400 text-amber-400" : ""}`} />
          <span>{isCurrentFollowed ? "İzleniyor" : "Listeye Ekle"}</span>
        </button>
      )}

      {/* Sabit / Kayan Takip Listesi Butonu (Floating Widget) */}
      <button
        onClick={() => setIsOpen(true)}
        className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-zinc-900 border border-zinc-800 text-zinc-300 hover:text-white hover:border-zinc-700 transition-all text-xs"
        title="Kişisel İzleme Listesi"
      >
        <Bookmark className="w-3.5 h-3.5 text-amber-400" />
        <span className="hidden sm:inline">İzleme Listem</span>
        <span className="px-1.5 py-0.2 rounded-full font-mono text-xs bg-amber-500/20 text-amber-400 font-bold border border-amber-500/30">
          {watchlist.length}
        </span>
      </button>

      {/* Slide-over Drawer Paneli */}
      {isOpen && (
        <div className="fixed inset-0 z-[110] flex justify-end bg-black/60 backdrop-blur-sm animate-in fade-in duration-200">
          <div
            className="w-full max-w-sm h-full bg-zinc-950 border-l border-zinc-800 shadow-2xl flex flex-col"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Header */}
            <div className="p-4 border-b border-zinc-800 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="p-1.5 rounded-lg bg-amber-500/10 text-amber-400 border border-amber-500/20">
                  <Star className="w-4 h-4 fill-amber-400" />
                </span>
                <div>
                  <h3 className="text-sm font-bold text-white tracking-tight">Kişisel İzleme Listem</h3>
                  <span className="text-xs font-mono text-zinc-400">
                    Tarayıcı Hafızası (Gizli & Güvenli)
                  </span>
                </div>
              </div>
              <button
                onClick={() => setIsOpen(false)}
                className="p-1 rounded-lg text-zinc-400 hover:text-white hover:bg-zinc-900 transition-colors"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Liste Alanı */}
            <div className="flex-1 overflow-y-auto p-4 space-y-2.5">
              {watchlist.length === 0 ? (
                <div className="py-16 text-center text-xs text-zinc-400">
                  <Bookmark className="w-8 h-8 text-zinc-700 mx-auto mb-2" />
                  <p className="font-semibold text-zinc-400">İzleme listeniz henüz boş.</p>
                  <p className="mt-1 text-xs text-zinc-400">
                    Hisse sayfalarındaki "Listeye Ekle" butonuna basarak hisseleri buraya ekleyebilirsiniz.
                  </p>
                </div>
              ) : (
                watchlist.map((ticker) => {
                  const quote = marketPrices[ticker];
                  return (
                    <div
                      key={ticker}
                      className="p-3 rounded-xl border border-zinc-800/80 bg-zinc-900/50 hover:bg-zinc-900 transition-all flex items-center justify-between"
                    >
                      <Link
                        href={`/hisse/${ticker}`}
                        onClick={() => setIsOpen(false)}
                        className="flex-1 min-w-0 pr-2"
                      >
                        <div className="flex items-center gap-2">
                          <span className="font-mono font-bold text-sm text-white">
                            ${ticker}
                          </span>
                          <ExternalLink className="w-3 h-3 text-zinc-400 opacity-60" />
                        </div>
                        {quote ? (
                          <div className="flex items-center gap-2 mt-0.5 text-xs font-mono">
                            <span className="text-zinc-200 font-semibold">{quote.value}</span>
                            <span
                              className={`flex items-center gap-0.5 text-xs ${
                                quote.up ? "text-emerald-400" : "text-rose-400"
                              }`}
                            >
                              {quote.up ? (
                                <TrendingUp className="w-3 h-3" />
                              ) : (
                                <TrendingDown className="w-3 h-3" />
                              )}
                              {quote.change}
                            </span>
                          </div>
                        ) : (
                          <span className="text-xs text-zinc-400 font-mono block mt-0.5">
                            Terminal Verisi Hazır
                          </span>
                        )}
                      </Link>

                      <button
                        onClick={() => toggleTicker(ticker)}
                        className="p-1.5 rounded-lg text-zinc-400 hover:text-rose-400 hover:bg-rose-500/10 transition-colors shrink-0"
                        title="Listeden Çıkar"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  );
                })
              )}
            </div>

            {/* Hızlı Ekleme ve Alt Bilgi */}
            <div className="p-4 border-t border-zinc-800 bg-zinc-900/40">
              <span className="text-xs uppercase font-bold tracking-wider text-zinc-400 block mb-2">
                Hızlı Ekle (BIST 30)
              </span>
              <div className="flex flex-wrap gap-1.5">
                {["THYAO", "ASELS", "BIMAS", "TUPRS", "EREGL", "KCHOL"].map((sym) => {
                  const added = watchlist.includes(sym);
                  return (
                    <button
                      key={sym}
                      onClick={() => toggleTicker(sym)}
                      className={`text-xs font-mono px-2 py-1 rounded border transition-all ${
                        added
                          ? "bg-amber-500/10 border-amber-500/30 text-amber-400"
                          : "bg-zinc-900 border-zinc-800 text-zinc-400 hover:text-white"
                      }`}
                    >
                      {added ? `✓ ${sym}` : `+ ${sym}`}
                    </button>
                  );
                })}
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
