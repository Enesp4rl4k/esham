import { test } from "node:test";
import assert from "node:assert/strict";
import { median, sectorPositions } from "./sector.ts";

const mk = (ticker, o = {}) => ({
  ticker, name: ticker, sector: "S", financial: false, price: 1, as_of: "2026-09-30", suspect: false,
  market_cap: 1e10, pe: null, pb: null, ev_ebitda: null, roe: null, net_margin: null, dividend_yield: null, net_debt_ebitda: null, ...o,
});

test("median: tek/çift sayıda eleman", () => {
  assert.equal(median([3, 1, 2]), 2);
  assert.equal(median([1, 2, 3, 4]), 2.5);
  assert.equal(median([]), null);
});

test("sıra: F/K'da düşük iyi, ROE'de yüksek iyi", () => {
  const all = [mk("A", { pe: 5, roe: 10 }), mk("B", { pe: 8, roe: 30 }), mk("C", { pe: 12, roe: 20 }), mk("D", { pe: 20, roe: 5 })];
  const a = sectorPositions(all[0], all);
  const pe = a.find((m) => m.def.key === "pe");
  const roe = a.find((m) => m.def.key === "roe");
  assert.equal(pe.rank, 1);   // en düşük F/K = 1.
  assert.equal(roe.rank, 3);  // 10 → 30 ve 20'nin altında
  assert.equal(pe.of, 4);
  assert.equal(pe.median, 10); // (8+12)/2
});

test("şüpheli hisseler istatistikten hariç; zarar eden (F/K null) için sıra yok", () => {
  const all = [mk("A", { pe: 5 }), mk("B", { pe: 8 }), mk("C", { pe: 12 }), mk("X", { pe: 0.5, suspect: true }), mk("L", { pe: null })];
  const pos = sectorPositions(all[0], all).find((m) => m.def.key === "pe");
  assert.equal(pos.of, 3);          // X sayılmaz, L'nin değeri yok
  assert.equal(pos.rank, 1);        // X (0.5) olsaydı 2. olurdu
  const loss = sectorPositions(all[4], all).find((m) => m.def.key === "pe");
  assert.equal(loss.value, null);
  assert.equal(loss.rank, null);
});

test("sektörde 3'ten az geçerli değer varsa medyan ve sıra yok", () => {
  const all = [mk("A", { pe: 5 }), mk("B", { pe: 8 })];
  const pos = sectorPositions(all[0], all).find((m) => m.def.key === "pe");
  assert.equal(pos.median, null);
  assert.equal(pos.rank, null);
});

test("finansal şirkette FD/FAVÖK ve Net borç/FAVÖK yok", () => {
  const bank = mk("B", { financial: true, pe: 5 });
  const keys = sectorPositions(bank, [bank]).map((m) => m.def.key);
  assert.ok(!keys.includes("ev_ebitda") && !keys.includes("net_debt_ebitda"));
});

test("konum 0-1 aralığına sıkıştırılır (uç değer çubuğu bozmaz)", () => {
  const all = [mk("A", { roe: 10 }), mk("B", { roe: 12 }), mk("C", { roe: 14 }), mk("D", { roe: 16 }), mk("E", { roe: 190 })];
  const e = sectorPositions(all[4], all).find((m) => m.def.key === "roe");
  assert.equal(e.pos, 1);
  const a = sectorPositions(all[0], all).find((m) => m.def.key === "roe");
  assert.ok(a.pos >= 0 && a.pos <= 1);
});
