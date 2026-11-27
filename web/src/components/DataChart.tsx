"use client";

import { useId, useState, type KeyboardEvent, type PointerEvent } from "react";
import { PALETTES, fmtNumber, type ColorToken, type Scene, type SceneItem } from "@/lib/veri";

/**
 * Veri grafiği: `buildScene` sahnesini SVG olarak çizer (PNG kartıyla aynı sahne; bkz. lib/veri.ts).
 * Renkler CSS değişkenleriyle verilir, böylece sitenin açık/koyu teması değişince grafik de değişir; geometri ve metin aynıdır.
 * Etkileşim: fare/dokunma ile ya da odaklanıp ←/→ (Home/End) ile bir dönem seçilir; seçilen dönemin değerleri grafiğin
 * altında yazılır (aria-live). Grafik metin alternatifi ve tam veri tablosu sayfada ayrıca bulunur.
 */

const v = (t: ColorToken) => `var(--vc-${t})`;
const vars = (theme: "dark" | "light") =>
  Object.entries(PALETTES[theme])
    .map(([k, c]) => `--vc-${k}:${c}`)
    .join(";");
export const CHART_CSS = `.veri-chart{${vars("dark")}}html[data-theme="light"] .veri-chart{${vars("light")}}`;

const FONT: Record<string, { family: string; weight: number }> = {
  display: { family: "var(--font-outfit), Outfit, sans-serif", weight: 700 },
  body: { family: "var(--font-inter), Inter, sans-serif", weight: 400 },
  bodyBold: { family: "var(--font-inter), Inter, sans-serif", weight: 700 },
};

function Item({ it }: { it: SceneItem }) {
  switch (it.k) {
    case "rect":
      return <rect x={it.x} y={it.y} width={it.w} height={it.h} rx={it.rx} style={{ fill: v(it.fill) }} />;
    case "line":
      return (
        <line x1={it.x1} y1={it.y1} x2={it.x2} y2={it.y2} strokeDasharray={it.dash?.join(" ")} style={{ stroke: v(it.stroke), strokeWidth: it.sw }} />
      );
    case "path":
      return (
        <polyline
          points={it.pts.map((p) => p.join(",")).join(" ")}
          fill="none"
          strokeLinejoin="round"
          strokeLinecap="round"
          style={{ stroke: v(it.stroke), strokeWidth: it.sw }}
        />
      );
    case "circle":
      return <circle cx={it.x} cy={it.y} r={it.r} style={{ fill: v(it.fill), stroke: it.stroke ? v(it.stroke) : undefined, strokeWidth: it.sw }} />;
    case "poly":
      return <polygon points={it.pts.map((p) => p.join(",")).join(" ")} style={{ fill: v(it.fill), stroke: it.stroke ? v(it.stroke) : undefined, strokeWidth: it.sw }} />;
    case "text": {
      const f = FONT[it.font];
      return (
        <text x={it.x} y={it.y} textAnchor={it.anchor} style={{ fontFamily: f.family, fontWeight: f.weight, fontSize: it.size }}>
          {it.spans.map((s, i) => (
            <tspan key={i} style={{ fill: v(s.fill), whiteSpace: "pre" }}>
              {s.text}
            </tspan>
          ))}
        </text>
      );
    }
  }
}

function SceneFigure({ scene, title, desc, decimals, className }: { scene: Scene; title: string; desc: string; decimals: number; className: string }) {
  const id = useId();
  const [idx, setIdx] = useState<number | null>(null);
  const { plot, xs, series, periodLabels, yDomain } = scene.meta;
  const Y = (val: number) => plot.y1 - ((val - yDomain[0]) / (yDomain[1] - yDomain[0])) * (plot.y1 - plot.y0);

  const pick = (e: PointerEvent<SVGSVGElement>) => {
    const svg = e.currentTarget;
    const r = svg.getBoundingClientRect();
    const x = ((e.clientX - r.left) / r.width) * scene.w;
    if (x < plot.x0 - 30 || x > plot.x1 + 30) return setIdx(null);
    let best = 0;
    xs.forEach((xx, i) => {
      if (Math.abs(xx - x) < Math.abs(xs[best] - x)) best = i;
    });
    setIdx(best);
  };
  const onKey = (e: KeyboardEvent<HTMLElement>) => {
    const last = xs.length - 1;
    const cur = idx ?? last;
    const next = e.key === "ArrowLeft" ? Math.max(0, cur - 1) : e.key === "ArrowRight" ? Math.min(last, cur + 1) : e.key === "Home" ? 0 : e.key === "End" ? last : null;
    if (next === null) return;
    e.preventDefault();
    setIdx(next);
  };

  return (
    <figure className={className} tabIndex={0} onKeyDown={onKey} aria-describedby={`${id}-live`}>
      <svg
        viewBox={`0 0 ${scene.w} ${scene.h}`}
        role="img"
        aria-labelledby={`${id}-t ${id}-d`}
        className="w-full h-auto rounded-xl border border-zinc-800 touch-pan-y select-none"
        onPointerMove={pick}
        onPointerDown={pick}
        onPointerLeave={() => setIdx(null)}
      >
        <title id={`${id}-t`}>{title}</title>
        <desc id={`${id}-d`}>{desc}</desc>
        {scene.items.map((it, i) => (
          <Item key={i} it={it} />
        ))}
        {idx !== null && (
          <g aria-hidden="true">
            <line x1={xs[idx]} x2={xs[idx]} y1={plot.y0} y2={plot.y1} style={{ stroke: v("muted"), strokeWidth: 1.5 }} strokeDasharray="6 6" />
            {series.map((s) =>
              s.values[idx] === null ? null : (
                <circle key={s.id} cx={xs[idx]} cy={Y(s.values[idx] as number)} r={7} style={{ fill: v(s.color), stroke: v("bg"), strokeWidth: 2.5 }} />
              ),
            )}
          </g>
        )}
      </svg>
      <figcaption id={`${id}-live`} aria-live="polite" className="mt-2 min-h-[3rem] text-sm text-zinc-300 leading-relaxed">
        {idx === null ? (
          <span className="text-zinc-400">Bir dönemin değerlerini görmek için grafiğin üzerine gelin ya da grafiğe odaklanıp ← / → tuşlarını kullanın.</span>
        ) : (
          <>
            <strong className="text-zinc-100">{periodLabels[idx]}:</strong>{" "}
            {series.map((s, i) => (
              <span key={s.id}>
                {i > 0 && " · "}
                <span className="inline-block w-2.5 h-2.5 rounded-full mr-1 align-middle" style={{ background: v(s.color) }} aria-hidden="true" />
                {s.label} {s.values[idx] === null ? "veri yok" : fmtNumber(s.values[idx] as number, decimals)}
              </span>
            ))}
          </>
        )}
      </figcaption>
    </figure>
  );
}

export function DataChart({ wide, tall, title, desc, decimals }: { wide: Scene; tall: Scene; title: string; desc: string; decimals: number }) {
  return (
    <div className="veri-chart">
      <style>{CHART_CSS}</style>
      <SceneFigure scene={wide} title={title} desc={desc} decimals={decimals} className="hidden md:block outline-none focus-visible:ring-2 focus-visible:ring-amber-400 rounded-xl" />
      <SceneFigure scene={tall} title={title} desc={desc} decimals={decimals} className="md:hidden outline-none focus-visible:ring-2 focus-visible:ring-amber-400 rounded-xl" />
    </div>
  );
}
