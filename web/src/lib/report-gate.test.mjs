// Yayın kapısının (esham-schedule.yml: yeni raporlar commit'lenmeden önce `npm test`) ek kuralları:
// - distinctSummary ortak vektörleri (Python: bot/tests/test_report_gate_rules.py aynı dosyayı koşar),
// - KAP olgu bloğu bildirim gövdesinden RAKAM taşımaz (yalnız başlık/şirket/tarih/bildirim no/bağlantı),
// - güncel (sürüm 2) KAP dışı raporun BAŞLIĞI bizim ürettiğimiz metindir: yasaklı kalıp taşımaz.
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import { distinctSummary, findBanned, isLegacy, NOTE_AMOUNT_MISSING } from "./neutral.ts";

const vectors = JSON.parse(readFileSync(new URL("./summary-vectors.json", import.meta.url), "utf-8"));
const reportsDir = new URL("../../content/reports/", import.meta.url);
const reports = () =>
  readdirSync(reportsDir)
    .filter((f) => f.endsWith(".json"))
    .map((f) => [f, JSON.parse(readFileSync(new URL(f, reportsDir), "utf-8"))]);

test("ortak vektörler: distinctSummary (Türkçe büyük/küçük harf, sondaki noktalama)", () => {
  for (const { title, summary, expected } of vectors.cases) {
    assert.equal(distinctSummary({ title, summary }), expected, JSON.stringify({ title, summary }));
  }
});

/** KAP olgu bloğundaki rakamlar: başlık, şirket/kod, tür, tarih, bildirim no ve KAP bağlantısı çıkarıldıktan sonra kalan. */
function factsDigits(doc) {
  const i = doc.body.indexOf("### Bildirim Bilgileri");
  if (i < 0) return { block: "", digits: [] };
  let block = doc.body.slice(i);
  const index = String(doc.kap?.index ?? "");
  const quotes = [doc.title, doc.kap?.company, doc.kap?.type, ...(doc.tags ?? [])].filter(Boolean);
  for (const q of quotes.sort((a, b) => b.length - a.length)) block = block.split(q).join("");
  block = block
    .split("\n")
    .filter((l) => !l.startsWith("- **Tarih:**"))
    .join("\n");
  if (index) block = block.split(`https://www.kap.org.tr/tr/Bildirim/${index}`).join("").split(`#${index}`).join("");
  return { block, digits: block.match(/\d[\d.,]*/g) ?? [] };
}

const FACTS_OK = {
  title: "X A.Ş.: Pay Geri Alım",
  tags: ["XXXXX", "KAP", "BIST"],
  kap: { company: "X A.Ş.", type: "Payların Geri Alınmasına İlişkin Bildirim", index: "1700856" },
  body: [
    "### Bildirim Bilgileri",
    "- **Başlık (KAP):** X A.Ş.: Pay Geri Alım",
    "- **Şirket:** X A.Ş. (XXXXX)",
    "- **Tarih:** 2026-11-04",
    "- **Bildirim türü (KAP):** Payların Geri Alınmasına İlişkin Bildirim",
    `- **Tutar:** ${NOTE_AMOUNT_MISSING}`,
    "- **Kaynak:** [KAP bildirimi #1700856](https://www.kap.org.tr/tr/Bildirim/1700856)",
  ].join("\n"),
};

test("KAP olgu bloğu bildirim gövdesinden rakam taşımaz (kural + mutasyon)", () => {
  assert.deepEqual(factsDigits(FACTS_OK).digits, []);
  // bildirim gövdesinden sızmış tutar/fiyat yakalanır
  const leaked = { ...FACTS_OK, body: FACTS_OK.body.replace(NOTE_AMOUNT_MISSING, "100.000 adet pay, ortalama 42,10 TL") };
  assert.deepEqual(factsDigits(leaked).digits, ["100.000", "42,10"]);
});

test("tüm güncel KAP raporları: olgu bloğunda rakam yok, tutar satırı yalnız 'bildirime bakın' notu", () => {
  let n = 0;
  for (const [f, doc] of reports()) {
    if (isLegacy(doc) || !doc.kap) continue;
    n++;
    const { block, digits } = factsDigits(doc);
    assert.ok(block, `${f}: olgu bloğu yok`);
    assert.deepEqual(digits, [], f);
    const amount = doc.body.split("\n").find((l) => l.startsWith("- **Tutar:**"));
    assert.equal(amount, `- **Tutar:** ${NOTE_AMOUNT_MISSING}`, f);
  }
  assert.ok(n >= 0);
});

test("güncel KAP dışı raporların başlığı (bizim metnimiz) yasaklı kalıp taşımaz", () => {
  for (const [f, doc] of reports()) {
    if (isLegacy(doc) || doc.kap) continue;
    assert.deepEqual(findBanned(doc.title), [], f);
  }
});
