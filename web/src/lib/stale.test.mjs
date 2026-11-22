import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { isStale, staleLabel, freshOnly, runScan, sectorStats, SCANS, STALE_ROW_HOURS } from "./programmatic.ts";

const NOW = Date.parse("2026-11-24T12:00:00Z");
const hoursAgo = (h) => new Date(NOW - h * 3600 * 1000).toISOString();
const row = (t, extra = {}) => ({ ticker: t, name: t, sector: "S", financial: false, price: 1, as_of: "2026-09-30", suspect: false,
  market_cap: 1e10, pe: 5, pb: 1, ev_ebitda: 4, roe: 20, net_margin: 10, dividend_yield: 3, net_debt_ebitda: 1, updated_at: hoursAgo(2), ...extra });

test("bayat: bot bayrağı, eşik aşımı ve tarihsiz satır", () => {
  assert.equal(isStale(row("A"), NOW), false);
  assert.equal(isStale(row("B", { stale: true }), NOW), true);
  assert.equal(isStale(row("C", { updated_at: hoursAgo(STALE_ROW_HOURS + 1) }), NOW), true);
  assert.equal(isStale(row("D", { updated_at: undefined }), NOW), true);
  assert.equal(staleLabel(row("C", { updated_at: "2026-11-10T00:00:00Z" })), "bayat — son veri: 2026-11-10");
});

test("bayat satır sıralama ve tarama sonuçlarına girmez, sektör medyanını bozmaz", () => {
  const u = { updated_at: new Date().toISOString(), count: 3, sector_median: {}, stocks: [row("A"), row("B", { stale: true, pe: 1 }), row("C", { pe: 9 })] };
  const sc = { ...SCANS[0], metric: "pe", dir: 1, test: () => true };
  assert.deepEqual(runScan(u, sc).map((s) => s.ticker).sort(), ["A", "C"]);
  const st = sectorStats(u.stocks);
  assert.equal(st.staleCount, 1);
  assert.equal(st.pe, 7); // A(5) ve C(9); bayat B(1) medyana girmez (dahil olsaydı 5 çıkardı)
  assert.deepEqual(freshOnly([row("A"), row("B", { stale: true })]).map((s) => s.ticker), ["A"]);
});

test("her görünümde bayat işareti kodda var (screener, sektör/tarama tablosu, karşılaştırma, fon, takvim)", () => {
  const read = (p) => readFileSync(new URL(p, import.meta.url), "utf8");
  for (const f of ["../components/StockTable.tsx", "../components/StockScreener.tsx", "../app/karsilastir/[pair]/page.tsx"]) {
    const src = read(f);
    assert.match(src, /isStale\(/, f);
    assert.match(src, /data-stale-row/, f);
  }
  assert.match(read("../components/FundScreener.tsx"), /bayat — son veri/);
  assert.match(read("../components/MorningCockpit.tsx"), /Takvim güncel değil/);
  // dosya düzeyi tarih artık "itibarıyla" diye veri tarihi gibi sunulmaz
  for (const f of ["../app/hisseler/sektor/[slug]/page.tsx", "../app/hisseler/tarama/[slug]/page.tsx", "../app/karsilastir/[pair]/page.tsx"]) {
    assert.doesNotMatch(read(f), /\{date\} itibarıyla|updated_at\.slice\(0, 10\)\} itibarıyla/, f);
    assert.match(read(f), /tarama zamanı/i, f);
  }
});
