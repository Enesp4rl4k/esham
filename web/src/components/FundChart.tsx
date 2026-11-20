"use client";

import { useMemo, useState } from "react";

type Point = [string, number]; // [ISO tarih, kapanış]
// Günlük seri (son 1 yıl tam, eskisi seyreltilmiş): aralık takvim günüyle kesilir.
const RANGES = [
  { id: "3A", label: "3 Ay", days: 92 },
  { id: "6A", label: "6 Ay", days: 183 },
  { id: "1Y", label: "1 Yıl", days: 366 },
  { id: "3Y", label: "3 Yıl", days: 1096 },
  { id: "5Y", label: "5 Yıl", days: 99999 },
] as const;

const W = 800, H = 280, PL = 8, PR = 52, PT = 16, PB = 26;
const nf = new Intl.NumberFormat("tr-TR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const nf6 = new Intl.NumberFormat("tr-TR", { minimumFractionDigits: 4, maximumFractionDigits: 6 });
const fmtDate = (d: string) => new Date(d).toLocaleDateString("tr-TR", { day: "numeric", month: "short", year: "numeric" });

/** Fon birim fiyat grafiği (bot: `esham funds` → fon JSON'undaki `prices`). Sentetik veri yok. */
export function FundChart({ code, series }: { code: string; series: Point[] }) {
  const [range, setRange] = useState<(typeof RANGES)[number]["id"]>("1Y");
  const [hover, setHover] = useState<number | null>(null);

  const pts = useMemo(() => {
    if (series.length === 0) return [];
    const last = new Date(series[series.length - 1][0]).getTime();
    const cut = last - RANGES.find((r) => r.id === range)!.days * 86400000;
    return series.filter((p) => new Date(p[0]).getTime() >= cut);
  }, [series, range]);

  if (pts.length < 2)
    return (
      <div className="rounded-2xl border border-zinc-800 bg-zinc-950/80 p-6 text-sm text-zinc-400">Bu fon için fiyat geçmişi henüz yok.</div>
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
          <p className="font-mono text-2xl font-bold text-white tabular-nums">{nf6.format(act[1])} ₺</p>
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
        aria-label={`${code} birim fiyatı, ${fmtDate(pts[0][0])} – ${fmtDate(pts[pts.length - 1][0])}: ${nf6.format(first)} ₺'den ${nf6.format(last)} ₺'ye`}
        onPointerMove={onMove}
        onPointerLeave={() => setHover(null)}
      >
        <defs>
          <linearGradient id={`pc-${code}`} x1="0" x2="0" y1="0" y2="1">
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
        <path d={area} fill={`url(#pc-${code})`} />
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
        Günlük birim fiyat (TEFAS). Son 1 yıl günlük, daha eski dönem seyreltilmiş örnektir. Geçmiş performans gelecekteki getiriyi garanti etmez.
      </p>
    </div>
  );
}
