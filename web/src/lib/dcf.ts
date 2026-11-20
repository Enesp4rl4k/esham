/**
 * İndirgenmiş nakit akışı (DCF) hesabı — saf fonksiyonlar, bağımlılık yok.
 *
 * Model REEL terimlerle çalışır: nakit akışı bugünkü alım gücüyle, iskonto oranı reel. Böylece
 * enflasyon tahminine bağımlılık kalkar (TL'de nominal model iki belirsiz varsayım ister).
 * Yıl sonu nakit akışı kabulü; ilk yıl büyümesi 5. yılda uç büyümeye doğrusal iner.
 */
export interface DcfInputs {
  baseFcf: number; // son 12 ay baz nakit akışı (raporlama para biriminde)
  growth1: number; // 1. yıl büyümesi, ondalık (0.06 = %6)
  terminalGrowth: number; // uç büyüme, ondalık
  wacc: number; // reel iskonto oranı, ondalık
  netDebt: number; // net borç (negatifse net nakit)
  shares: number; // hisse adedi
  years?: number;
}

export interface DcfProjection {
  year: number;
  growth: number;
  fcf: number;
  pv: number;
}

export interface DcfResult {
  projections: DcfProjection[];
  pvFcf: number;
  terminalValue: number;
  pvTerminal: number;
  enterpriseValue: number;
  equityValue: number;
  perShare: number;
  terminalShare: number; // uç değerin firma değerindeki payı (0-1)
}

export function dcf(i: DcfInputs): DcfResult | null {
  const years = i.years ?? 5;
  if (!(i.shares > 0) || !(i.wacc > i.terminalGrowth) || !Number.isFinite(i.baseFcf) || i.baseFcf <= 0) return null;

  const projections: DcfProjection[] = [];
  let fcf = i.baseFcf;
  let pvFcf = 0;
  for (let t = 1; t <= years; t++) {
    const g = years === 1 ? i.terminalGrowth : i.growth1 + ((i.terminalGrowth - i.growth1) * (t - 1)) / (years - 1);
    fcf *= 1 + g;
    const pv = fcf / Math.pow(1 + i.wacc, t);
    pvFcf += pv;
    projections.push({ year: t, growth: g, fcf, pv });
  }
  const terminalValue = (fcf * (1 + i.terminalGrowth)) / (i.wacc - i.terminalGrowth);
  const pvTerminal = terminalValue / Math.pow(1 + i.wacc, years);
  const enterpriseValue = pvFcf + pvTerminal;
  const equityValue = enterpriseValue - i.netDebt;
  return {
    projections,
    pvFcf,
    terminalValue,
    pvTerminal,
    enterpriseValue,
    equityValue,
    perShare: equityValue / i.shares,
    terminalShare: pvTerminal / enterpriseValue,
  };
}

/** WACC × uç büyüme duyarlılık tablosu (hisse başı değer, raporlama para biriminde). null = geçersiz hücre. */
export function sensitivity(
  base: Omit<DcfInputs, "wacc" | "terminalGrowth">,
  wacc: number,
  terminalGrowth: number,
  waccSteps = [-0.04, -0.02, 0, 0.02, 0.04],
  growthSteps = [-0.02, -0.01, 0, 0.01, 0.02],
): { waccs: number[]; growths: number[]; values: (number | null)[][] } {
  const waccs = waccSteps.map((s) => wacc + s);
  const growths = growthSteps.map((s) => terminalGrowth + s);
  const values = waccs.map((w) => growths.map((g) => dcf({ ...base, wacc: w, terminalGrowth: g })?.perShare ?? null));
  return { waccs, growths, values };
}

export interface BaseChoice {
  key: "fcf" | "net_income";
  label: string;
  value: number | null;
}

/** Varsayılan baz nakit akışı: SNA pozitifse SNA, değilse pozitif net kâr, ikisi de değilse null. */
export function defaultBase(fcf: number | null, netIncome: number | null): BaseChoice["key"] | null {
  if (fcf !== null && fcf > 0) return "fcf";
  if (netIncome !== null && netIncome > 0) return "net_income";
  return null;
}

export interface Defaults {
  wacc: number;
  growth1: number;
  terminalGrowth: number;
}

/** Reel varsayılanlar: dövizli (USD/EUR) raporlayanlarda daha düşük iskonto oranı. */
export function defaultAssumptions(currency: string): Defaults {
  const hard = currency !== "TRY";
  return { wacc: hard ? 0.12 : 0.14, growth1: 0.06, terminalGrowth: 0.03 };
}

export const SCENARIOS: Record<"cons" | "base" | "opt", { label: string; dWacc: number; dG1: number; dGT: number }> = {
  cons: { label: "Temkinli", dWacc: +0.02, dG1: -0.03, dGT: -0.01 },
  base: { label: "Baz", dWacc: 0, dG1: 0, dGT: 0 },
  opt: { label: "İyimser", dWacc: -0.02, dG1: +0.03, dGT: +0.01 },
};
