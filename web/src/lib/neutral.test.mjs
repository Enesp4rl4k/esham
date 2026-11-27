import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { findBanned, stripBanned, sanitizeSummary, sanitizeReport } from "./neutral.ts";

// Gerçek eski rapor: İş Bankası tahvil başvurusu ("MEGA SÖZLEŞME", "Finansal Sinyal", ISATR fiyatı 4950000.00 TL)
const legacy = JSON.parse(
  readFileSync(
    new URL(
      "../../content/reports/2026-11-04-turkiye-is-bankasi-a-s-yurt-icinde-sermaye-benzeri-tahvil-ihracina-iliskin-spk-basvurusu.json",
      import.meta.url,
    ),
    "utf-8",
  ),
);

test("yasaklı kalıplar büyük/küçük harf ve aksan duyarsız yakalanır", () => {
  for (const t of ["Finansal Sinyal: Pozitif", "FİNANSAL SİNYAL", "Pivot Üstü: Boğa / Altı: Ayı", "İLK KÂR SATIŞI",
    "Olası Tepki Alım Tabanı", "KRİTİK DİRENÇ", "MEGA SÖZLEŞME", "pozitif haber akışı etkisi yaratması beklenir"]) {
    assert.ok(findBanned(t).length > 0, t);
  }
  for (const t of ["Kasım ayı içinde ödenecektir.", "MEGA POLİETİLEN A.Ş.", "Satış bedeli nakit varlıkları destekler.",
    "Bu sayfa, kamuya açık bir KAP bildiriminin otomatik özetidir; yatırım tavsiyesi değildir."]) {
    assert.deepEqual(findBanned(t), [], t);
  }
});

test("eski rapor gövdesi görüntülemede temizlenir; olgusal giriş korunur", () => {
  const body = stripBanned(legacy.body);
  assert.deepEqual(findBanned(body), []);
  assert.ok(body.includes("Hızlı Bakış"));
  assert.ok(!body.includes("4950000"));
  assert.ok(!body.includes("Sözleşme Tutarı"));
  assert.ok(!body.includes("| Metrik |"));
});

test("özetteki 'MEGA SÖZLEŞME |' etiketi düşer", () => {
  assert.equal(
    sanitizeSummary("🔥 MEGA SÖZLEŞME | GARAN: İştirak satışının tamamlanması", "başlık"),
    "GARAN: İştirak satışının tamamlanması",
  );
  assert.equal(sanitizeSummary("Temiz özet.", "başlık"), "Temiz özet.");
});

test("sanitizeReport: KAP raporunda bir şey ayıklandıysa eski kart gizlenir; temiz rapora dokunulmaz", () => {
  const { report, changed } = sanitizeReport(legacy);
  assert.equal(changed, true);
  assert.equal(report.image, undefined);
  assert.ok(!report.tags.includes("Mega Sözleşme"));
  assert.ok(!report.summary.includes("MEGA"));

  const clean = { title: "T", summary: "S", body: "### Hızlı Bakış\nMetin.\n\n\n", tags: ["KAP"], sources: ["KAP"], image: "/cards/x.png" };
  const r2 = sanitizeReport(clean);
  assert.equal(r2.changed, false);
  assert.equal(r2.report, clean);
});

test("tüm mevcut rapor gövdeleri süzgeçten sonra temizdir", async () => {
  const { readdirSync } = await import("node:fs");
  const dir = new URL("../../content/reports/", import.meta.url);
  let dirty = 0;
  for (const f of readdirSync(dir).filter((x) => x.endsWith(".json"))) {
    const doc = JSON.parse(readFileSync(new URL(f, dir), "utf-8"));
    const { report } = sanitizeReport({ ...doc, tags: doc.tags ?? [], sources: doc.sources ?? [] });
    if (findBanned(report.body).length || findBanned(report.summary).length || report.tags.some((t) => findBanned(t).length)) dirty++;
  }
  assert.equal(dirty, 0);
});
