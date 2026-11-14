import { test } from "node:test";
import assert from "node:assert/strict";
import { normalize, move, toggle, visibleOrder, PRE_PAINT_SCRIPT } from "./home-layout.ts";

const ids = ["a", "b", "c", "d"];
const defaults = { order: ["a", "b", "c", "d"], hidden: ["d"] };

test("kayıt yoksa varsayılan; bozuk kayıtta da varsayılan", () => {
  assert.deepEqual(normalize(null, ids, defaults), defaults);
  assert.deepEqual(normalize({ order: "x" }, ids, defaults), defaults);
  assert.deepEqual(normalize("garbage", ids, defaults), defaults);
});

test("bilinmeyen kimlik atılır, tekrar temizlenir, eksik bölüm varsayılan sırayla sona eklenir", () => {
  const n = normalize({ order: ["c", "zzz", "c", "a"], hidden: ["a", "zzz", "a"] }, ids, defaults);
  assert.deepEqual(n.order, ["c", "a", "b", "d"]); // yeni/eksik b, d sona
  assert.deepEqual(n.hidden, ["a"]);
});

test("yukarı/aşağı taşıma sınırlarda değişmez", () => {
  const l = { order: ["a", "b", "c"], hidden: [] };
  assert.deepEqual(move(l, "b", -1).order, ["b", "a", "c"]);
  assert.deepEqual(move(l, "b", 1).order, ["a", "c", "b"]);
  assert.equal(move(l, "a", -1), l);
  assert.equal(move(l, "c", 1), l);
  assert.equal(move(l, "yok", 1), l);
});

test("gizle/göster ve görünür sıra", () => {
  let l = { order: ["a", "b", "c"], hidden: [] };
  l = toggle(l, "b");
  assert.deepEqual(visibleOrder(l), ["a", "c"]);
  l = toggle(l, "b");
  assert.deepEqual(visibleOrder(l), ["a", "b", "c"]);
});

test("ön-boyama betiği yalnızca güvenli kimlikleri CSS'e yazar", () => {
  const store = { "esham:home:v1": JSON.stringify({ order: ["a", 'x"]{}*{display:none}', "b"], hidden: ["b"] }) };
  const appended = [];
  const ctx = {
    localStorage: { getItem: (k) => store[k] ?? null },
    document: { createElement: () => ({}), head: { appendChild: (n) => appended.push(n) } },
  };
  new Function("localStorage", "document", PRE_PAINT_SCRIPT)(ctx.localStorage, ctx.document);
  assert.equal(appended.length, 1);
  const css = appended[0].textContent;
  assert.ok(css.includes('[data-home-section="a"]{order:0}'));
  assert.ok(css.includes('[data-home-section="b"]{display:none}'));
  assert.ok(!css.includes("display:none}*"), "enjeksiyon denemesi CSS'e girmemeli");
  assert.ok(!css.includes('x"'));
});
