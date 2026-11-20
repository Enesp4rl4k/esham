/** Arama sonuçlarında kesilmeyen başlık/açıklama uzunlukları. */
export const TITLE_MAX = 60;
export const DESC_MAX = 155;

/** Sözcük sınırında keser, sonuna "…" ekler; sınır içindeyse dokunmaz. */
export function truncate(text: string, max: number): string {
  const clean = text.replace(/\s+/g, " ").trim();
  if (clean.length <= max) return clean;
  const cut = clean.slice(0, max - 1);
  const lastSpace = cut.lastIndexOf(" ");
  const base = lastSpace > max * 0.6 ? cut.slice(0, lastSpace) : cut;
  return base.replace(/[\s,;:.\-–—]+$/, "") + "…";
}

export const seoTitle = (t: string) => truncate(t, TITLE_MAX);
export const seoDescription = (d: string) => truncate(d, DESC_MAX);

export const DEFAULT_OG_IMAGE = {
  url: "/cards/default-bist.png" /* metadataBase ile mutlaklaşır */,
  width: 1200,
  height: 600,
  alt: "Esham — BIST hisse analizi",
};
