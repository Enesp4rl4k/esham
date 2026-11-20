"use client";

import { useEffect, useMemo, useState } from "react";

type Point = [string, number]; // [ISO tarih, kapanış]
const RANGES = [
  { id: "6A", label: "6 Ay", weeks: 26 },
  { id: "1Y", label: "1 Yıl", weeks: 52 },
  { id: "3Y", label: "3 Yıl", weeks: 156 },
  { id: "5Y", label: "5 Yıl", weeks: 9999 },
] as const;

const W = 800, H = 280, PL = 8, PR = 52, PT = 16, PB = 26;
const nf = new Intl.NumberFormat("tr-TR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const fmtDate = (d: string) => new Date(d).toLocaleDateString("tr-TR", { day: "numeric", month: "short", year: "numeric" });

/** Gerçek haftalık kapanış serisi (bot: `esham stocks` → public/data/prices/<T>.json). Sentetik veri yok. */
export function PriceChart({ ticker }: { ticker: string }) {
  const [series, setSeries] = useState<Point[] | null>(null);
  const [state, setState] = useState<"loading" | "ok" | "missing">("loading");
  const [range, setRange] = useState<(typeof RANGES)[number]["id"]>("1Y");
  const [hover, setHover] = useState<number | null>(null);

  useEffect(() => {
    let alive = true;
    fetch(`/data/prices/${ticker}.json`)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(String(r.status)))))
      .then((d: Point[]) => {
        if (!alive) return;
        if (Array.isArray(d) && d.length > 4) {
          setSeries(d);
          setState("ok");
        } else setState("missing");
      })
      .catch(() => alive && setState("missing"));
    return () => {
      alive = false;
    };
  }, [ticker]);

  const pts = useMemo(() => {
    if (!series) return [];
    const w = RANGES.find((r) => r.id === range)!.weeks;
    return series.slice(-w);
  }, [series, range]);

  if (state === "loading") return <div className="h-72 rounded-2xl border border-zinc-800 bg-zinc-950/80 animate-pulse" aria-busy="true" />;
  if (state === "missing" || pts.length < 2)
    return (
      <div className="rounded-2xl border border-zinc-800 bg-zinc-950/80 p-6 text-sm text-zinc-400">
        Bu hisse için fiyat geçmişi henüz yok.
      </div>
    );

  const vals = pts.map((p) => p[1]);
  const lo = Math.min(...vals), hi = Math.max(...vals);
  const pad = (hi - lo) * 0.08 || 1;
  const min = lo - pad, max = hi + pad;
  const x = (i: number) => PL + (i * (W - PL - PR)) / (pts.length - 1);
  const y = (v: number) => PT + ((max - v) / (max - min)) * (H - PT - PB);
  const line = pts.map((p, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(p[1]).toFixed(1)}`).join("");
  const area = `${line}L${x(pts.length - 1).toFixed(1)},${H - PB}L${PL},${H - PB}Z`;

  const first = pts[0][1], last = pts[pts.length - 1][1];
  const change = (last / first - 1) * 100;
  const up = change >= 0;
  const color = up ? "#22c55e" : "#ef4444";
  const act = hover !== null ? pts[hover] : pts[pts.length - 1];
  const ticks = [hi, (hi + lo) / 2, lo];

  const onMove = (e: React.PointerEvent<SVGSVGElement>) => {
    const r = e.currentTarget.getBoundingClientRect();
    const px = ((e.clientX - r.left) / r.width) * W;
    const i = Math.round(((px - PL) / (W - PL - PR)) * (pts.length - 1));
    setHover(Math.max(0, Math.min(pts.length - 1, i)));
  };

  return (
    <div className="rounded-2xl border border-zinc-800 bg-zinc-950/80 p-5 shadow-xl">
      <div className="flex flex-wrap items-start justify-between gap-3 mb-3">
        <div>
          <p className="font-mono text-2xl font-bold text-white tabular-nums">{nf.format(act[1])} ₺</p>
          <p className="text-xs text-zinc-400 mt-0.5">
            {fmtDate(act[0])} ·{" "}
            <span style={{ color }} className="font-mono font-semibold">
              {up ? "▲" : "▼"} %{nf.format(Math.abs(change))}
            </span>{" "}
            <span>({RANGES.find((r) => r.id === range)!.label} değişim)</span>
          </p>
        </div>
        <div className="flex gap-1" role="group" aria-label="Zaman aralığı">
          {RANGES.map((r) => (
            <button
              key={r.id}
              type="button"
              aria-pressed={range === r.id}
              onClick={() => {
                setRange(r.id);
                setHover(null);
              }}
              className={`px-3 py-1.5 rounded-lg text-xs border transition-colors ${
                range === r.id ? "bg-amber-500/15 border-amber-500/50 text-amber-300" : "bg-zinc-900 border-zinc-800 text-zinc-400 hover:text-white"
              }`}
            >
              {r.label}
            </button>
          ))}
        </div>
      </div>

      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="w-full h-auto touch-pan-y"
        role="img"
        aria-label={`${ticker} haftalık kapanış fiyatı, ${fmtDate(pts[0][0])} – ${fmtDate(pts[pts.length - 1][0])}: ${nf.format(first)} ₺'den ${nf.format(last)} ₺'ye, en düşük ${nf.format(lo)}, en yüksek ${nf.format(hi)}`}
        onPointerMove={onMove}
        onPointerLeave={() => setHover(null)}
      >
        <defs>
          <linearGradient id={`pc-${ticker}`} x1="0" x2="0" y1="0" y2="1">
            <stop offset="0%" stopColor={color} stopOpacity="0.25" />
            <stop offset="100%" stopColor={color} stopOpacity="0" />
          </linearGradient>
        </defs>
        {ticks.map((t, i) => (
          <g key={i}>
            <line x1={PL} x2={W - PR} y1={y(t)} y2={y(t)} stroke="#27272a" strokeDasharray="3 4" />
            <text x={W - PR + 6} y={y(t) + 3} fontSize="12" fill="#a1a1aa" fontFamily="monospace">
              {nf.format(t)}
            </text>
          </g>
        ))}
        <path d={area} fill={`url(#pc-${ticker})`} />
        <path d={line} fill="none" stroke={color} strokeWidth="2" strokeLinejoin="round" />
        <text x={PL} y={H - 8} fontSize="12" fill="#a1a1aa" fontFamily="monospace">
          {fmtDate(pts[0][0])}
        </text>
        <text x={W - PR} y={H - 8} fontSize="12" fill="#a1a1aa" fontFamily="monospace" textAnchor="end">
          {fmtDate(pts[pts.length - 1][0])}
        </text>
        {hover !== null && (
          <g>
            <line x1={x(hover)} x2={x(hover)} y1={PT} y2={H - PB} stroke="#52525b" />
            <circle cx={x(hover)} cy={y(pts[hover][1])} r="4" style={{ fill: "var(--background)" }} stroke={color} strokeWidth="2" />
          </g>
        )}
      </svg>
      <p className="mt-2 text-xs text-zinc-400">
        Haftalık kapanış fiyatları, Yahoo Finance. Bölünme (bedelsiz) düzeltmeli, temettü düzeltmesiz. Gün içi fiyat değildir.
      </p>
    </div>
  );
}
