"use client";

import React, { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Menu, X, ChevronRight, BarChart2, ShieldAlert, Calendar, RefreshCcw } from "lucide-react";

export function MobileMenu() {
  const [isOpen, setIsOpen] = useState(false);
  const pathname = usePathname();

  const close = () => setIsOpen(false);

  return (
    <div className="lg:hidden">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="p-2 text-zinc-400 hover:text-white transition-colors"
        aria-label="Menüyü aç/kapat"
      >
        {isOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
      </button>

      {isOpen && (
        <div className="fixed inset-x-0 top-14 bottom-0 bg-zinc-950/98 border-b border-zinc-900 shadow-2xl py-5 px-6 z-50 overflow-y-auto backdrop-blur-2xl flex flex-col gap-6">
          {/* Ana Sayfalar */}
          <div className="space-y-1">
            <Link
              href="/"
              onClick={close}
              className={`block py-2 text-base font-semibold transition-colors ${
                pathname === "/" ? "text-amber-400" : "text-white hover:text-amber-400"
              }`}
            >
              Raporlar & Bülten
            </Link>
            <Link
              href="/tarim-emtia"
              onClick={close}
              className={`block py-2 text-base font-semibold transition-colors ${
                pathname === "/tarim-emtia" ? "text-amber-400" : "text-white hover:text-amber-400"
              }`}
            >
              Emtia & Tanker Terminali
            </Link>
            <Link
              href="/tarim-emtia?tab=petrolTanker"
              onClick={close}
              className="block py-1.5 pl-3 text-xs text-zinc-400 hover:text-amber-400 border-l border-zinc-800 font-mono"
            >
              Petrol & Tanker Navlun (TCE)
            </Link>
            <Link
              href="/arsiv"
              onClick={close}
              className={`block py-2 text-base font-semibold transition-colors ${
                pathname === "/arsiv" ? "text-amber-400" : "text-white hover:text-amber-400"
              }`}
            >
              Rapor Arşivi
            </Link>
          </div>

          {/* Radarlar */}
          <div>
            <div className="text-[11px] font-mono uppercase tracking-wider text-zinc-500 mb-2">
              Radarlar & Takvim
            </div>
            <div className="space-y-1 pl-1">
              <Link
                href="/piyasa/devaluasyon-radari"
                onClick={close}
                className="flex items-center justify-between py-2 text-sm text-zinc-300 hover:text-white"
              >
                <span>Kur Şoku & Devalüasyon Radarı</span>
                <ChevronRight className="w-4 h-4 text-zinc-600" />
              </Link>
              <Link
                href="/piyasa/geri-alimlar"
                onClick={close}
                className="flex items-center justify-between py-2 text-sm text-zinc-300 hover:text-white"
              >
                <span>Pay Geri Alım Radarı</span>
                <ChevronRight className="w-4 h-4 text-zinc-600" />
              </Link>
              <Link
                href="/piyasa/temettu-takvimi"
                onClick={close}
                className="flex items-center justify-between py-2 text-sm text-zinc-300 hover:text-white"
              >
                <span>Temettü Takvimi</span>
                <ChevronRight className="w-4 h-4 text-zinc-600" />
              </Link>
              <Link
                href="/halka-arz-takvimi"
                onClick={close}
                className="flex items-center justify-between py-2 text-sm text-zinc-300 hover:text-white"
              >
                <span>Halka Arz Takvimi</span>
                <ChevronRight className="w-4 h-4 text-zinc-600" />
              </Link>
            </div>
          </div>

          {/* Piyasalar & Sektörler */}
          <div>
            <div className="text-[11px] font-mono uppercase tracking-wider text-zinc-500 mb-2">
              Piyasalar & Kategoriler
            </div>
            <div className="grid grid-cols-2 gap-2 text-xs">
              <Link
                href="/kategori/bist"
                onClick={close}
                className="p-2.5 rounded-lg bg-zinc-900 border border-zinc-800 text-zinc-300 hover:text-white"
              >
                BIST & Sektör
              </Link>
              <Link
                href="/kategori/viop"
                onClick={close}
                className="p-2.5 rounded-lg bg-zinc-900 border border-zinc-800 text-zinc-300 hover:text-white"
              >
                VİOP & Türev
              </Link>
              <Link
                href="/kategori/global"
                onClick={close}
                className="p-2.5 rounded-lg bg-zinc-900 border border-zinc-800 text-zinc-300 hover:text-white"
              >
                Küresel Makro
              </Link>
              <Link
                href="/kategori/gundem"
                onClick={close}
                className="p-2.5 rounded-lg bg-zinc-900 border border-zinc-800 text-zinc-300 hover:text-white"
              >
                Ekonomi & Gündem
              </Link>
              <Link
                href="/kategori/kripto"
                onClick={close}
                className="p-2.5 rounded-lg bg-zinc-900 border border-zinc-800 text-zinc-300 hover:text-white"
              >
                Kripto Varlıklar
              </Link>
              <Link
                href="/kategori/teknoloji"
                onClick={close}
                className="p-2.5 rounded-lg bg-zinc-900 border border-zinc-800 text-zinc-300 hover:text-white"
              >
                Teknoloji & Girişim
              </Link>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
