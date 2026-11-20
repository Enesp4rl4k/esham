import Link from "next/link";
import { BarChart3 } from "lucide-react";
import { sectorPositions, type MetricPosition } from "@/lib/sector";
import type { UniverseStock } from "@/lib/stocks";

const nf = new Intl.NumberFormat("tr-TR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const fmt = (v: number | null, u: "x" | "%") =>
  v === null ? "—" : u === "%" ? `${v < 0 ? "−" : ""}%${nf.format(Math.abs(v))}` : `${nf.format(v)}x`;

/** Şirketin sektöründeki konumu: değer, sektör medyanı, sıra ve %10–%90 aralığında çubuk. */
export function SectorComparison({ stock, universe }: { stock: UniverseStock; universe: UniverseStock[] }) {
  const peers = universe.filter((s) => s.sector === stock.sector);
  const usable = peers.filter((s) => !s.suspect).length;
  const rows = sectorPositions(stock, universe);
  if (peers.length < 3) return null;

  return (
    <div className="rounded-2xl border border-zinc-800 bg-zinc-950/80 p-5 md:p-6 shadow-xl">
      <div className="flex flex-wrap items-center justify-between gap-3 pb-4 border-b border-zinc-800/80 mb-5">
        <div className="flex items-center gap-2">
          <span className="p-1.5 rounded-lg bg-zinc-800/80 text-zinc-200 border border-zinc-700">
            <BarChart3 className="w-4 h-4" />
          </span>
          <h3 className="text-base font-bold text-white tracking-tight">Sektörde Konum · {stock.sector}</h3>
        </div>
        <Link href={`/hisseler?sector=${encodeURIComponent(stock.sector)}`} className="text-sm text-zinc-300 hover:text-white underline-offset-4 hover:underline">
          {peers.length} hissenin tamamı
        </Link>
      </div>

      <ul className="divide-y divide-zinc-900">
        {rows.map((m) => (
          <Row key={m.def.key} m={m} />
        ))}
      </ul>

      <p className="mt-5 text-xs text-zinc-400 leading-relaxed">
        Sıra ve medyan, sektördeki {usable} hisse üzerinden hesaplanır; uç değerli ya da veri tutarsızlığı bayrağı taşıyan hisseler dâhil edilmez.
        Çubuk, sektörün %10–%90 aralığını gösterir (en uçtaki değerler kırpılır). Sektörde en az 3 geçerli değer yoksa medyan ve sıra gösterilmez.
        Zarar eden şirketlerde F/K hesaplanmaz.
      </p>
    </div>
  );
}

function Row({ m }: { m: MetricPosition }) {
  const { def } = m;
  const better =
    m.value !== null && m.median !== null && Math.abs(m.value - m.median) > 1e-9
      ? def.better === "low" ? m.value < m.median : m.value > m.median
      : null; // medyana eşit → nötr renk
  const tone = "text-zinc-100"; // renk yerine metin: yeşil/kırmızı sitede fiyat yönü demek
  const verdict = better === null ? "" : better ? " · medyandan iyi" : " · medyandan zayıf";
  const rankText = m.rank !== null ? `${m.of} hissede ${m.rank}.${verdict}` : m.value === null ? "Hesaplanamadı" : "Yetersiz veri";

  return (
    <li className="py-3.5 grid grid-cols-[7.5rem_1fr] sm:grid-cols-[9rem_1fr_9rem] items-center gap-x-4 gap-y-1.5">
      <div>
        <p className="text-sm font-medium text-zinc-100">{def.label}</p>
        <p className="text-xs text-zinc-400">{def.hint}</p>
      </div>

      <div className="order-3 sm:order-none col-span-2 sm:col-span-1" aria-hidden="true">
        <div className="relative h-2 rounded-full bg-zinc-800">
          {m.medianPos !== null && <span className="absolute top-[-3px] h-[14px] w-[2px] bg-zinc-300" style={{ left: `${m.medianPos * 100}%` }} />}
          {m.pos !== null && (
            <span
              className={`absolute top-1/2 -translate-y-1/2 -translate-x-1/2 h-4 w-4 rounded-full border-2 border-[var(--background)] bg-zinc-100`}
              style={{ left: `${m.pos * 100}%` }}
            />
          )}
        </div>
        <div className="flex justify-between mt-1 text-xs text-zinc-400 font-mono tabular-nums">
          <span>{fmt(m.min, def.unit)}</span>
          <span>{m.median !== null ? `medyan ${fmt(m.median, def.unit)}` : ""}</span>
          <span>{fmt(m.max, def.unit)}</span>
        </div>
      </div>

      <div className="text-right">
        <p className={`font-mono text-lg font-bold tabular-nums ${tone}`}>{fmt(m.value, def.unit)}</p>
        <p className="text-xs text-zinc-400">{rankText}</p>
      </div>
    </li>
  );
}
