// Veri grafikleri: her veri kümesi için kart sahnelerini (JSON) yazar; PNG'yi bot/esham/publishing/veri_cards.py çizer.
// Kullanım: node scripts/veri-scenes.mjs <çıkış klasörü> [--all-variants]
//   Varsayılan: yalnız yayımlanan varyant (DEFAULT_VARIANT) × kart boyutları.
//   --all-variants: taslaklar için tüm görsel varyantlar.
// Dosya adı: <slug>__<boyut>__<varyant>.scene.json; içerik sceneJson(scene) — kartın gömülü özeti bu baytların sha256'sıdır.
import { mkdirSync, readFileSync, readdirSync, writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { CARD_SIZES, DEFAULT_VARIANT, VARIANTS, assertValid, buildScene, displayDomain, sceneJson } from "../src/lib/veri.ts";
import { SITE_URL } from "../src/lib/config.ts";

const here = path.dirname(fileURLToPath(import.meta.url));
const dataDir = path.join(here, "..", "public", "data", "veri");
const out = process.argv[2];
if (!out) {
  console.error("kullanım: node scripts/veri-scenes.mjs <çıkış klasörü> [--all-variants]");
  process.exit(2);
}
const variants = process.argv.includes("--all-variants") ? Object.keys(VARIANTS) : [DEFAULT_VARIANT];
mkdirSync(out, { recursive: true });
let n = 0;
for (const f of readdirSync(dataDir).filter((x) => x.endsWith(".json")).sort()) {
  const ds = assertValid(JSON.parse(readFileSync(path.join(dataDir, f), "utf8")), f);
  for (const size of CARD_SIZES) {
    for (const v of variants) {
      writeFileSync(path.join(out, `${ds.slug}__${size}__${v}.scene.json`), sceneJson(buildScene(ds, size, v, { domain: displayDomain(SITE_URL) })), "utf8");
      n++;
    }
  }
}
console.log(`${n} sahne yazıldı → ${out}`);
