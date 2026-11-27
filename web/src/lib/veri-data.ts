import fs from "node:fs";
import path from "node:path";
import { CARD_SIZES, assertValid, cardPath, type SizeKey, type VeriDataset } from "./veri";

/**
 * Veri kümelerini derleme anında okur ve DOĞRULAR: geçersiz bir dosya derlemeyi durdurur (sessizce yayımlanmaz).
 * Dosyalar: web/public/data/veri/<slug>.json (bot/esham/jobs/publish_veri_*.py yazar).
 */
const DATA_DIR = path.join(process.cwd(), "public", "data", "veri");
const PUBLIC_DIR = path.join(process.cwd(), "public");

let cache: VeriDataset[] | null = null;

export function loadDatasets(): VeriDataset[] {
  if (cache) return cache;
  if (!fs.existsSync(DATA_DIR)) return (cache = []);
  const out = fs
    .readdirSync(DATA_DIR)
    .filter((f) => f.endsWith(".json"))
    .sort((a, b) => a.localeCompare(b))
    .map((f) => {
      const ds = assertValid(JSON.parse(fs.readFileSync(path.join(DATA_DIR, f), "utf8")), `public/data/veri/${f}`);
      if (`${ds.slug}.json` !== f) throw new Error(`public/data/veri/${f}: dosya adı slug ile aynı olmalı (${ds.slug})`);
      return ds;
    });
  return (cache = out);
}

export function getDataset(slug: string): VeriDataset | null {
  return loadDatasets().find((d) => d.slug === slug) ?? null;
}

/** Yayımlanmış kart PNG'leri (yalnız var olanlar). */
export function publishedCards(slug: string): { size: SizeKey; url: string; width: number; height: number }[] {
  return CARD_SIZES.filter((s) => fs.existsSync(path.join(PUBLIC_DIR, cardPath(slug, s)))).map((s) => {
    const [width, height] = s.split("x").map(Number);
    return { size: s, url: cardPath(slug, s), width, height };
  });
}
