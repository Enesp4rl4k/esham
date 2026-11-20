/** Fon JSON okuyucuları (sunucu tarafı, build zamanı). Dosya yoksa boş döner; sayfalar zarifçe düşmelidir. */
import fs from "fs";
import path from "path";
import type { FundDetail, FundUniverse } from "./funds";

const DATA = () => path.join(process.cwd(), "public", "data");
let uniCache: FundUniverse | null | undefined;

export function loadFundUniverse(): FundUniverse | null {
  if (uniCache !== undefined) return uniCache;
  try {
    uniCache = JSON.parse(fs.readFileSync(path.join(DATA(), "universe-funds.json"), "utf-8")) as FundUniverse;
  } catch {
    uniCache = null;
  }
  return uniCache;
}

export function loadFund(code: string): FundDetail | null {
  if (!/^[A-Z0-9]{2,6}$/.test(code)) return null;
  try {
    return JSON.parse(fs.readFileSync(path.join(DATA(), "funds", `${code}.json`), "utf-8")) as FundDetail;
  } catch {
    return null;
  }
}

export const getFundCodes = (): string[] => loadFundUniverse()?.funds.map((f) => f.code) ?? [];

