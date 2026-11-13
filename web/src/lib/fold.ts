/** Türkçe-duyarsız karşılaştırma: İ/ı/ş/ğ/ü/ö/ç → ASCII, küçük harf. */
export function fold(s: string): string {
  return s
    .replace(/İ/g, "i")
    .replace(/I/g, "i")
    .toLowerCase()
    .replace(/ı/g, "i")
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "");
}
