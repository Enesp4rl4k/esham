"use client";

import React, { useState, useMemo } from "react";
import { TrendingUp, TrendingDown, BarChart2, Calendar, Maximize2 } from "lucide-react";

interface InteractiveStockChartProps {
  ticker: string;
  currentPrice: number;
  changePct: number;
  sma20?: number;
  sma50?: number;
}

export function InteractiveStockChart({
  ticker,
  currentPrice,
  changePct,
  sma20,
  sma50,
}: InteractiveStockChartProps) {
  const [period, setPeriod] = useState<"1H" | "1A" | "3A" | "6A" | "1Y">("1A");
  const [hoverIndex, setHoverIndex] = useState<number | null>(null);

  // Periyoda göre sentetik veri üretimi (Baz fiyata göre gerçekçi rastgele yürüyüş)
  const chartData = useMemo(() => {
    const pointsMap = { "1H": 7, "1A": 30, "3A": 90, "6A": 180, "1Y": 252 };
    const numPoints = pointsMap[period];
    const data: { date: string; price: number; volume: number; sma20: number }[] = [];

    let p = currentPrice * (1.0 - changePct / 100.0 * (numPoints / 15));
    const now = new Date();

    for (let i = numPoints; i >= 0; i--) {
      const d = new Date(now.getTime() - i * 24 * 60 * 60 * 1000);
      const noise = (Math.sin(i * 0.4) * 0.015 + (Math.random() - 0.48) * 0.02) * currentPrice;
      p = Math.max(10, p + noise);

      // Son noktayı kesin güncel fiyata sabitle
      if (i === 0) p = currentPrice;

      data.push({
        date: d.toLocaleDateString("tr-TR", { day: "numeric", month: "short" }),
        price: Number(p.toFixed(2)),
        volume: Math.floor(Math.random() * 5000000 + 1000000),
        sma20: Number((p * 0.985).toFixed(2)),
      });
    }
    return data;
  }, [period, currentPrice, changePct]);

  const prices = chartData.map((d) => d.price);
  const minPrice = Math.min(...prices) * 0.98;
  const maxPrice = Math.max(...prices) * 1.02;
  const range = maxPrice - minPrice || 1;

  const width = 800;
  const height = 300;
  const paddingBottom = 40;
  const paddingTop = 20;
  const chartHeight = height - paddingBottom - paddingTop;

  // SVG Noktaları Hesabı
  const points = chartData.map((d, i) => {
    const x = (i / (chartData.length - 1)) * width;
    const y = paddingTop + chartHeight - ((d.price - minPrice) / range) * chartHeight;
    return { x, y, ...d };
  });

  const pathD = points.reduce(
    (acc, pt, i) => (i === 0 ? `M ${pt.x} ${pt.y}` : `${acc} L ${pt.x} ${pt.y}`),
    ""
  );

  const areaD = `${pathD} L ${width} ${height - paddingBottom} L 0 ${height - paddingBottom} Z`;

  const activePoint = hoverIndex !== null ? points[hoverIndex] : points[points.length - 1];
  const isUp = changePct >= 0;

  return (
    <div className="rounded-2xl border border-zinc-800 bg-zinc-950/90 p-6 backdrop-blur-md shadow-xl">
      {/* Üst Bar: Fiyat Bilgisi ve Periyot Seçiciler */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-4 border-b border-zinc-800 gap-4 mb-4">
        <div>
          <div className="flex items-center gap-3">
            <span className="font-mono text-2xl font-extrabold text-white">
              {activePoint ? `${activePoint.price.toFixed(2)} ₺` : `${currentPrice.toFixed(2)} ₺`}
            </span>
            <span
              className={`flex items-center gap-1 font-mono text-xs font-bold px-2 py-0.5 rounded ${
                isUp
                  ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                  : "bg-rose-500/10 text-rose-400 border border-rose-500/20"
              }`}
            >
              {isUp ? <TrendingUp className="w-3.5 h-3.5" /> : <TrendingDown className="w-3.5 h-3.5" />}
              %{changePct >= 0 ? `+${changePct.toFixed(2)}` : changePct.toFixed(2)}
            </span>
            {activePoint && (
              <span className="text-xs text-zinc-500 font-mono">
                {activePoint.date}
              </span>
            )}
          </div>
          <span className="text-[11px] text-zinc-500 block mt-0.5">
            BIST ${ticker} Seans Grafiği (Otomatik Ölçekli & HO Destekli)
          </span>
        </div>

        {/* Periyot Butonları */}
        <div className="flex items-center gap-1 bg-zinc-900 p-1 rounded-xl border border-zinc-800 self-start sm:self-auto">
          {(["1H", "1A", "3A", "6A", "1Y"] as const).map((p) => (
            <button
              key={p}
              onClick={() => {
                setPeriod(p);
                setHoverIndex(null);
              }}
              className={`px-3 py-1 rounded-lg text-xs font-mono font-semibold transition-all ${
                period === p
                  ? "bg-cyan-500/15 text-cyan-400 border border-cyan-500/30 shadow-sm"
                  : "text-zinc-400 hover:text-white"
              }`}
            >
              {p}
            </button>
          ))}
        </div>
      </div>

      {/* SVG Grafik Çizim Alanı */}
      <div className="relative w-full overflow-hidden">
        <svg
          viewBox={`0 0 ${width} ${height}`}
          className="w-full h-auto overflow-visible cursor-crosshair"
          onMouseLeave={() => setHoverIndex(null)}
          onMouseMove={(e) => {
            const rect = e.currentTarget.getBoundingClientRect();
            const relX = e.clientX - rect.left;
            const idx = Math.round((relX / rect.width) * (points.length - 1));
            if (idx >= 0 && idx < points.length) setHoverIndex(idx);
          }}
        >
          <defs>
            <linearGradient id="stockAreaGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#06b6d4" stopOpacity="0.25" />
              <stop offset="100%" stopColor="#06b6d4" stopOpacity="0.0" />
            </linearGradient>
          </defs>

          {/* Yatay Kılavuz Çizgileri */}
          {[0, 0.25, 0.5, 0.75, 1].map((pct, i) => {
            const y = paddingTop + chartHeight * (1 - pct);
            const val = minPrice + range * pct;
            return (
              <g key={i}>
                <line
                  x1="0"
                  y1={y}
                  x2={width}
                  y2={y}
                  stroke="rgba(255,255,255,0.05)"
                  strokeDasharray="4 4"
                />
                <text
                  x={width - 5}
                  y={y - 4}
                  fill="#71717a"
                  fontSize="10"
                  fontFamily="monospace"
                  textAnchor="end"
                >
                  {val.toFixed(1)} ₺
                </text>
              </g>
            );
          })}

          {/* Dolgu Alanı */}
          <path d={areaD} fill="url(#stockAreaGradient)" />

          {/* Fiyat Çizgisi */}
          <path
            d={pathD}
            fill="none"
            stroke="#06b6d4"
            strokeWidth="2.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          />

          {/* Aktif Hover Noktası & Crosshair */}
          {hoverIndex !== null && activePoint && (
            <g>
              <line
                x1={activePoint.x}
                y1={paddingTop}
                x2={activePoint.x}
                y2={height - paddingBottom}
                stroke="#06b6d4"
                strokeWidth="1"
                strokeDasharray="2 2"
              />
              <circle
                cx={activePoint.x}
                cy={activePoint.y}
                r="5"
                fill="#06b6d4"
                stroke="#09090b"
                strokeWidth="2"
              />
            </g>
          )}
        </svg>
      </div>

      {/* Alt Bilgi Barı */}
      <div className="flex items-center justify-between text-xs text-zinc-500 font-mono mt-3 pt-3 border-t border-zinc-800/80">
        <div className="flex items-center gap-4">
          <span className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-cyan-400" />
            <span>Fiyat Trendi</span>
          </span>
          {sma20 && (
            <span className="hidden sm:inline">
              20G HO: <strong className="text-zinc-300">{sma20.toFixed(2)} ₺</strong>
            </span>
          )}
          {sma50 && (
            <span className="hidden sm:inline">
              50G HO: <strong className="text-zinc-300">{sma50.toFixed(2)} ₺</strong>
            </span>
          )}
        </div>
        <span className="text-[11px] text-zinc-600">Canlı Vektörel Engine</span>
      </div>
    </div>
  );
}
