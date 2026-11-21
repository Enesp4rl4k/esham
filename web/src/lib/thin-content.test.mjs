import test from "node:test";
import assert from "node:assert/strict";
import { THIN_WORD_MIN, wordCount, hasDataTable, isThinReport } from "./thin-content.ts";

const words = (n) => Array.from({ length: n }, (_, i) => `k${i}`).join(" ");
const TABLE = "| A | B |\n| --- | --- |\n| 1 | 2 |";

test("sözcük sayımı boşlukları yok sayar", () => {
  assert.equal(wordCount("  bir  iki\n\nüç "), 3);
  assert.equal(wordCount(""), 0);
});

test("tablo tespiti: ayırıcı satır gerekir", () => {
  assert.equal(hasDataTable(TABLE), true);
  assert.equal(hasDataTable("| A | B |\n| 1 | 2 |"), false);
  assert.equal(hasDataTable("a --- b"), false);
  assert.equal(hasDataTable("|:---|---:|"), true);
});

test("kısa ve verisiz rapor ince", () => {
  assert.equal(isThinReport({ body: words(50) }), true);
  assert.equal(isThinReport({ body: "" }), true);
});

test("eşikte ve üstünde ince değil (sınır)", () => {
  assert.equal(isThinReport({ body: words(THIN_WORD_MIN - 1) }), true);
  assert.equal(isThinReport({ body: words(THIN_WORD_MIN) }), false);
});

test("kısa ama tablolu rapor ince değil", () => {
  assert.equal(isThinReport({ body: `${words(20)}\n\n${TABLE}` }), false);
});

test("kısa ama ipo verisi olan rapor ince değil", () => {
  assert.equal(isThinReport({ body: words(20), ipo: { company: "X", ticker: "Y" } }), false);
});
