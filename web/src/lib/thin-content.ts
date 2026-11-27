/**
 * İnce içerik kapısı (PRODUCT_SEO_PLAN.md §5.3 "Kalite kapısı").
 *
 * KURAL (tek yer): bir rapor ancak ŞU İKİ koşul birlikte sağlanıyorsa "ince"dir:
 *   1. gövde `THIN_WORD_MIN` (300) sözcükten kısa, VE
 *   2. veri içeriği yok: gövdede markdown tablosu yok ve yapılandırılmış
 *      finansal alan (`ipo` meta verisi) yok.
 * İnce raporlar `noindex, follow` olur; sitemap ve RSS'ten çıkar, ama bağlantıyla
 * erişilebilir kalır. Hisse, fon, sektör, tarama, karşılaştırma ve yasal sayfalar
 * bu kuralın kapsamında DEĞİLDİR (yalnızca `/rapor/*`).
 *
 * Eşik 300: 1.777 raporun sözcük dağılımı iki kümelidir (<150 sözcük: 1.000,
 * 300-700: ~690); 150-300 arası yalnızca 33 rapor içerir, yani eşik doğal
 * vadidedir ve planın "300 kelime" ölçütüyle örtüşür.
 */
export const THIN_WORD_MIN = 300;

export interface ThinCheckInput {
  body: string;
  ipo?: unknown;
}

export function wordCount(body: string): number {
  const t = body.trim();
  return t ? t.split(/\s+/).length : 0;
}

/** Markdown tablo ayırıcı satırı (`| --- | :---: |`) var mı. */
export function hasDataTable(body: string): boolean {
  return /^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$/m.test(body);
}

export function isThinReport(r: ThinCheckInput): boolean {
  if (wordCount(r.body) >= THIN_WORD_MIN) return false;
  if (r.ipo) return false;
  if (hasDataTable(r.body)) return false;
  return true;
}

/**
 * Dizin kararı TEK fonksiyon (rapor sayfası robots, sitemap ve RSS bunu kullanır; bkz. content.ts):
 * yalın görünümdeki eski kayıt (`legacyMinimal`) ⇒ noindex ⇒ sitemap/RSS dışı. Eski halka arz kayıtlarının
 * `ipo` meta verisi ince içerik kuralını atlatıyordu; yalın görünüm kararı önce gelir.
 */
export function isIndexable(r: ThinCheckInput & { legacyMinimal?: boolean }): boolean {
  if (r.legacyMinimal) return false;
  return !isThinReport(r);
}
