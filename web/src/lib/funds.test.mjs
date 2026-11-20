import test from "node:test";
import assert from "node:assert/strict";
import { categoryGroups, fundSlug, sortBy, topBy, describeFund, fmtMoney, fmtSigned, riskLabel } from "./funds.ts";
import { loadFund } from "./funds-data.ts";

const row = (o) => ({ code: "X", name: "X", category: "Hisse Senedi", risk: 6, price: 1, daily: 0, aum: 1e9, investors: 1, fee: 2, as_of: "2026-11-20",
  r1m: null, r3m: null, r6m: null, ytd: null, r1y: null, r3y: null, r5y: null, real_1y: null, vol: null, mdd: null, sharpe: null, rank: null, rank_of: null, ...o });

test("fundSlug Türkçe karakterleri ASCII yapar", () => {
  assert.equal(fundSlug("Para Piyasası"), "para-piyasasi");
  assert.equal(fundSlug("Değişken"), "degisken");
  assert.equal(fundSlug("Kıymetli Madenler"), "kiymetli-madenler");
});

test("kategori grupları fon sayısına göre azalan sıralanır", () => {
  const g = categoryGroups([row({ code: "A", category: "Serbest" }), row({ code: "B", category: "Değişken" }), row({ code: "C", category: "Değişken" })]);
  assert.deepEqual(g.map((x) => [x.slug, x.funds.length]), [["degisken", 2], ["serbest", 1]]);
});

test("sortBy boşları sonda tutar; topBy boşları eler", () => {
  const f = [row({ code: "A", r1y: 5 }), row({ code: "B", r1y: null }), row({ code: "C", r1y: 20 })];
  assert.deepEqual(sortBy(f, "r1y", -1).map((x) => x.code), ["C", "A", "B"]);
  assert.deepEqual(sortBy(f, "r1y", 1).map((x) => x.code), ["A", "C", "B"]);
  assert.deepEqual(topBy(f, "r1y", 5).map((x) => x.code), ["C", "A"]);
});

test("biçimleyiciler", () => {
  assert.equal(fmtMoney(14066966700.8), "14,07 Mr ₺");
  assert.equal(fmtMoney(5_500_000), "5,50 Mn ₺");
  assert.equal(fmtSigned(-2.5), "▼ %2,50");
  assert.equal(fmtSigned(null), "—");
  assert.equal(riskLabel(6), "6/7 · yüksek");
});

const detail = (o = {}) => ({ code: "AFT", name: "AK PORTFÖY YENİ TEKNOLOJİLER", category: "Hisse Senedi", risk: 6, updated_at: "", as_of: "2026-11-20",
  price: 0.86, daily: 2.3, aum: 14066966700, units: 1, investors: 124384, market_share: 10, fee: 2.9,
  returns: { "1m": -11, "3m": -12, "6m": -13, ytd: 0.3, "1y": 8.68, "3y": 171, "5y": 510 }, real_1y: -16.2, usd_1y: -8.8,
  metrics: { volatility: 27.7, max_drawdown: -22.5, sharpe: -1.15 }, category_rank: { rank: 99, of: 170, by: "1y" }, category_median_1y: 11.09,
  benchmarks: { cpi: 29.77, usd: 19.17, deposit: 40.54 }, allocation: null, prices: [], source: "TEFAS", ...o });

test("describeFund nötr, veriye dayalı paragraflar üretir", () => {
  const p = describeFund(detail());
  assert.equal(p.length, 4);
  assert.match(p[1], /medyan/);
  assert.match(p[1], /99\. sırada/);
  assert.match(p[2], /reel/);
  assert.doesNotMatch(p.join(" "), /\b(al|sat|öneriyoruz|tavsiye ederiz)\b/i);
});

test("describeFund eksik veriyi yazmaz", () => {
  const p = describeFund(detail({ returns: { "1m": null, "3m": null, "6m": null, ytd: null, "1y": null, "3y": null, "5y": null }, fee: null,
    metrics: { volatility: null, max_drawdown: null, sharpe: null } }));
  assert.equal(p.length, 1);
  assert.doesNotMatch(p[0], /yönetim ücreti/);
});

test("loadFund geçersiz kodu reddeder (yol gezintisi)", () => {
  assert.equal(loadFund("../universe"), null);
  assert.equal(loadFund(""), null);
});
