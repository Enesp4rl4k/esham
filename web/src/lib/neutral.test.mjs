import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import { findBanned, normalize, stripBanned, legacyView, NOTE_KAP, isKapReport } from "./neutral.ts";

const vectors = JSON.parse(readFileSync(new URL("./neutral-vectors.json", import.meta.url), "utf-8"));
const reportsDir = new URL("../../content/reports/", import.meta.url);

// ---- ortak vektörler (Python tarafı bot/tests/test_neutral_language.py aynı dosyayı koşar) ----

test("ortak vektörler: yasaklanması gerekenler yakalanır", () => {
  const missed = vectors.block.filter((t) => findBanned(t).length === 0);
  assert.deepEqual(missed, []);
});

test("ortak vektörler: olgusal ifadeler korunur", () => {
  const over = vectors.keep.filter((t) => findBanned(t).length > 0).map((t) => [t, findBanned(t)]);
  assert.deepEqual(over, []);
});

test("ortak vektörler: normalizasyon", () => {
  for (const [input, expected] of vectors.normalize) assert.equal(normalize(input), expected, JSON.stringify(input));
});

test("ortak vektörler: strip", () => {
  for (const [input, expected] of vectors.strip) assert.equal(stripBanned(input), expected);
});

// ---- eski raporlar ----

const load = (name) => JSON.parse(readFileSync(new URL(name, reportsDir), "utf-8"));

test("eski KAP raporu yalın görünümde: yorum gövdesi yok, başlık aynen, eski kart yok", () => {
  const doc = load("2026-11-04-turkiye-is-bankasi-a-s-yurt-icinde-sermaye-benzeri-tahvil-ihracina-iliskin-spk-basvurusu.json");
  const { report, minimal } = legacyView({ ...doc, tags: doc.tags ?? [], sources: doc.sources ?? [] });
  assert.equal(minimal, true);
  assert.equal(report.image, undefined);
  assert.ok(report.body.includes(`- **Başlık:** ${doc.title}`));
  assert.ok(report.body.includes("- **Şirket:** TÜRKİYE İŞ BANKASI A.Ş."));
  for (const gone of ["Hızlı Bakış", "Finansal Sinyal", "4950000", "Sözleşme Tutarı"]) assert.ok(!report.body.includes(gone), gone);
  assert.equal(report.summary, doc.title);
  assert.ok(!report.tags.includes("Mega Sözleşme"));
});

test("şema sürümü taşıyan yeni rapora dokunulmaz", () => {
  const r = { slug: "s", title: "T", category: "bist", summary: "S", body: "B", publishedAt: "2026-11-27T00:00:00Z", aiGenerated: true, tags: [], sources: ["KAP"], image: "/cards/x.png", schemaVersion: 2 };
  assert.equal(legacyView(r).report, r);
});

test("tüm eski raporlar: yalın görünümde yasaklı kalıp yok, eski kart yok; 'BIST için Beklenti' render edilmez", () => {
  let minimal = 0;
  let kept = 0;
  for (const f of readdirSync(reportsDir).filter((x) => x.endsWith(".json"))) {
    const doc = JSON.parse(readFileSync(new URL(f, reportsDir), "utf-8"));
    const { report, minimal: m } = legacyView({ ...doc, tags: doc.tags ?? [], sources: doc.sources ?? [], aiGenerated: doc.aiGenerated !== false });
    if (m) minimal++; else kept++;
    assert.equal(report.image, undefined, f);
    if (isKapReport(report)) assert.ok(m, f);
    // KAP başlığı birebir alıntıdır ve süzülmez; denetim başlık dışındaki üretilmiş/şablon metne yapılır.
    const generated = report.body.split(doc.title).join("") + "\n" + report.summary.split(doc.title).join("");
    assert.deepEqual(findBanned(generated), [], f);
    assert.ok(!/BIST için Beklenti/i.test(report.body), f);
  }
  assert.ok(minimal > 0 && kept >= 0);
});

test("not metni tek kaynaktan", () => {
  assert.match(NOTE_KAP, /yatırım tavsiyesi değildir/);
});
