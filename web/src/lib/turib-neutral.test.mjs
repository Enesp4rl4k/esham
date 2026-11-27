import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { neutralizeTuribDataset, arbitrageLevelLabel } from "./turib-neutral.ts";
import { findBanned } from "./neutral.ts";

test("tarım veri seti istemciye 'fırsat'/'kâr kalır'/tahmin metni taşımaz", () => {
  const raw = JSON.parse(readFileSync(new URL("../../public/data/turib-market.json", import.meta.url), "utf-8"));
  const out = JSON.stringify(neutralizeTuribDataset(raw));
  for (const bad of ["FIRSAT", "kâr kalır", "yansıyacak", "pozitif destekler", "kâr yazabilir", "Marj Baskısı"]) {
    assert.ok(!out.includes(bad), bad);
  }
  assert.deepEqual(findBanned(out), []);
});

test("eski ve yeni arbitraj sınıfları aynı tarafsız etikete çevrilir", () => {
  assert.equal(arbitrageLevelLabel("YUKSEK_FIRSAT"), arbitrageLevelLabel("NET_FARK_0_50_USTU"));
  assert.equal(arbitrageLevelLabel("SINIRLI_FIRSAT"), "Net fark 0–0,50 ₺/kg");
  assert.equal(arbitrageLevelLabel("ARBITRAJ_YOK"), "Net fark yok");
});
