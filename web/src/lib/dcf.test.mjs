// Çalıştır: npm test   (Node 22+; .ts doğrudan içe aktarılır)
import { test } from "node:test";
import assert from "node:assert/strict";
import { dcf, sensitivity, defaultBase, defaultAssumptions, SCENARIOS } from "./dcf.ts";

const base = { baseFcf: 100, growth1: 0.1, terminalGrowth: 0.02, wacc: 0.1, netDebt: 50, shares: 10 };

test("elle doğrulanmış küçük model (tek yıl)", () => {
  // 1 yıl: fcf = 100*(1+0.02)=102 ; PV = 102/1.1 ; TV = 102*1.02/(0.08) ; PV(TV)=TV/1.1
  const r = dcf({ ...base, years: 1 });
  const fcf1 = 102;
  const tv = (fcf1 * 1.02) / 0.08;
  const ev = fcf1 / 1.1 + tv / 1.1;
  assert.ok(Math.abs(r.enterpriseValue - ev) < 1e-9);
  assert.ok(Math.abs(r.perShare - (ev - 50) / 10) < 1e-9);
});

test("büyüme ilk yıldan uç büyümeye doğrusal iner", () => {
  const r = dcf(base);
  assert.equal(r.projections.length, 5);
  assert.ok(Math.abs(r.projections[0].growth - 0.1) < 1e-12);
  assert.ok(Math.abs(r.projections[4].growth - 0.02) < 1e-12);
  assert.ok(r.projections[1].growth < r.projections[0].growth && r.projections[1].growth > r.projections[2].growth);
});

test("geçersiz girdilerde null: WACC ≤ uç büyüme, negatif baz, hisse yok", () => {
  assert.equal(dcf({ ...base, wacc: 0.02 }), null);
  assert.equal(dcf({ ...base, wacc: 0.01 }), null);
  assert.equal(dcf({ ...base, baseFcf: -5 }), null);
  assert.equal(dcf({ ...base, baseFcf: 0 }), null);
  assert.equal(dcf({ ...base, shares: 0 }), null);
});

test("net nakit hisse başı değeri artırır; terminal payı 0-1 arası", () => {
  const a = dcf({ ...base, netDebt: 50 });
  const b = dcf({ ...base, netDebt: -50 });
  assert.ok(b.perShare > a.perShare);
  assert.ok(a.terminalShare > 0 && a.terminalShare < 1);
});

test("duyarlılık: WACC artınca değer düşer, uç büyüme artınca yükselir, geçersiz hücre null", () => {
  const { baseFcf, growth1, netDebt, shares } = base;
  const s = sensitivity({ baseFcf, growth1, netDebt, shares }, 0.1, 0.02);
  const mid = s.values[2][2];
  assert.ok(Math.abs(mid - dcf(base).perShare) < 1e-9);
  assert.ok(s.values[3][2] < mid && s.values[1][2] > mid);
  assert.ok(s.values[2][3] > mid && s.values[2][1] < mid);
  const tight = sensitivity({ baseFcf, growth1, netDebt, shares }, 0.03, 0.02, [0], [0, 0.02]);
  assert.equal(tight.values[0][1], null); // g = 4% > wacc 3%
});

test("varsayılan baz seçimi ve varsayımlar", () => {
  assert.equal(defaultBase(10, 5), "fcf");
  assert.equal(defaultBase(-1, 5), "net_income");
  assert.equal(defaultBase(-1, -5), null);
  assert.equal(defaultBase(null, null), null);
  assert.ok(defaultAssumptions("USD").wacc < defaultAssumptions("TRY").wacc);
  const d = defaultAssumptions("TRY");
  assert.ok(d.wacc + SCENARIOS.cons.dWacc > d.terminalGrowth + SCENARIOS.opt.dGT); // senaryolar geçerli kalır
});
