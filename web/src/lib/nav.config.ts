/** Ana menü: tek kaynak (masaüstü + mobil). Hisseler · Fonlar · Piyasa · Analizler. */
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
  { key: "fonlar", label: "Fonlar", href: "/fonlar", match: ["/fonlar", "/fon/"] },
  {
    key: "piyasa",
    label: "Piyasa",
    match: ["/halka-arz-takvimi", "/tarim-emtia", "/piyasa"],
    items: [
      { href: "/halka-arz-takvimi", label: "Halka Arz Takvimi", description: "Taslak ve onaylı izahnameler, fiyat tespit raporları" },
      { href: "/tarim-emtia", label: "Emtia, Petrol & Tanker", description: "Brent, İstanbul Boğazı geçişleri, TÜRİB ve TMO fiyatları" },
      { href: "/piyasa/temettu-takvimi", label: "Kâr Payı Takvimi", description: "KAP bildirimlerinden hak kullanım ve ödeme tarihleri" },
      { href: "/piyasa/geri-alimlar", label: "Pay Geri Alımları", description: "KAP bildirimlerinden işlem, fiyat ve program limiti" },
      { href: "/piyasa/makro-gostergeler", label: "Makro Göstergeler", description: "TCMB faiz, USD/TRY değişimi; kaynak ve tarihleriyle" },
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
