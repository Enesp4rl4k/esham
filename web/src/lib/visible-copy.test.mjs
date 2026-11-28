import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync, readdirSync, statSync, existsSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { findBanned } from "./neutral.ts";

// Görünen metinlerde (kaynak + varsa derlenmiş çıktı) geri dönmemesi gereken ifadeler. Kalıplar ifadenin
// kendisini arar; URL slug'ları ve iç anahtarlar ("ucuz" gibi id değerleri, "dusuk-fk") yakalanmaz.
const FORBIDDEN = [
  /(düşük|yüksek)\s*=\s*(ucuz|pahalı|verimli|kârlı|fazla ödeme|az borçlu)/i,
  /yapay zeka (destekli|ile analiz|tarafından otomatik)/i,
  /yapay zekâ (destekli|ile analiz)/i,
  /medyandan (iyi|zayıf)/i,
  /daha avantajlı/i,
  /(düşük|yüksek) iyi\)/i,
  /ucuzluğa işaret|ucuzluk işareti/i,
  /Yüksek Prim Potansiyeli|Piyasada Pahalı/,
  /\bUcuz hisse(ler)?\b/i,
];

const srcRoot = fileURLToPath(new URL("../", import.meta.url));
const outRoot = fileURLToPath(new URL("../../out/", import.meta.url));

function walk(dir, accept, acc = []) {
  for (const n of readdirSync(dir)) {
    const p = join(dir, n);
    if (statSync(p).isDirectory()) walk(p, accept, acc);
    else if (accept(n)) acc.push(p);
  }
  return acc;
}

const isSource = (n) => /\.(ts|tsx)$/.test(n) && !/\.test\./.test(n);

function hits(files) {
  const out = [];
  for (const f of files) {
    const txt = readFileSync(f, "utf-8");
    for (const rx of FORBIDDEN) {
      const m = rx.exec(txt);
      if (m) out.push(`${f}: ${m[0]}`);
    }
  }
  return out;
}

test("kaynak: görünen metinlerde değer yargısı / 'yapay zeka destekli' ifadeleri yok", () => {
  assert.deepEqual(hits(walk(srcRoot, isSource)), []);
});

test("derlenmiş çıktı (varsa): aynı ifadeler yok", { skip: !existsSync(outRoot) }, () => {
  assert.deepEqual(hits(walk(outRoot, (n) => /\.(html|xml|txt|json)$/.test(n))), []);
});

test("üretilmiş metin süzgeci aynı ifadeleri yakalar; olgusal tanım ve şirket adı serbest", () => {
  for (const t of ["Düşük = ucuz", "Yüksek = verimli", "Düşük F/K = ucuz", "Yüksek = fazla ödeme", "Düşük = az borçlu"]) {
    assert.ok(findBanned(t).length > 0, t);
  }
  // Konusu yapay zekâ olan gerçek bildirimler süzgeçten geçer; "yapay zeka destekli" yasağı yalnız sitenin kendi metni için (FORBIDDEN).
  for (const t of ["ASELSAN A.Ş.: Yapay Zeka Destekli Analiz Platformu İçin Sözleşme İmzalanması", "Fiyat / hisse başına kâr", "MEGA METAL Sanayi ve Ticaret A.Ş.", "/hisseler/tarama/dusuk-fk"]) {
    assert.deepEqual(findBanned(t), [], t);
  }
});

test("derlenmiş çıktı (varsa): İsvea eski raporlarının sayfalarında yanlış hisse kodu yok", { skip: !existsSync(outRoot) }, () => {
  const pages = walk(join(outRoot, "rapor"), (n) => n.endsWith(".html") || n.endsWith(".txt")).filter((f) => f.includes("isvea-seramik"));
  assert.ok(pages.length > 0);
  assert.deepEqual(pages.filter((f) => readFileSync(f, "utf-8").includes("AYX")), []);
});
