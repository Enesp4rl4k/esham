import test from "node:test";
import assert from "node:assert/strict";
import { truncate, seoTitle, seoDescription } from "./seo.ts";

test("kısa metin değişmez", () => {
  assert.equal(truncate("Kısa başlık", 60), "Kısa başlık");
});

test("uzun başlık sözcük sınırında kesilir ve sınırı aşmaz", () => {
  const t = seoTitle("Haftalık Piyasa Özeti: BIST 100 haftayı yükselişle kapattı ve sektörlerde ayrışma sürdü");
  assert.ok(t.length <= 60, t);
  assert.ok(t.endsWith("…"));
  assert.ok(!t.includes("  "));
});

test("açıklama 155 karakteri aşmaz", () => {
  const d = seoDescription("a ".repeat(200));
  assert.ok(d.length <= 155);
});
