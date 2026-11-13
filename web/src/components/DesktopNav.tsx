"use client";

import React, { useState, useRef, useEffect } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { ChevronDown, BarChart2, ShieldAlert, Calendar, RefreshCcw, Landmark, Wheat, Archive, Layers, Fuel } from "lucide-react";

interface DropdownItem {
  href: string;
  label: string;
  description?: string;
  icon?: React.ComponentType<{ className?: string }>;
}

export function DesktopNav() {
  const pathname = usePathname();
  const [openDropdown, setOpenDropdown] = useState<string | null>(null);
  const timeoutRef = useRef<NodeJS.Timeout | null>(null);

  const handleMouseEnter = (key: string) => {
    if (timeoutRef.current) clearTimeout(timeoutRef.current);
    setOpenDropdown(key);
  };

  const handleMouseLeave = () => {
    timeoutRef.current = setTimeout(() => {
      setOpenDropdown(null);
    }, 150);
  };

  const piyasalarItems: DropdownItem[] = [
    {
      href: "/kategori/bist",
      label: "BIST & Sektörler",
      description: "Borsa İstanbul şirketleri, sektör rotasyonları ve bilanço analizleri",
      icon: BarChart2,
    },
    {
      href: "/kategori/viop",
      label: "VİOP & Türev",
      description: "Vadeli işlem kontratları, basis spread ve Takasbank teminatları",
      icon: Layers,
    },
    {
      href: "/kategori/global",
      label: "Küresel Makro",
      description: "ABD tahvilleri, Fed faiz patikası, DXY ve küresel piyasalar",
      icon: Landmark,
    },
    {
      href: "/tarim-emtia?tab=petrolTanker",
      label: "Petrol & Tanker Navlun",
      description: "Brent, WTI, VLCC/Aframax kiralama ücretleri ve boğaz bekleme süreleri",
      icon: Fuel,
    },
    {
      href: "/kategori/gundem",
      label: "Ekonomi & Gündem",
      description: "TCMB kararları, enflasyon verileri ve makroekonomik gelişmeler",
    },
    {
      href: "/kategori/kripto",
      label: "Kripto Varlıklar",
      description: "Bitcoin, kurumsal ETF akışları ve zincir üstü likidite verileri",
    },
  ];

  const radarlarItems: DropdownItem[] = [
    {
      href: "/piyasa/devaluasyon-radari",
      label: "Kur Şoku & Devalüasyon Radarı",
      description: "TCMB rezerv yanma hızı, Kapalıçarşı makası ve VİOP ima edilen faiz",
      icon: ShieldAlert,
    },
    {
      href: "/piyasa/geri-alimlar",
      label: "Pay Geri Alım Radarı",
      description: "BIST şirketlerinin KAP bildirimli hisse geri alım fonları ve maliyetleri",
      icon: RefreshCcw,
    },
    {
      href: "/piyasa/temettu-takvimi",
      label: "Temettü Takvimi",
      description: "Kesinleşen ve teklif edilen nakit kâr payı dağıtımları ve verimleri",
      icon: Calendar,
    },
    {
      href: "/halka-arz-takvimi",
      label: "Halka Arz Takvimi",
      description: "Taslak ve onaylı BIST izahnameleri, konsorsiyum ve fiyat tespit raporları",
    },
  ];

  const isPiyasalarActive = piyasalarItems.some((item) => pathname.startsWith(item.href));
  const isRadarlarActive = radarlarItems.some((item) => pathname.startsWith(item.href));

  return (
    <nav className="hidden xl:flex items-center gap-1 xl:gap-2 text-sm font-medium whitespace-nowrap">
      {/* 0. Hisse Tarayıcı */}
      <Link
        href="/hisseler"
        className={`px-3 py-1.5 rounded-lg transition-colors ${
          pathname === "/hisseler" || pathname.startsWith("/hisse/")
            ? "text-white bg-zinc-900 border border-zinc-800"
            : "text-zinc-400 hover:text-white hover:bg-zinc-900/50"
        }`}
      >
        Hisseler
      </Link>

      {/* 1. Raporlar & Akış (Ana Sayfa) */}
      <Link
        href="/"
        className={`px-3 py-1.5 rounded-lg transition-colors ${
          pathname === "/"
            ? "text-white bg-zinc-900 border border-zinc-800"
            : "text-zinc-400 hover:text-white hover:bg-zinc-900/50"
        }`}
      >
        Raporlar
      </Link>

      {/* 2. Piyasalar Dropdown */}
      <div
        className="relative"
        onMouseEnter={() => handleMouseEnter("piyasalar")}
        onMouseLeave={handleMouseLeave}
      >
        <button
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg transition-colors ${
            isPiyasalarActive || openDropdown === "piyasalar"
              ? "text-white bg-zinc-900 border border-zinc-800"
              : "text-zinc-400 hover:text-white hover:bg-zinc-900/50"
          }`}
          aria-expanded={openDropdown === "piyasalar"}
        >
          <span>Piyasalar</span>
          <ChevronDown
            className={`w-3.5 h-3.5 transition-transform duration-200 ${
              openDropdown === "piyasalar" ? "rotate-180 text-amber-400" : "text-zinc-500"
            }`}
          />
        </button>

        {openDropdown === "piyasalar" && (
          <div className="absolute top-full left-0 mt-1 w-72 rounded-xl border border-zinc-800 bg-zinc-950/95 p-2 shadow-2xl backdrop-blur-xl z-50 animate-in fade-in zoom-in-95 duration-150">
            <div className="text-[10px] font-mono uppercase tracking-wider text-zinc-500 px-2.5 py-1.5">
              Piyasa Kapsamı
            </div>
            {piyasalarItems.map((item) => {
              const Icon = item.icon;
              const active = pathname === item.href;
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  onClick={() => setOpenDropdown(null)}
                  className={`flex items-start gap-2.5 p-2 rounded-lg transition-colors ${
                    active ? "bg-zinc-900 text-white" : "hover:bg-zinc-900/80 text-zinc-300 hover:text-white"
                  }`}
                >
                  {Icon && (
                    <span className="p-1 rounded-md bg-zinc-900 text-zinc-400 border border-zinc-800 shrink-0 mt-0.5">
                      <Icon className="w-3.5 h-3.5" />
                    </span>
                  )}
                  <div>
                    <span className="text-xs font-semibold block">{item.label}</span>
                    {item.description && (
                      <span className="text-[11px] text-zinc-500 line-clamp-1 mt-0.5 font-normal">
                        {item.description}
                      </span>
                    )}
                  </div>
                </Link>
              );
            })}
          </div>
        )}
      </div>

      {/* 3. Radarlar & Takvim Dropdown */}
      <div
        className="relative"
        onMouseEnter={() => handleMouseEnter("radarlar")}
        onMouseLeave={handleMouseLeave}
      >
        <button
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg transition-colors ${
            isRadarlarActive || openDropdown === "radarlar"
              ? "text-white bg-zinc-900 border border-zinc-800"
              : "text-zinc-400 hover:text-white hover:bg-zinc-900/50"
          }`}
          aria-expanded={openDropdown === "radarlar"}
        >
          <span>Radarlar & Takvim</span>
          <ChevronDown
            className={`w-3.5 h-3.5 transition-transform duration-200 ${
              openDropdown === "radarlar" ? "rotate-180 text-amber-400" : "text-zinc-500"
            }`}
          />
        </button>

        {openDropdown === "radarlar" && (
          <div className="absolute top-full left-0 mt-1 w-80 rounded-xl border border-zinc-800 bg-zinc-950/95 p-2 shadow-2xl backdrop-blur-xl z-50 animate-in fade-in zoom-in-95 duration-150">
            <div className="text-[10px] font-mono uppercase tracking-wider text-zinc-500 px-2.5 py-1.5">
              Analitik Radarlar
            </div>
            {radarlarItems.map((item) => {
              const Icon = item.icon;
              const active = pathname === item.href;
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  onClick={() => setOpenDropdown(null)}
                  className={`flex items-start gap-2.5 p-2 rounded-lg transition-colors ${
                    active ? "bg-zinc-900 text-white" : "hover:bg-zinc-900/80 text-zinc-300 hover:text-white"
                  }`}
                >
                  {Icon && (
                    <span className="p-1 rounded-md bg-zinc-900 text-amber-400 border border-zinc-800 shrink-0 mt-0.5">
                      <Icon className="w-3.5 h-3.5" />
                    </span>
                  )}
                  <div>
                    <span className="text-xs font-semibold block">{item.label}</span>
                    {item.description && (
                      <span className="text-[11px] text-zinc-500 line-clamp-1 mt-0.5 font-normal">
                        {item.description}
                      </span>
                    )}
                  </div>
                </Link>
              );
            })}
          </div>
        )}
      </div>

      {/* 4. Emtia & Terminal */}
      <Link
        href="/tarim-emtia"
        className={`px-3 py-1.5 rounded-lg transition-colors ${
          pathname === "/tarim-emtia"
            ? "text-white bg-zinc-900 border border-zinc-800"
            : "text-zinc-400 hover:text-white hover:bg-zinc-900/50"
        }`}
      >
        Emtia & Terminal
      </Link>

      {/* 5. Arşiv */}
      <Link
        href="/arsiv"
        className={`px-3 py-1.5 rounded-lg transition-colors ${
          pathname === "/arsiv"
            ? "text-white bg-zinc-900 border border-zinc-800"
            : "text-zinc-400 hover:text-white hover:bg-zinc-900/50"
        }`}
      >
        Arşiv
      </Link>
    </nav>
  );
}
