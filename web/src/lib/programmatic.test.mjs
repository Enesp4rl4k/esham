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
