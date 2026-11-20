// `npm run build` sonrası: segment dosyalarını buda, dosya bütçesini denetle.
// Bütçe aşılırsa çıkış kodu 1: CI ve dağıtım başarısız olur (sessiz kırılma yok).
import { appendFileSync, existsSync } from "node:fs";
import { FAIL_AT, FILE_LIMIT, WARN_AT, breakdown, countFiles, pruneSegments } from "./export-tools.mjs";

const out = process.argv[2] ?? "out";
if (!existsSync(out)) {
  console.error(`✖ ${out}/ yok: önce \`next build\` çalışmalı`);
  process.exit(1);
}

const before = countFiles(out);
const removed = process.env.NO_PRUNE ? 0 : pruneSegments(out);
const total = countFiles(out);
const { dirs, rootFiles } = breakdown(out);

const lines = [
  `Statik çıktı: ${total.toLocaleString("tr-TR")} dosya (limit ${FILE_LIMIT.toLocaleString("tr-TR")}, uyarı ${WARN_AT.toLocaleString("tr-TR")}, hata ${FAIL_AT.toLocaleString("tr-TR")})`,
  removed ? `Budama: ${before.toLocaleString("tr-TR")} → ${total.toLocaleString("tr-TR")} (${removed.toLocaleString("tr-TR")} segment dosyası silindi)` : "Budama yok",
  "En kalabalık klasörler: " + dirs.slice(0, 5).map(([n, c]) => `${n}=${c}`).join(", ") + `, kök=${rootFiles}`,
];
console.log(lines.join("\n"));

// GitHub Actions özetine de yaz
if (process.env.GITHUB_STEP_SUMMARY) {
  appendFileSync(process.env.GITHUB_STEP_SUMMARY, "### Statik çıktı bütçesi\n\n" + lines.map((l) => `- ${l}`).join("\n") + "\n");
}

if (total >= FAIL_AT) {
  console.error(`✖ Dosya bütçesi aşıldı (${total} ≥ ${FAIL_AT}). Cloudflare Pages ${FILE_LIMIT} dosyada dağıtımı reddeder.`);
  process.exit(1);
}
if (total >= WARN_AT) {
  console.warn(`⚠ Dosya bütçesi ${WARN_AT}'i geçti (${total}). Eski raporları arşiv sayfasına taşımayı planlayın.`);
  if (process.env.GITHUB_ACTIONS) console.log(`::warning title=Dosya bütçesi::Statik çıktı ${total} dosya (limit ${FILE_LIMIT})`);
}
