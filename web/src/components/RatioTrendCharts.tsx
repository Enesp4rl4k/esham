import { LineChart } from "lucide-react";

export interface QuarterPoint {
  date: string;
  gross_margin: number | null;
  ebitda_margin: number | null;
  net_margin: number | null;
  current_ratio: number | null;
  leverage: number | null;
  roe_annualized: number | null;
}

type Unit = "%" | "x";
const CHARTS: { key: keyof Omit<QuarterPoint, "date">; title: string; unit: Unit; color: string; note?: string }[] = [
  { key: "gross_margin", title: "Brüt Kâr Marjı (Çeyreklik)", unit: "%", color: "#38bdf8" },
  { key: "ebitda_margin", title: "FAVÖK Marjı (Çeyreklik)", unit: "%", color: "#a78bfa" },
  { key: "net_margin", title: "Net Kâr Marjı (Çeyreklik)", unit: "%", color: "#34d399" },
  { key: "current_ratio", title: "Cari Oran", unit: "x", color: "#fb923c" },
  { key: "leverage", title: "Kaldıraç Oranı", unit: "%", color: "#f472b6", note: "Toplam yükümlülük / toplam aktif" },
  { key: "roe_annualized", title: "Özkaynak Karlılığı", unit: "%", color: "#e8a030", note: "Çeyrek net kâr × 4 / özkaynak" },
];

const nf = new Intl.NumberFormat("tr-TR", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
const fmt = (v: number, u: Unit) => (u === "%" ? `%${nf.format(v)}` : `${nf.format(v)}x`);
const label = (d: string) => {
  const [y, m] = d.split("-");
  return `${y}/${Number(m)}`;
};

const W = 320, H = 150, PL = 16, PR = 40, PT = 14, PB = 22;

function MiniChart({ pts, unit, color }: { pts: { date: string; v: number | null }[]; unit: Unit; color: string }) {
  const vals = pts.map((p) => p.v).filter((v): v is number => v !== null);
  let lo = Math.min(...vals), hi = Math.max(...vals);
  if (hi === lo) { hi += 1; lo -= 1; }
  const pad = (hi - lo) * 0.12;
  lo -= pad; hi += pad;
  const x = (i: number) => PL + (pts.length === 1 ? (W - PL - PR) / 2 : (i * (W - PL - PR)) / (pts.length - 1));
  const y = (v: number) => PT + ((hi - v) / (hi - lo)) * (H - PT - PB);
  const ticks = [hi - pad, (hi + lo) / 2, lo + pad];
  // boşlukları (null) bölerek çiz
  const segs: string[] = [];
  let cur = "";
  pts.forEach((p, i) => {
    if (p.v === null) { if (cur) segs.push(cur); cur = ""; return; }
    cur += `${cur ? "L" : "M"}${x(i).toFixed(1)},${y(p.v).toFixed(1)}`;
  });
  if (cur) segs.push(cur);

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-auto" role="img" aria-label="Çeyreklik trend grafiği">
      {ticks.map((t, i) => (
        <g key={i}>
          <line x1={PL} x2={W - PR} y1={y(t)} y2={y(t)} stroke="#27272a" strokeDasharray="3 4" />
          <text x={W - PR + 6} y={y(t) + 3} fontSize="9" fill="#71717a" fontFamily="monospace">{nf.format(t)}</text>
        </g>
      ))}
      {lo < 0 && hi > 0 && <line x1={PL} x2={W - PR} y1={y(0)} y2={y(0)} stroke="#52525b" />}
      {segs.map((d, i) => <path key={i} d={d} fill="none" stroke={color} strokeWidth="2" strokeLinejoin="round" />)}
      {pts.map((p, i) =>
        p.v === null ? null : (
          <circle key={i} cx={x(i)} cy={y(p.v)} r="3.5" fill="#0a0a0a" stroke={color} strokeWidth="2">
            <title>{`${label(p.date)}: ${fmt(p.v, unit)}`}</title>
          </circle>
        ),
      )}
      {pts.map((p, i) => (
        <text key={i} x={x(i)} y={H - 6} fontSize="9" textAnchor="middle" fill="#71717a" fontFamily="monospace">
          {label(p.date)}
        </text>
      ))}
    </svg>
  );
}

export function RatioTrendCharts({ data, sector }: { data: QuarterPoint[]; sector?: string }) {
  const rows = data.slice(-8);
  const cards = CHARTS.map((c) => {
    const all = rows.map((r) => ({ date: r.date, v: r[c.key] }));
    const first = all.findIndex((p) => p.v !== null);
    const pts = first < 0 ? [] : all.slice(first); // baştaki boş çeyrekleri kırp
    const have = pts.filter((p) => p.v !== null);
    return { ...c, pts, have };
  }).filter((c) => c.have.length >= 2); // < 2 nokta = trend yok (örn. bankalarda brüt marj)

  if (cards.length === 0) return null;

  return (
    <div>
      <div className="flex items-center gap-2 mb-4">
        <span className="p-1.5 rounded-lg bg-sky-500/10 text-sky-400 border border-sky-500/20">
          <LineChart className="w-4 h-4" />
        </span>
        <h3 className="text-sm font-bold text-white tracking-tight">Çeyreklik Trendler</h3>
        {sector && <span className="text-[11px] text-zinc-500">· {sector}</span>}
      </div>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {cards.map((c) => {
          const last = c.have[c.have.length - 1].v as number;
          const prev = c.have.length > 1 ? (c.have[c.have.length - 2].v as number) : null;
          const delta = prev === null ? null : last - prev;
          return (
            <figure key={c.key} className="rounded-2xl border border-zinc-800 bg-zinc-950/80 p-4 m-0">
              <figcaption className="flex items-baseline justify-between gap-2 mb-1">
                <span className="text-xs font-bold text-white">{c.title}</span>
                <span className="text-sm font-mono font-bold tabular-nums" style={{ color: c.color }}>
                  {fmt(last, c.unit)}
                </span>
              </figcaption>
              <p className="text-[10px] text-zinc-500 mb-2 h-3">
                {c.note ?? ""}
                {delta !== null && (
                  <span className="ml-1">
                    {c.note ? "· " : ""}önceki çeyreğe göre {delta >= 0 ? "▲" : "▼"} {nf.format(Math.abs(delta))}
                    {c.unit === "%" ? " puan" : ""}
                  </span>
                )}
              </p>
              <MiniChart pts={c.pts} unit={c.unit} color={c.color} />
            </figure>
          );
        })}
      </div>
    </div>
  );
}
