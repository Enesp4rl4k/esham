import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import { findBanned, normalize, stripBanned, legacyView, legacyTitle, legacySummary, NOTE_KAP, isKapReport, isLegacy, distinctSummary } from "./neutral.ts";
import { isIndexable } from "./thin-content.ts";

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
  assert.ok(report.body.includes(`- **Başlık (KAP):** ${doc.title}`));
  assert.equal(report.title, doc.title); // resmî KAP başlığı aynen
  assert.ok(report.body.includes("- **Şirket:** TÜRKİYE İŞ BANKASI A.Ş."));
  for (const gone of ["Hızlı Bakış", "Finansal Sinyal", "4950000", "Sözleşme Tutarı"]) assert.ok(!report.body.includes(gone), gone);
  assert.equal(report.summary, "KAP bildirimi — eski kayıt.");
  assert.ok(!report.tags.includes("Mega Sözleşme"));
});

test("görünüm kararı YALNIZ schemaVersion'a dayanır: sürüm 2 her üretici için güncel", () => {
  // Kaynakta KAP geçmesi, AI kullanımı ya da kalıp içermesi yeni raporu "eski kayıt" yapmaz.
  const producers = [
    { title: "BIST & Küresel Piyasalar Sabah Raporu", sources: ["KAP", "BIST", "Ekonomik Takvim"], aiGenerated: true },
    { title: "Haftalık Piyasa Özeti — 27 Kasım 2026 haftası", sources: ["BIST", "KAP", "Yahoo Finance"], aiGenerated: true },
    { title: "X A.Ş. Halka Arz Analizi", sources: ["KAP", "İzahname", "Fiyat Tespit Raporu"], aiGenerated: true },
    { title: "X A.Ş. Finansal Analiz", sources: ["KAP", "Finansal Tablolar"], aiGenerated: true },
    { title: "Küresel Makro Görünümü", sources: ["Yahoo Finance"], aiGenerated: true },
    { title: "Haftalık Sektör Endeksi Değişimleri", sources: ["TradingView"], aiGenerated: false },
    { title: "Bankacılık Sektörü Çarpan Tablosu", sources: ["Yahoo Finance"], aiGenerated: false },
    { title: "Kapanış Bülteni: BIST +%1,2", sources: ["BIST", "TradingView"], aiGenerated: false },
    { title: "VİOP Piyasa & Teminat Stresi Raporu", sources: ["TradingView", "Takasbank"], aiGenerated: false },
    { title: "A A.Ş.: Yeni İş İlişkisi", sources: ["KAP", "AAAAA"], aiGenerated: true },
  ];
  for (const p of producers) {
    const r = { slug: "s", category: "bist", summary: "S", body: "Hedef fiyat 150 TL", publishedAt: "2026-11-28T00:00:00Z", tags: [], image: "/cards/x.png", schemaVersion: 2, ...p };
    const v = legacyView(r);
    assert.equal(v.minimal, false, p.title);
    assert.equal(v.report, r, p.title);
    const old = legacyView({ ...r, schemaVersion: undefined });
    assert.equal(old.minimal, true, p.title);
  }
});

// Tüm kayıtlar bu iki denetimden geçer. Eski kayıt (schemaVersion yok) yalın görünüme düşer; GÜNCEL kayıt
// (schemaVersion >= 2, bot'un her yeni raporu) olduğu gibi gösterilir. Önceki sürüm her dosyayı "eski" varsayıyordu:
// zamanlanmış yayın ilk güncel raporu commit'leyince (2026-11-27) testler kırıldı ve site derlenemez oldu.
const viewOf = (doc) => legacyView({ ...doc, tags: doc.tags ?? [], sources: doc.sources ?? [], aiGenerated: doc.aiGenerated !== false });

// Resmî KAP alıntıları (başlık, şirket, tür) süzülmez; denetim bunların dışındaki metne yapılır.
const withoutQuotes = (text, doc) =>
  [doc.title, doc.kap?.company, doc.kap?.type].filter(Boolean).reduce((t, q) => t.split(q).join(""), text);

function checkReportView(f, doc) {
  const v = viewOf(doc);
  const { report, minimal } = v;
  if (isLegacy(doc)) {
    assert.equal(minimal, true, f);
    assert.equal(report.image, undefined, f);
  } else {
    assert.equal(minimal, false, f); // güncel kayıt yalın görünüme DÜŞMEZ
    assert.equal(report.body, doc.body, f);
    assert.equal(report.title, doc.title, f);
  }
  const generated = withoutQuotes(report.body, doc) + "\n" + withoutQuotes(report.summary, doc);
  assert.deepEqual(findBanned(generated), [], f);
  assert.ok(!/BIST için Beklenti/i.test(report.body), f);
  return minimal;
}

function checkSummaryAndTitle(f, doc) {
  const { report } = viewOf(doc);
  if (isLegacy(doc)) {
    assert.ok(!report.summary.includes(report.title), f);
    if (report.title !== doc.title) {
      assert.match(report.title, / — \d{1,2} \S+ \d{4}$/, f);
      for (const bad of ["takip ediliyor", "izleniyor", "Güvenli liman", "risk iştahı", "rotasyon"]) assert.ok(!report.title.includes(bad), f);
    }
    return;
  }
  // Güncel kayıt: özet boş olamaz (feed/meta/arama ister); yalın KAP raporunda özet resmî başlığa DÜŞER,
  // yani özet == başlık meşrudur. Önemli olan başlığın ekranda iki kez görünmemesidir.
  assert.ok(report.summary.trim().length > 0, f);
  // KAP dışı güncel kaydın başlığı bizim ürettiğimiz metindir (KAP başlığı alıntıdır, süzülmez).
  if (!doc.kap) assert.deepEqual(findBanned(report.title), [], f);
  const shown = distinctSummary(report); // kural ve ortak vektörler: report-gate.test.mjs
  assert.ok(shown === "" || shown === report.summary.trim(), f);
}

