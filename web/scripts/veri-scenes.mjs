// Veri grafikleri: her veri kümesi için kart sahnelerini (JSON) yazar; PNG'yi bot/esham/publishing/veri_cards.py çizer.
// Kullanım: node scripts/veri-scenes.mjs [--all-variants]
//   Varsayılan: yalnız yayımlanan varyant (DEFAULT_VARIANT) × kart boyutları → web/.veri-scenes/yayin/
//   --all-variants: taslaklar için tüm görsel varyantlar → web/.veri-scenes/taslak/
// Klasör sabittir (git dışı); komut satırından yol alınmaz. Her çalıştırmada klasördeki eski *.scene.json dosyaları silinir.
// Dosya adı: <slug>__<boyut>__<varyant>.scene.json; içerik sceneJson(scene) — kartın gömülü özeti bu baytların sha256'sıdır.
import { mkdirSync, readFileSync, readdirSync, unlinkSync, writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { CARD_SIZES, DEFAULT_VARIANT, VARIANTS, assertValid, buildScene, displayDomain, sceneJson } from "../src/lib/veri.ts";
import { SITE_URL } from "../src/lib/config.ts";

const here = path.dirname(fileURLToPath(import.meta.url));
const web = path.join(here, "..");
const dataDir = path.join(web, "public", "data", "veri");
const all = process.argv.includes("--all-variants");
const out = path.join(web, ".veri-scenes", all ? "taslak" : "yayin");
const variants = all ? Object.keys(VARIANTS) : [DEFAULT_VARIANT];
mkdirSync(out, { recursive: true });
for (const f of readdirSync(out)) if (f.endsWith(".scene.json")) unlinkSync(path.join(out, f));
let n = 0;
for (const f of readdirSync(dataDir).filter((x) => x.endsWith(".json")).sort((a, b) => a.localeCompare(b))) {
  const ds = assertValid(JSON.parse(readFileSync(path.join(dataDir, f), "utf8")), f);
  for (const size of CARD_SIZES) {
    for (const v of variants) {
      writeFileSync(path.join(out, `${ds.slug}__${size}__${v}.scene.json`), sceneJson(buildScene(ds, size, v, { domain: displayDomain(SITE_URL) })), "utf8");
      n++;
    }
  }
}
console.log(`${n} sahne yazıldı → ${out}`);
