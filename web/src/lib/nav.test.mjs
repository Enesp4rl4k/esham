import { test } from "node:test";
import assert from "node:assert/strict";
import { nav, stakeValue } from "./nav.ts";

const base = {
  stakes: [
    { title: "A", pct: 50, relation: "Bağlı Ortaklık", ticker: "AAA", mcap: 1000 },
    { title: "B", pct: 20, relation: "İştirak", ticker: "BBB", mcap: 500 },
    { title: "C", pct: 100, relation: "Bağlı Ortaklık", ticker: null, mcap: null },
  ],
  holdingMcap: 400,
  price: 10, // → 40 hisse
  unlistedValue: 0,
  netDebt: 0,
};

test("pay değeri = pay × piyasa değeri; değer yoksa null", () => {
  assert.equal(stakeValue(base.stakes[0]), 500);
  assert.equal(stakeValue(base.stakes[1]), 100);
  assert.equal(stakeValue(base.stakes[2]), null);
});

test("kısmi NAV: yalnızca değeri bilinen paylar toplanır; bilinmeyenler sayılır", () => {
  const r = nav(base);
  assert.equal(r.listedValue, 600);
  assert.equal(r.valuedStakes, 2);
  assert.equal(r.unvaluedStakes, 1);
  assert.equal(r.nav, 600);
  assert.equal(r.shares, 40);
  assert.equal(r.navPerShare, 15);
  assert.ok(Math.abs(r.discount - (10 / 15 - 1)) < 1e-12); // %33,3 iskonto
  assert.equal(r.coverage, 1.5);
});

test("listelenmeyen değer artırır, net borç azaltır", () => {
  const r = nav({ ...base, unlistedValue: 200, netDebt: 100 });
  assert.equal(r.nav, 700);
  assert.equal(r.navPerShare, 17.5);
  const cash = nav({ ...base, netDebt: -60 }); // net nakit NAV'a eklenir
  assert.equal(cash.nav, 660);
});

test("NAV ≤ 0 ise iskonto null; geçersiz fiyat/piyasa değerinde null", () => {
  const r = nav({ ...base, netDebt: 1000 });
  assert.ok(r.nav < 0);
  assert.equal(r.discount, null);
  assert.equal(nav({ ...base, price: 0 }), null);
  assert.equal(nav({ ...base, holdingMcap: 0 }), null);
});
