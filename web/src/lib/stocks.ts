/**
 * Hisse evreni okuyucu — bot'un ürettiği public/data/universe.json (sunucu tarafı, build zamanı).
 * Dosya yoksa boş döner; çağıran sayfalar zarifçe düşmelidir.
 */
import fs from "fs";
import path from "path";

export interface UniverseStock {
  ticker: string;
  name: string;
  sector: string;
  financial: boolean;
  price: number | null;
  as_of: string;
  market_cap: number | null;
  pe: number | null;
  pb: number | null;
  ev_ebitda: number | null;
  roe: number | null;
  net_margin: number | null;
  dividend_yield: number | null;
  net_debt_ebitda: number | null;
}

export interface Universe {
  updated_at: string;
  count: number;
  sector_median: Record<string, Record<string, number>>;
  stocks: UniverseStock[];
}

let cache: Universe | null | undefined;

export function loadUniverse(): Universe | null {
  if (cache !== undefined) return cache;
  try {
    const raw = fs.readFileSync(path.join(process.cwd(), "public", "data", "universe.json"), "utf-8");
    cache = JSON.parse(raw) as Universe;
  } catch {
    cache = null;
  }
  return cache;
}

export function getUniverseTickers(): string[] {
  return loadUniverse()?.stocks.map((s) => s.ticker) ?? [];
}

export function getStockName(ticker: string): string | undefined {
  return loadUniverse()?.stocks.find((s) => s.ticker === ticker)?.name;
}

export interface Leaderboard {
  title: string;
  hint: string;
  metric: keyof UniverseStock;
  unit: "x" | "%";
  rows: UniverseStock[];
}

/** Ana sayfa liderlik tabloları: anlamsız/uç değerler ve küçük şirketler elenir. */
export function buildLeaderboards(u: Universe, n = 5): Leaderboard[] {
  const big = u.stocks.filter((s) => (s.market_cap ?? 0) >= 5e9); // ≥ 5 milyar TL: illikit/uç değerleri ele
  const pick = (
    title: string,
    hint: string,
    metric: keyof UniverseStock,
    unit: "x" | "%",
    ok: (s: UniverseStock) => boolean,
    dir: 1 | -1,
  ): Leaderboard => ({
    title,
    hint,
    metric,
    unit,
    rows: big
      .filter((s) => typeof s[metric] === "number" && ok(s))
      .sort((a, b) => dir * ((a[metric] as number) - (b[metric] as number)))
      .slice(0, n),
  });
  return [
    pick("En Düşük F/K", "Kâr eden şirketler, bankalar dâhil", "pe", "x", (s) => (s.pe as number) > 0, 1),
    pick("En Yüksek ROE", "Özkaynak karlılığı, TTM", "roe", "%", (s) => (s.roe as number) < 200, -1),
    pick("En Yüksek Temettü Verimi", "Son 12 ay brüt", "dividend_yield", "%", (s) => (s.dividend_yield as number) > 0, -1),
    pick("En Düşük FD/FAVÖK", "Bankalar/sigorta hariç", "ev_ebitda", "x", (s) => !s.financial && (s.ev_ebitda as number) > 0, 1),
  ];
}