const reportFiles = () => readdirSync(reportsDir).filter((x) => x.endsWith(".json"));

test("tüm raporlar: eski kayıt yalın, güncel kayıt olduğu gibi; yasaklı kalıp yok; 'BIST için Beklenti' render edilmez", () => {
  let minimal = 0;
  for (const f of reportFiles()) if (checkReportView(f, load(f))) minimal++;
  assert.ok(minimal > 0); // arşivdeki eski kayıtlar yalın görünümde
});

test("tüm raporlar: başlık yorum taşımaz; özet başlığı kartta tekrarlamaz", () => {
  for (const f of reportFiles()) checkSummaryAndTitle(f, load(f));
});

// ---- güncel (şablon yolu) KAP raporu: botun bugün ürettiği biçim; regresyon (2026-11-27) ----

const FRESH_KAP = {
  slug: "x-a-s-ozet-hk-1000001-2026-11-30",
  title: "X A.Ş.: Özet Hk.",
  category: "bist",
  summary: "X A.Ş.: Özet Hk.", // yalın rapor: özet resmî KAP başlığına düşer
  publishedAt: "2026-11-30T09:00:00Z",
  author: "Esham AI",
  aiGenerated: true,
  sources: ["KAP"],
  tags: ["KAP", "BIST"],
  body: [
    "### Bildirim Bilgileri",
    "- **Başlık (KAP):** X A.Ş.: Özet Hk.",
    "- **Şirket:** X A.Ş.",
    "- **Tarih:** 2026-11-30",
    "- **Bildirim türü (KAP):** İzahname-Özet (SPK Tarafından Onaylanan)",
    "- **Tutar:** Tutar bilgisi için bildirime bakın.",
    "- **Kaynak:** [KAP bildirimi #1000001](https://www.kap.org.tr/tr/Bildirim/1000001)",
  ].join("\n"),
  image: "/cards/x-a-s-ozet-hk-1000001-2026-11-30.png",
  schemaVersion: 2,
  kap: { company: "X A.Ş.", type: "İzahname-Özet (SPK Tarafından Onaylanan)", index: "1000001", url: "https://www.kap.org.tr/tr/Bildirim/1000001" },
};

test("güncel yalın KAP raporu (özet == başlık, kart görseli var) aynı denetimlerden geçer", () => {
  assert.equal(checkReportView("fresh", FRESH_KAP), false);
  checkSummaryAndTitle("fresh", FRESH_KAP);
  assert.equal(distinctSummary(FRESH_KAP), ""); // başlık altında aynı satır tekrar edilmez
  assert.equal(viewOf(FRESH_KAP).report.image, FRESH_KAP.image); // güncel kartı yalın görünüm silmez
});

test("denetim gevşetilmedi: güncel raporda yasaklı kalıp, boş özet ya da yorum hâlâ yakalanır", () => {
  const bad = { ...FRESH_KAP, body: FRESH_KAP.body + "\n\nHedef fiyat 150 TL, güçlü al." };
  assert.throws(() => checkReportView("bad", bad));
  assert.throws(() => checkSummaryAndTitle("bad", { ...FRESH_KAP, summary: " " }));
  assert.throws(() => checkSummaryAndTitle("bad", { ...FRESH_KAP, kap: undefined, sources: ["Yahoo Finance"], title: "BIST için güçlü al sinyali" }));
  // eski kayıt için yalın görünüm kuralları aynen sürer
  const old = { ...FRESH_KAP, schemaVersion: undefined };
  assert.equal(viewOf(old).minimal, true);
  assert.equal(viewOf(old).report.image, undefined);
});

test("distinctSummary: farklı özet görünür; aynı (büyük/küçük harf, boşluk farkıyla) gizlenir; boş gizlenir", () => {
  assert.equal(distinctSummary({ title: "A: B", summary: "Başka bir özet" }), "Başka bir özet");
  assert.equal(distinctSummary({ title: "A: B", summary: "  a:  b " }), "");
  assert.equal(distinctSummary({ title: "A: B", summary: "" }), "");
  assert.equal(distinctSummary({ title: "A: B" }), "");
});

test("not metni tek kaynaktan", () => {
  assert.match(NOTE_KAP, /yatırım tavsiyesi değildir/);
});

test("ortak vektörler: eski kayıt görünen başlığı ve özeti (Python legacy_title/legacy_summary ile aynı)", () => {
  for (const [doc, title, summary] of vectors.legacy) {
    assert.equal(legacyTitle(doc), title, doc.title);
    assert.equal(legacySummary(doc), summary, doc.title);
  }
});

test("dizin kararı tek fonksiyon: yalın görünüm ⇒ noindex (ipo meta veriye rağmen)", () => {
  const hun = JSON.parse(readFileSync(new URL("2026-11-10-hun-yenilenebilir-enerji-uretim-a-s-halka-arz-analizi.json", reportsDir), "utf-8"));
  const { report, minimal } = legacyView({ ...hun, tags: hun.tags ?? [], sources: hun.sources ?? [] });
  assert.equal(minimal, true);
  assert.equal(isIndexable({ ...report, legacyMinimal: minimal }), false);
  assert.equal(report.ipo?.verdict, undefined);
  assert.equal(isIndexable({ body: "x", ipo: { company: "X", ticker: "Y" } }), true); // sürüm 2 halka arz
});