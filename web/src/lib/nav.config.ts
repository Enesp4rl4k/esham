/** Ana menü: tek kaynak (masaüstü + mobil). Plan: Hisseler · Piyasa · Analizler. */
export interface NavLink {
  href: string;
  label: string;
  description?: string;
}
export interface NavGroup {
  key: string;
  label: string;
  /** Başlığın kendisi de bir sayfaya gider (açılır menüsüz) */
  href?: string;
  /** Başlığı etkin saymak için ek yol önekleri */
  match?: string[];
  items?: NavLink[];
}

export const NAV: NavGroup[] = [
  { key: "hisseler", label: "Hisseler", href: "/hisseler", match: ["/hisseler", "/hisse/"] },
  {
    key: "piyasa",
    label: "Piyasa",
    match: ["/piyasa", "/halka-arz-takvimi", "/tarim-emtia"],
    items: [
      { href: "/piyasa/temettu-takvimi", label: "Temettü Takvimi", description: "Kesinleşen ve teklif edilen kâr payları ve verimleri" },
      { href: "/halka-arz-takvimi", label: "Halka Arz Takvimi", description: "Taslak ve onaylı izahnameler, fiyat tespit raporları" },
      { href: "/piyasa/geri-alimlar", label: "Pay Geri Alımları", description: "KAP bildirimli geri alım programları ve maliyetleri" },
      { href: "/piyasa/devaluasyon-radari", label: "Devalüasyon Radarı", description: "Rezerv, Kapalıçarşı makası ve VİOP ima edilen faiz" },
      { href: "/tarim-emtia", label: "Emtia, Petrol & Tanker", description: "Brent, navlun, TÜRİB ve et-yem paritesi" },
      { href: "/kategori/viop", label: "VİOP & Türev", description: "Vadeli kontratlar, baz farkı ve teminatlar" },
    ],
  },
  {
    key: "analizler",
    label: "Analizler",
    match: ["/arsiv", "/kategori", "/rapor"],
    items: [
      { href: "/arsiv", label: "Tüm analizler", description: "Günlük bülten, haftalık özet ve arşiv" },
      { href: "/kategori/bist", label: "BIST & Sektör" },
      { href: "/kategori/global", label: "Küresel Makro" },
      { href: "/kategori/gundem", label: "Ekonomi & Gündem" },
      { href: "/kategori/kripto", label: "Kripto Varlıklar" },
      { href: "/kategori/teknoloji", label: "Teknoloji & Girişim" },
    ],
  },
];

export function isGroupActive(g: NavGroup, pathname: string): boolean {
  const prefixes = [...(g.match ?? []), ...(g.href ? [g.href] : []), ...(g.items?.map((i) => i.href.split("?")[0]) ?? [])];
  return prefixes.some((p) => pathname === p || pathname.startsWith(p.endsWith("/") ? p : p + "/") || pathname.startsWith(p));
}
