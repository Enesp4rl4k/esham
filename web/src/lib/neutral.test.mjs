import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import { findBanned, normalize, stripBanned, legacyView, legacyTitle, legacySummary, disambiguateLegacyTitles, NOTE_KAP, isKapReport } from "./neutral.ts";
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

test("tüm eski raporlar: yalın görünümde yasaklı kalıp yok, eski kart yok; 'BIST için Beklenti' render edilmez", () => {
  let minimal = 0;
  let kept = 0;
  for (const f of readdirSync(reportsDir).filter((x) => x.endsWith(".json"))) {
    const doc = JSON.parse(readFileSync(new URL(f, reportsDir), "utf-8"));
    const { report, minimal: m } = legacyView({ ...doc, tags: doc.tags ?? [], sources: doc.sources ?? [], aiGenerated: doc.aiGenerated !== false });
    if (m) minimal++; else kept++;
    assert.equal(report.image, undefined, f);
    assert.ok(m, f); // sürüm alanı olmayan her kayıt yalın görünümde
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

test("ortak vektörler: eski kayıt görünen başlığı ve özeti (Python legacy_title/legacy_summary ile aynı)", () => {
  for (const [doc, title, summary] of vectors.legacy) {
    assert.equal(legacyTitle(doc), title, doc.title);
    assert.equal(legacySummary(doc), summary, doc.title);
  }
});

test("eski KAP dışı başlık yorum taşımaz; kartta başlık tekrarı yok", () => {
  for (const f of readdirSync(reportsDir).filter((x) => x.endsWith(".json"))) {
    const doc = JSON.parse(readFileSync(new URL(f, reportsDir), "utf-8"));
    const { report } = legacyView({ ...doc, tags: doc.tags ?? [], sources: doc.sources ?? [], aiGenerated: doc.aiGenerated !== false });
    assert.ok(!report.summary.includes(report.title), f);
    if (report.title !== doc.title) {
      assert.match(report.title, / — \d{1,2} \S+ \d{4}$/, f);
      for (const bad of ["takip ediliyor", "izleniyor", "Güvenli liman", "risk iştahı", "rotasyon"]) assert.ok(!report.title.includes(bad), f);
    }
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
const ISVEA = readdirSync(reportsDir).filter((f) => f.includes("isvea-seramik"));
const TICKER_PATTERN = /[A-Z][A-Z0-9]{2,5}/;

test("eski raporlarda yapılandırılmış hisse kodu GÖSTERİLMEZ: İsvea raporlarında 'AYX' hiçbir yüzeyde yok", () => {
  assert.ok(ISVEA.length >= 2); let withCode = 0;
  const views = ISVEA.map((f) => {
    const doc = JSON.parse(readFileSync(new URL(f, reportsDir), "utf-8"));
    withCode += JSON.stringify(doc).includes("AYX") ? 1 : 0;
    const { report } = legacyView({ ...doc, tags: doc.tags ?? [], sources: doc.sources ?? [] });
    return { ...report, legacyMinimal: true };
  });
  assert.ok(withCode > 0, "veri hâlâ yanlış kodu taşıyor (sınama anlamlı)");
  for (const v of disambiguateLegacyTitles(views)) {
    // başlık, kart özeti, gövde (OG/JSON-LD/RSS bu alanlardan beslenir), etiketler, ipo bloğu
    const surfaces = JSON.stringify({ t: v.title, s: v.summary, b: v.body, tags: v.tags, ipo: v.ipo });
    assert.ok(!surfaces.includes("AYX"), surfaces);
    assert.equal(v.ipo, undefined);
  }
});

test("eski türetilmiş başlıkta ve şirket satırında hisse kodu deseni yok (tüm eski raporlar)", () => {
  for (const f of readdirSync(reportsDir).filter((x) => x.endsWith(".json"))) {
    const doc = JSON.parse(readFileSync(new URL(f, reportsDir), "utf-8"));
    const { report } = legacyView({ ...doc, tags: doc.tags ?? [], sources: doc.sources ?? [] });
    if (report.title !== doc.title) assert.ok(!TICKER_PATTERN.test(report.title.replace(/BIST|VİOP|KAP/g, "")), `${f}: ${report.title}`);
    assert.ok(!/Hisse kodu/.test(report.body), f);
    assert.ok(report.tags.every((t) => !/^[A-Z][A-Z0-9]{2,5}$/.test(t) || t === "KAP" || t === "BIST"), f);
  }
});

test("aynı gün aynı türetilmiş başlık: raporun kendi yayın saati ayırıcı olur; KAP başlığı ve saatsiz kayıt değişmez", () => {
  const mk = (title, publishedAt, extra = {}) => ({ title, sources: ["X"], publishedAt, legacyMinimal: true, ...extra });
  const out = disambiguateLegacyTitles([
    mk("Halka arz belgesi özeti — 6 Temmuz 2026", "2026-07-06T10:05:00Z"),
    mk("Halka arz belgesi özeti — 6 Temmuz 2026", "2026-07-06T11:30:00Z"),
    mk("Sabah bülteni — 6 Temmuz 2026", "2026-07-06T05:30:00Z"),
    mk("Gündem notu — 6 Temmuz 2026", "2026-07-06"),
    mk("Gündem notu — 6 Temmuz 2026", "2026-07-06"),
    mk("A A.Ş.: Duyuru", "2026-07-06T10:00:00Z", { sources: ["KAP"] }),
    mk("A A.Ş.: Duyuru", "2026-07-06T11:00:00Z", { sources: ["KAP"] }),
  ]);
  assert.deepEqual(out.map((r) => r.title), [
    "Halka arz belgesi özeti — 6 Temmuz 2026 · 13:05",
    "Halka arz belgesi özeti — 6 Temmuz 2026 · 14:30",
    "Sabah bülteni — 6 Temmuz 2026",
    "Gündem notu — 6 Temmuz 2026",
    "Gündem notu — 6 Temmuz 2026",
    "A A.Ş.: Duyuru",
    "A A.Ş.: Duyuru",
  ]);
});

test("resmî KAP başlığında şirket ön eki yoksa yalnız yapılandırılmış kap.company gösterilir; kod/tahmin yok", () => {
  const rep = (over) => ({ slug: "s", category: "bist", summary: "S", body: "x", publishedAt: "2026-07-07T10:00:00Z", aiGenerated: true, sources: ["KAP"], image: undefined, ...over });
  const noPrefix = "Kredi Derecelendirme Notu Bildirimi";
  const withCompany = legacyView(rep({ title: noPrefix, tags: ["PBT", "KAP", "BIST"], kap: { company: "PASİFİK TEKNOLOJİ A.Ş." } }));
  assert.ok(withCompany.report.body.includes("- **Şirket:** PASİFİK TEKNOLOJİ A.Ş."));
  assert.equal(withCompany.report.title, noPrefix);
  const none = legacyView(rep({ title: noPrefix, tags: ["PBT", "KAP", "BIST"] }));
  assert.ok(!none.report.body.includes("Şirket:") && !none.report.body.includes("PBT"));
  const prefixed = legacyView(rep({ title: "X A.Ş.: Duyuru", tags: ["XXX", "KAP"], kap: { company: "BAŞKA A.Ş." } }));
  assert.ok(prefixed.report.body.includes("- **Şirket:** X A.Ş."));
});
