import test from "node:test";
import assert from "node:assert/strict";
import { slugify, sectorGroups, sectorStats, runScan, SCANS, MIN_INDEXABLE } from "./programmatic.ts";

const st = (o) => ({ ticker: "X", name: "X", sector: "Enerji", financial: false, price: 1, as_of: "", market_cap: 1e10, pe: null, pb: null, ev_ebitda: null, roe: null, net_margin: null, dividend_yield: null, net_debt_ebitda: null, ...o });

test("slugify Türkçe karakterleri ASCII yapar", () => {
  assert.equal(slugify("Bankacılık"), "bankacilik");
  assert.equal(slugify("İçecek"), "icecek");
  assert.equal(slugify("Dayanıklı Tüketim"), "dayanikli-tuketim");
  assert.equal(slugify("İnşaat Malz."), "insaat-malz");
});

test("sektör grupları büyüklüğe göre sıralı ve slug benzersiz", () => {
  const u = { stocks: [st({ ticker: "A" }), st({ ticker: "B" }), st({ ticker: "C", sector: "Cam" })] };
  const g = sectorGroups(u);
  assert.equal(g[0].name, "Enerji");
  assert.equal(new Set(g.map((x) => x.slug)).size, g.length);
});

test("sektör istatistiği şüpheli satırları hariç tutar", () => {
  const s = sectorStats([st({ pe: 10 }), st({ pe: 20 }), st({ pe: 1000, suspect: true })]);
  assert.equal(s.pe, 15);
});

test("tarama: şüpheli elenir, sıralama yönü doğru", () => {
  const u = { stocks: [st({ ticker: "A", pe: 5 }), st({ ticker: "B", pe: 3 }), st({ ticker: "C", pe: 2, suspect: true }), st({ ticker: "D", pe: -4 })] };
  const r = runScan(u, SCANS.find((x) => x.slug === "dusuk-fk"));
  assert.deepEqual(r.map((x) => x.ticker), ["B", "A"]);
  assert.ok(MIN_INDEXABLE >= 3);
});

test("tarama slug ve kimlikleri benzersiz", () => {
  assert.equal(new Set(SCANS.map((s) => s.slug)).size, SCANS.length);
});

import { pairSlug, comparePairs, comparePair } from "./programmatic.ts";

test("çift slug alfabetik ve tekil", () => {
  assert.equal(pairSlug("thyao", "PGSUS"), "PGSUS-vs-THYAO");
  assert.equal(pairSlug("PGSUS", "THYAO"), "PGSUS-vs-THYAO");
});

test("çiftler aynı sektörden, tekrarsız ve sıralı slug", () => {
  const mk = (t, mc, sector = "Enerji") => ({ ticker: t, name: t, sector, financial: false, price: 1, as_of: "", market_cap: mc, pe: 5, pb: 1, ev_ebitda: 4, roe: 10, net_margin: 5, dividend_yield: 1, net_debt_ebitda: 1 });
  const u = { stocks: [mk("D", 4), mk("C", 3), mk("B", 2), mk("A", 1), mk("Z", 9, "Cam")] };
  const p = comparePairs(u, 3);
  assert.equal(p.length, 3);
  assert.equal(new Set(p.map((x) => x.slug)).size, 3);
  for (const x of p) assert.ok(x.a.ticker < x.b.ticker);
});

test("karşılaştırma: düşük iyi/yüksek iyi kazananı ve finansal elemesi", () => {
  const base = { ticker: "A", name: "A", sector: "S", financial: false, price: 1, as_of: "", market_cap: 1, pe: 5, pb: 1, ev_ebitda: 4, roe: 10, net_margin: 5, dividend_yield: 1, net_debt_ebitda: 1 };
  const r = comparePair(base, { ...base, ticker: "B", pe: 8, roe: 20 });
  assert.equal(r.find((x) => x.metric.key === "pe").winner, "a");
  assert.equal(r.find((x) => x.metric.key === "roe").winner, "b");
  const f = comparePair({ ...base, financial: true }, base);
  assert.ok(!f.some((x) => x.metric.key === "ev_ebitda"));
});
