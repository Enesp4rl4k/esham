/**
 * /tarim-emtia veri setini istemciye vermeden ÖNCE tarafsızlaştırır.
 *
 * Bot artık "fırsat"/"kâr kalır"/marj yorumu üretmiyor (bkz. bot/esham/sources/regional_arbitrage.py,
 * agri_bist.py), ancak mevcut `public/data/turib-market.json` eski metinleri taşıyabilir. Sayfa yüküne
 * (RSC) giden veride bu metinler kalmasın diye:
 * - arbitraj sınıfı tarafsız etikete çevrilir, serbest metin açıklamalar (`notes`, `evaluation`) atılır;
 * - şirket satırlarındaki `commentary` atılır, `marginPressure` yalnız fiyat yönünü söyler;
 * - `macroTakeaway` (tahmin cümlesi içerebiliyordu) atılır.
 * Sayılar olduğu gibi kalır; yeni metin üretilmez.
 */
type Opp = { opportunityLevel?: string; notes?: string; commodityChange?: string };
type Company = { marginPressure?: string; commentary?: string; commodityChange?: string };

export function arbitrageLevelLabel(level: string | undefined): string {
  if (level === "NET_FARK_0_50_USTU" || level === "YUKSEK_FIRSAT") return "Net fark > 0,50 ₺/kg";
  if (level === "NET_FARK_POZITIF" || level === "SINIRLI_FIRSAT") return "Net fark 0–0,50 ₺/kg";
  return "Net fark yok";
}

export function inputPriceLabel(change: string | undefined): string {
  const n = parseFloat(String(change ?? "").replace("%", "").replace(",", "."));
  if (Number.isNaN(n)) return "Veri yok";
  return n > 0 ? "Girdi fiyatı yükseldi" : n < 0 ? "Girdi fiyatı düştü" : "Girdi fiyatı yatay";
}

export function neutralizeTuribDataset<
  T extends { regionalArbitrage?: { evaluation?: string; opportunities?: Opp[] }; agriBist?: { macroTakeaway?: string; companies?: Company[] } },
>(d: T): T {
  const ra = d.regionalArbitrage;
  const ab = d.agriBist;
  return {
    ...d,
    regionalArbitrage: ra && {
      ...ra,
      evaluation: undefined,
      opportunities: (ra.opportunities ?? []).map((o) => ({
        ...o,
        opportunityLevel: arbitrageLevelLabel(o.opportunityLevel),
        notes: "",
      })),
    },
    agriBist: ab && {
      ...ab,
      macroTakeaway: undefined,
      companies: (ab.companies ?? []).map((c) => ({
        ...c,
        marginPressure: inputPriceLabel(c.commodityChange),
        commentary: "",
      })),
    },
  };
}
