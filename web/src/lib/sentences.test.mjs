// Cümle bölme eşitliği: neutral.ts splitSentences ile bot/esham/sentences.py split_sentences aynı ortak
// vektörleri geçer (neutral-vectors.json → sentences). Python tarafı: bot/tests/test_formatting_and_sentences.py.
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { splitSentences } from "./neutral.ts";

const vectors = JSON.parse(readFileSync(new URL("./neutral-vectors.json", import.meta.url), "utf-8"));

test("ortak cümle vektörleri (sayı ve kısaltma farkında bölme)", () => {
  assert.ok(vectors.sentences.length >= 5);
  for (const [input, expected] of vectors.sentences) assert.deepEqual(splitSentences(input), expected, input);
});

test("Türkçe biçimli sayı, tarih ve saatte bölünmez", () => {
  assert.deepEqual(splitSentences("S&P 500 +%1,16 (7.266,17). Veri 27.11.2026 saat 08.30'da geldi."), [
    "S&P 500 +%1,16 (7.266,17).",
    "Veri 27.11.2026 saat 08.30'da geldi.",
  ]);
});
