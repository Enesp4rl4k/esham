import test from "node:test";
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { existsSync, readFileSync, readdirSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import {
  CARD_SIZES,
  COMMENTARY_PATTERNS,
  DEFAULT_VARIANT,
  VARIANTS,
  buildScene,
  cardPath,
  datasetTexts,
  displayDomain,
  fmtNumber,
  isIndexableDataset,
  latestValues,
  nextPeriod,
  sceneJson,
  sceneTexts,
  spreadLabels,
  tableRows,
  toCsv,
  validateDataset,
  veriSitemap,
} from "./veri.ts";
import { findBanned, normalize } from "./neutral.ts";
import { SITE_URL } from "./config.ts";

const O = { domain: displayDomain(SITE_URL) };

const here = path.dirname(fileURLToPath(import.meta.url));
const WEB = path.join(here, "..", "..");
const DATA = path.join(WEB, "public", "data", "veri");
const files = existsSync(DATA) ? readdirSync(DATA).filter((f) => f.endsWith(".json")).sort() : [];
const load = (f) => JSON.parse(readFileSync(path.join(DATA, f), "utf8"));
const clone = (x) => JSON.parse(JSON.stringify(x));

// Küçük, elle yazılmış geçerli veri kümesi (sentetik; yalnız şema testleri için)
function mini(over = {}) {
  const prov = (cell) => ({ file: "f1", sheet: "Sayı", cell, label: "Örnek A.Ş." });
  return {
    schema: 1,
    slug: "ornek",
    title: "Örnek seri",
    kicker: "Deneme",
    measure: "Şube sayısı",
    unit: "adet",
    periodType: "quarter",
    coverage: "Dönem sonu",
    description: "Şema testi için sentetik veri.",
    sample: true,
    source: { name: "Örnek Kaynak", short: "ÖK", publication: "Örnek yayın", url: "https://example.org/a", termsUrl: "https://example.org/t", terms: "Test." },
    methodology: ["Sentetik."],
    breaks: [],
    updatedAt: "2026-11-27",
    periods: ["2025-Q4", "2026-Q1", "2026-Q2", "2026-Q3"],
    files: { f1: { name: "a.xlsx", url: "https://example.org/a.xlsx", page: "https://example.org/a", retrieved: "2026-11-27" } },
    series: [
      { id: "a", label: "A", sourceLabel: "Örnek A.Ş.", values: [10, null, 12, 13], provenance: [prov("C1"), null, prov("C3"), prov("C4")] },
      { id: "b", label: "B", sourceLabel: "Örnek B.Ş.", values: [1000, 1001, 1002, 999], provenance: [prov("D1"), prov("D2"), prov("D3"), prov("D4")] },
    ],
    ...over,
  };
}

// ---- şema / doğrulayıcı ----------------------------------------------------------------------

test("yayımlanan her veri kümesi şemaya uyar ve dosya adı slug ile aynıdır", () => {
  assert.ok(files.length >= 1, "en az bir veri kümesi bekleniyor");
  for (const f of files) {
    const ds = load(f);
    assert.deepEqual(validateDataset(ds), [], f);
    assert.equal(`${ds.slug}.json`, f);
  }
});

test("doğrulayıcı: geçerli örnek kabul edilir; null değer kaynaksız olabilir", () => {
  assert.deepEqual(validateDataset(mini()), []);
});

test("doğrulayıcı: dönemler artan ve kesintisiz olmalı", () => {
  const a = mini({ periods: ["2025-Q4", "2026-Q2", "2026-Q1", "2026-Q3"] });
  assert.ok(validateDataset(a).some((e) => e.includes("kesintisiz")));
  const b = mini({ periods: ["2025-Q4", "2026-Q1", "2026-Q3", "2026-Q4"] }); // boşluklu dönem listesi
  assert.ok(validateDataset(b).some((e) => e.includes("kesintisiz")));
  const c = mini({ periods: ["2025-4", "2026-Q1", "2026-Q2", "2026-Q3"] });
  assert.ok(validateDataset(c).some((e) => e.includes("biçimi")));
  assert.equal(nextPeriod("2026-Q4", "quarter"), "2027-Q1");
  assert.equal(nextPeriod("2026-12", "month"), "2027-01");
});

test("doğrulayıcı: birim izinli listede olmalı; 'adet' negatif olmayan tam sayı ister", () => {
  assert.ok(validateDataset(mini({ unit: "parça" })).some((e) => e.includes("birim")));
  const d = mini();
  d.series[0].values[0] = 10.5;
  assert.ok(validateDataset(d).some((e) => e.includes("tam sayı")));
  const n = mini();
  n.series[0].values[0] = -1;
  assert.ok(validateDataset(n).some((e) => e.includes("tam sayı")));
});

test("doğrulayıcı: dolu her değerin kaynağı (dosya, sayfa, hücre, etiket) zorunlu", () => {
  const d = mini();
  d.series[1].provenance[2] = null;
  assert.ok(validateDataset(d).some((e) => e.includes("kaynağı eksik")));
  const e = mini();
  e.series[1].provenance[2] = { ...e.series[1].provenance[2], file: "yok" };
  assert.ok(validateDataset(e).some((x) => x.includes("kaynağı eksik")));
  const f = mini();
  f.files.f1.retrieved = "";
  assert.ok(validateDataset(f).some((x) => x.includes("files.f1")));
  const g = mini();
  g.series[0].values.pop();
  assert.ok(validateDataset(g).some((x) => x.includes("uzunluğu")));
});

test("gerçek veri: her dolu noktanın kaynak dosyası TBB adresidir ve indirme tarihi vardır", () => {
  for (const f of files) {
    const ds = load(f);
    if (ds.sample) continue;
    for (const s of ds.series)
      s.values.forEach((v, i) => {
        if (v === null) return;
        const file = ds.files[s.provenance[i].file];
        assert.ok(file.url.startsWith("https://www.tbb.org.tr/") || !ds.source.url.includes("tbb.org.tr"), `${s.id} ${ds.periods[i]}`);
        assert.match(file.retrieved, /^\d{4}-\d{2}-\d{2}$/);
      });
  }
});

// ---- boşluklar: ara değer üretilmez -------------------------------------------------------------

test("eksik nokta çizgide boşluktur: ara değer üretilmez", () => {
  const ds = mini();
  const sc = buildScene(ds, "1600x900", DEFAULT_VARIANT, O);
  const pathsA = sc.items.filter((it) => it.k === "path" && it.stroke === "s0");
  const dotsA = sc.items.filter((it) => it.k === "circle" && it.fill === "s0" && !it.stroke);
  // A: [10, null, 12, 13] → tek başına bir nokta + iki noktalı bir parça; toplam 3 nokta (null için nokta yok)
  assert.equal(pathsA.length, 1);
  assert.equal(pathsA[0].pts.length, 2);
  assert.equal(dotsA.length, 1);
  assert.equal(dotsA[0].x, sc.meta.xs[0]);
  // tabloda ve CSV'de de boş
  assert.equal(tableRows(ds).find((r) => r.period === "2026-Q1").cells[0], "—");
  assert.match(toCsv(ds), /\r\n2026-Q1,,1001\r\n/);
});

// ---- tek tanım: tablo, CSV, grafik ve kart aynı sayıları gösterir ------------------------------------

test("parite: grafikteki son değer etiketleri tablo ve CSV ile aynı", () => {
  for (const f of files) {
    const ds = load(f);
    const latest = latestValues(ds);
    const csvRows = toCsv(ds).trim().split("\r\n").map((r) => r.split(","));
    for (const size of CARD_SIZES) {
      for (const variant of Object.keys(VARIANTS)) {
        const sc = buildScene(ds, size, variant, O);
        assert.deepEqual(
          sc.meta.valueLabels.map((v) => [v.seriesId, v.period, v.value, v.text]),
          latest.map((v) => [v.id, v.period, v.value, v.text]),
          `${f} ${size} ${variant}`,
        );
        const texts = sceneTexts(sc).join("\n");
        for (const v of latest) assert.ok(texts.includes(v.text), `${f} ${size} ${variant}: ${v.label} ${v.text} grafikte yok`);
      }
    }
    // tablo: her hücre aynı biçimleyiciden; CSV: ham değer
    const rows = tableRows(ds);
    ds.series.forEach((s, j) =>
      s.values.forEach((v, i) => {
        const row = rows.find((r) => r.period === ds.periods[i]);
        assert.equal(row.cells[j], v === null ? "—" : fmtNumber(v, ds.decimals ?? 0));
        assert.equal(csvRows[i + 1][j + 1], v === null ? "" : String(v));
      }),
    );
  }
});

function pngText(buf) {
  const out = {};
  assert.equal(buf.subarray(1, 4).toString("latin1"), "PNG");
  let o = 8;
  while (o < buf.length) {
    const len = buf.readUInt32BE(o);
    const type = buf.subarray(o + 4, o + 8).toString("latin1");
    if (type === "tEXt") {
      const data = buf.subarray(o + 8, o + 8 + len);
      const z = data.indexOf(0);
      out[data.subarray(0, z).toString("latin1")] = data.subarray(z + 1).toString("latin1");
    }
    o += 12 + len;
  }
  return out;
}

test("parite: yayımlanan PNG kartı güncel veriden üretilen sahnenin ta kendisidir (sha256)", () => {
  for (const f of files) {
    const ds = load(f);
    for (const size of CARD_SIZES) {
      const p = path.join(WEB, "public", cardPath(ds.slug, size));
      if (!isIndexableDataset(ds) && !existsSync(p)) continue;
      assert.ok(existsSync(p), `${p} yok: python -m esham.jobs.publish_veri_cards çalıştırın`);
      const meta = pngText(readFileSync(p));
      const want = createHash("sha256").update(sceneJson(buildScene(ds, size, DEFAULT_VARIANT, O)), "utf8").digest("hex");
      assert.equal(meta["esham:scene-sha256"], want, `${p} eski: veri değişmiş, kart yeniden üretilmeli (python -m esham.jobs.publish_veri_cards)`);
      assert.equal(meta["esham:slug"], ds.slug);
      assert.equal(meta["esham:variant"], DEFAULT_VARIANT);
    }
  }
});

// ---- tarafsız dil --------------------------------------------------------------------------

const COMMENTARY_RE = new RegExp(COMMENTARY_PATTERNS.map((p) => `(?:${p})`).join("|"), "u");
const commentary = (t) => t.split(/\r?\n/).filter((line) => COMMENTARY_RE.test(normalize(line)));

test("tarafsız dil: veri kümesi metinleri, grafik/kart metinleri ve sayfa şablonları temiz", () => {
  const texts = [];
  for (const f of files) {
    const ds = load(f);
    texts.push(...datasetTexts(ds));
    for (const size of CARD_SIZES) for (const v of Object.keys(VARIANTS)) texts.push(...sceneTexts(buildScene(ds, size, v, O)));
  }
  for (const page of ["app/veri/page.tsx", "app/veri/[slug]/page.tsx", "components/DataChart.tsx"]) {
    texts.push(readFileSync(path.join(here, "..", page), "utf8"));
  }
  for (const t of texts) {
    assert.deepEqual(findBanned(t), [], t.slice(0, 120));
    assert.deepEqual(commentary(t), [], t.slice(0, 120));
  }
});

test("yorum kalıpları gerçekten yakalar (kendi kendini sınama)", () => {
  for (const bad of ["Akbank şube sayısı geriliyor", "Halkbank öne geçti", "En çok şube İş Bankası'nda", "Rekor seviye", "Şube sayısı azaldı"]) {
    assert.ok(commentary(bad).length > 0, bad);
  }
  for (const ok of ["Şube sayısı, çeyreklik, dönem sonu", "Akbank 601", "Yurt içi ve yurt dışı şubeler toplamı"]) {
    assert.deepEqual(commentary(ok), [], ok);
  }
});

// ---- dizin ve site haritası --------------------------------------------------------------------

test("gerçek veri indekslenir ve site haritasında; örnek veri asla", () => {
  const all = files.map(load);
  const real = all.filter((d) => !d.sample);
  assert.ok(real.length >= 1);
  const sm = veriSitemap("https://x.test", all).map((e) => e.url);
  assert.ok(sm.includes("https://x.test/veri"));
  for (const d of real) {
    assert.ok(isIndexableDataset(d), d.slug);
    assert.ok(sm.includes(`https://x.test/veri/${d.slug}`), d.slug);
  }
  const sample = { ...clone(real[0]), slug: "ornek-kopya", sample: true };
  assert.equal(isIndexableDataset(sample), false);
  assert.ok(!veriSitemap("https://x.test", [sample]).some((e) => e.url.includes("ornek-kopya")));
  assert.deepEqual(veriSitemap("https://x.test", [sample]), []);
  assert.equal(isIndexableDataset(mini({ sample: false, series: [mini().series[0]] })), false); // 3 dolu nokta < 8
});

test("örnek veri kartta ve grafikte işaretlenir", () => {
  const sc = buildScene(mini(), "1080x1350", DEFAULT_VARIANT, O);
  const t = sceneTexts(sc).join(" ");
  assert.ok(t.includes("ÖRNEK VERİ"));
});

// ---- yerleşim yardımcıları -------------------------------------------------------------------

test("uç etiketleri çakışmaz ve sırası korunur", () => {
  const ys = [400, 402, 401, 600, 405, 100];
  const out = spreadLabels(ys, 28, 50, 700);
  const order = ys.map((y, i) => i).sort((a, b) => ys[a] - ys[b] || a - b);
  for (let k = 1; k < order.length; k++) assert.ok(out[order[k]] - out[order[k - 1]] >= 27.99);
  assert.ok(Math.min(...out) >= 50 && Math.max(...out) <= 700);
});

test("sayı biçimi: binlik nokta, ondalık virgül", () => {
  assert.equal(fmtNumber(1119), "1.119");
  assert.equal(fmtNumber(601), "601");
  assert.equal(fmtNumber(1234567.891, 2), "1.234.567,89");
  assert.equal(fmtNumber(0), "0");
});
