/**
 * NAV (net aktif değer) hesabı — saf fonksiyonlar.
 *
 * NAV = Σ (doğrudan pay × iştirakin piyasa değeri) + listelenmeyen iştiraklerin değeri − holding net borcu.
 * Yalnızca KAP'taki DOĞRUDAN paylar bilinir; ara holdingler üzerinden gelen dolaylı paylar dâhil değildir,
 * bu yüzden varsayılan sonuç "kısmi NAV"dir (listelenmeyen değer girilmediği sürece).
 */
export interface Stake {
  title: string;
  pct: number; // %
  relation: string;
  ticker: string | null; // borsada işlem görüyorsa
  mcap: number | null; // iştirakin piyasa değeri (TL); bilinmiyorsa null
}

export interface NavInputs {
  stakes: Stake[];
  holdingMcap: number; // TL
  price: number; // TL
  unlistedValue: number; // TL, kullanıcı girdisi
  netDebt: number; // TL, holding düzeyi, kullanıcı girdisi (negatif = net nakit)
}

export interface NavResult {
  listedValue: number;
  valuedStakes: number; // piyasa değeri bilinen listelenmiş pay sayısı
  unvaluedStakes: number; // değeri bilinmeyen (listelenmemiş / evren dışı) pay sayısı
  nav: number;
  navPerShare: number;
  shares: number;
  /** price / navPerShare − 1 (negatif = iskonto). NAV ≤ 0 ise null. */
  discount: number | null;
  /** listelenmiş doğrudan payların değerinin holding piyasa değerine oranı */
  coverage: number;
}

export function stakeValue(s: Stake): number | null {
  return s.mcap === null ? null : (s.pct / 100) * s.mcap;
}

export function nav(i: NavInputs): NavResult | null {
  if (!(i.price > 0) || !(i.holdingMcap > 0)) return null;
  let listedValue = 0;
  let valued = 0;
  let unvalued = 0;
  for (const s of i.stakes) {
    const v = stakeValue(s);
    if (v === null) unvalued++;
    else {
      listedValue += v;
      valued++;
    }
  }
  const navTotal = listedValue + i.unlistedValue - i.netDebt;
  const shares = i.holdingMcap / i.price;
  const navPerShare = navTotal / shares;
  return {
    listedValue,
    valuedStakes: valued,
    unvaluedStakes: unvalued,
    nav: navTotal,
    navPerShare,
    shares,
    discount: navPerShare > 0 ? i.price / navPerShare - 1 : null,
    coverage: listedValue / i.holdingMcap,
  };
}
