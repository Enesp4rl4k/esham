import test from "node:test";
import assert from "node:assert/strict";
import { NAV, isGroupActive } from "./nav.config.ts";

const g = (k) => NAV.find((x) => x.key === k);

test("menü 3 başlık ve boş href yok", () => {
  assert.deepEqual(NAV.map((x) => x.key), ["hisseler", "piyasa", "analizler"]);
  for (const x of NAV) for (const i of x.items ?? []) assert.ok(i.href.startsWith("/"));
});

test("etkin başlık yola göre belirlenir", () => {
  assert.ok(isGroupActive(g("hisseler"), "/hisse/THYAO"));
  assert.ok(isGroupActive(g("piyasa"), "/piyasa/temettu-takvimi"));
  assert.ok(isGroupActive(g("analizler"), "/rapor/x"));
  assert.ok(!isGroupActive(g("piyasa"), "/hisse/THYAO"));
  assert.ok(!isGroupActive(g("hisseler"), "/"));
});
