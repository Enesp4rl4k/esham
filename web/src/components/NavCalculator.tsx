"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { Layers } from "lucide-react";
import { nav, stakeValue, type Stake } from "@/lib/nav";

interface Props {
  ticker: string;
  price: number; // TL
  holdingMcap: number; // TL
  stakes: Stake[];
  source: string;
  fetchedAt: string;
}

const nf2 = new Intl.NumberFormat("tr-TR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const nf1 = new Intl.NumberFormat("tr-TR", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
const mr = (v: number) => `${nf1.format(v / 1e9)} Mr ₺`;

export function NavCalculator({ ticker, price, holdingMcap, stakes, source, fetchedAt }: Props) {
  // girdiler milyar ₺
  const [unlisted, setUnlisted] = useState("0");
  const [debt, setDebt] = useState("0");
  const num = (s: string) => {
    const v = parseFloat(s.replace(",", "."));
    return Number.isFinite(v) ? v : 0;
  };

  const r = useMemo(
    () => nav({ stakes, holdingMcap, price, unlistedValue: num(unlisted) * 1e9, netDebt: num(debt) * 1e9 }),
    [stakes, holdingMcap, price, unlisted, debt],
  );
  if (!r) return null;

  const listed = stakes.filter((s) => s.mcap !== null).sort((a, b) => (stakeValue(b) ?? 0) - (stakeValue(a) ?? 0));
  const unvalued = stakes.filter((s) => s.mcap === null).sort((a, b) => b.pct - a.pct);
  const partial = num(unlisted) === 0;
  const date = new Date(fetchedAt).toLocaleDateString("tr-TR", { day: "numeric", month: "long", year: "numeric" });

  return (
    <div className="rounded-2xl border border-zinc-800 bg-zinc-950/80 p-5 md:p-6 shadow-xl">
      <div className="flex flex-wrap items-center justify-between gap-3 pb-4 border-b border-zinc-800/80 mb-5">
        <div className="flex items-center gap-2">
          <span className="p-1.5 rounded-lg bg-violet-500/10 text-violet-300 border border-violet-500/20"><Layers className="w-4 h-4" /></span>
          <h3 className="text-base font-bold text-white tracking-tight">NAV (Net Aktif Değer) · {ticker}</h3>
        </div>
        <span className="text-xs text-zinc-400">Pay oranları: {source}, {date}</span>
      </div>

      <div className="rounded-xl border border-amber-500/30 bg-amber-500/10 p-4 mb-6 text-sm text-amber-100 leading-relaxed">
        <b>{partial ? "Kısmi NAV." : "Elle girilen değerlerle NAV."}</b> KAP yalnızca <b>doğrudan</b> payları verir; ara holdingler üzerinden gelen
        dolaylı paylar (örneğin bir alt holdingin tuttuğu halka açık şirketler) dâhil değildir. Listelenmeyen iştiraklerin ve holding düzeyindeki
        borcun değerini aşağıya siz girin; girmezseniz NAV bu kalemleri 0 sayar.
      </div>

      <div className="grid gap-8 lg:grid-cols-2">
        <div className="space-y-5">
          <div>
            <label htmlFor="nav-unlisted" className="block text-sm font-medium text-zinc-200 mb-1">Listelenmeyen iştiraklerin değeri (milyar ₺)</label>
            <input id="nav-unlisted" inputMode="decimal" value={unlisted} onChange={(e) => setUnlisted(e.target.value)}
              className="w-full px-3 py-2.5 rounded-lg bg-zinc-900 border border-zinc-800 text-base font-mono text-white focus:outline-none focus-visible:border-amber-500/60 focus-visible:ring-2 focus-visible:ring-amber-500/30" />
            <p className="text-xs text-zinc-400 mt-1">Borsada işlem görmeyen {unvalued.length} iştirak (aşağıdaki liste) için kendi tahmininiz, örneğin defter değeri.</p>
          </div>
          <div>
            <label htmlFor="nav-debt" className="block text-sm font-medium text-zinc-200 mb-1">Holding düzeyi net borç (milyar ₺)</label>
            <input id="nav-debt" inputMode="decimal" value={debt} onChange={(e) => setDebt(e.target.value)}
              className="w-full px-3 py-2.5 rounded-lg bg-zinc-900 border border-zinc-800 text-base font-mono text-white focus:outline-none focus-visible:border-amber-500/60 focus-visible:ring-2 focus-visible:ring-amber-500/30" />
            <p className="text-xs text-zinc-400 mt-1">Yalnızca holding şirketin kendi net borcu (konsolide değil). Net nakit için negatif girin.</p>
          </div>
        </div>

        <div className="rounded-xl border border-zinc-800 bg-zinc-900/70 p-5">
          <p className="text-sm text-zinc-300">{partial ? "Kısmi " : ""}NAV / hisse</p>
          <p className="font-mono text-4xl font-bold text-white tabular-nums mt-1">{nf2.format(r.navPerShare)} ₺</p>
          <div className="flex flex-wrap gap-x-6 gap-y-1 mt-3 text-sm">
            <span className="text-zinc-300">Fiyat: <b className="font-mono text-white tabular-nums">{nf2.format(price)} ₺</b></span>
            {r.discount !== null && !partial && (
              <span className={r.discount <= 0 ? "text-emerald-400" : "text-rose-300"}>
                {r.discount <= 0 ? "İskonto" : "Prim"}: <b className="font-mono tabular-nums">%{nf1.format(Math.abs(r.discount) * 100)}</b>
              </span>
            )}
            {partial && <span className="text-zinc-400">Prim/iskonto, listelenmeyen değeri girene kadar gösterilmez (kısmi NAV yanıltır).</span>}
          </div>
          <dl className="mt-4 space-y-1.5 text-sm font-mono tabular-nums">
            {([
              ["Listelenmiş doğrudan paylar", mr(r.listedValue)],
              ["(+) Listelenmeyen (girdi)", mr(num(unlisted) * 1e9)],
              ["(−) Holding net borcu (girdi)", mr(num(debt) * 1e9)],
              ["NAV", mr(r.nav)],
              ["Holding piyasa değeri", mr(holdingMcap)],
            ] as const).map(([k, v], i) => (
              <div key={k} className={`flex justify-between gap-3 ${i === 3 ? "font-bold text-white border-t border-zinc-800 pt-1.5" : "text-zinc-300"}`}>
                <dt className="font-sans font-normal">{k}</dt>
                <dd>{v}</dd>
              </div>
            ))}
          </dl>
          {r.coverage > 1 && (
            <p className="mt-3 text-xs text-zinc-400">Listelenmiş doğrudan paylar holdingin piyasa değerinin %{nf1.format(r.coverage * 100)}&apos;i; bu, holding düzeyindeki borç ve ara şirketlerin (dolaylı) etkisini girdilerle tamamlamanız gerektiğini gösterir.</p>
          )}
        </div>
      </div>

      <div className="mt-8 overflow-x-auto">
        <table className="w-full text-sm min-w-[560px]">
          <caption className="text-left text-xs font-bold uppercase tracking-wider text-zinc-400 pb-2">Borsada işlem gören doğrudan paylar</caption>
          <thead className="text-zinc-400">
            <tr>
              <th scope="col" className="text-left font-medium py-2">İştirak</th>
              <th scope="col" className="text-left font-medium py-2">Tür</th>
              <th scope="col" className="text-right font-medium py-2">Pay</th>
              <th scope="col" className="text-right font-medium py-2">Piyasa değeri</th>
              <th scope="col" className="text-right font-medium py-2">Paya düşen</th>
              <th scope="col" className="text-right font-medium py-2">NAV içi pay</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-900 font-mono tabular-nums text-zinc-300">
            {listed.map((s) => {
              const v = stakeValue(s) as number;
              return (
                <tr key={s.title}>
                  <th scope="row" className="py-2.5 text-left font-sans font-normal">
                    {s.ticker ? <Link href={`/hisse/${s.ticker}`} className="font-mono font-bold text-white hover:underline">{s.ticker}</Link> : null}
                    <span className="ml-2 text-xs text-zinc-400">{s.title}</span>
                  </th>
                  <td className="py-2.5 text-left font-sans text-xs text-zinc-400">{s.relation}</td>
                  <td className="py-2.5 text-right">%{nf2.format(s.pct)}</td>
                  <td className="py-2.5 text-right">{mr(s.mcap as number)}</td>
                  <td className="py-2.5 text-right text-white">{mr(v)}</td>
                  <td className="py-2.5 text-right">{r.nav > 0 ? `%${nf1.format((v / r.nav) * 100)}` : "—"}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {unvalued.length > 0 && (
        <details className="mt-6 text-sm text-zinc-300">
          <summary className="cursor-pointer text-zinc-200 font-medium">Değeri hesaplanamayan {unvalued.length} iştirak (listelenmemiş ya da veri dışı)</summary>
          <ul className="mt-3 grid gap-x-8 gap-y-1 sm:grid-cols-2 text-xs text-zinc-400">
            {unvalued.map((s) => (
              <li key={s.title} className="flex justify-between gap-3">
                <span>{s.title}</span>
                <span className="font-mono tabular-nums text-zinc-300">%{nf2.format(s.pct)}</span>
              </li>
            ))}
          </ul>
        </details>
      )}

      <p className="mt-6 text-xs text-zinc-400 leading-relaxed border-t border-zinc-800/80 pt-4">
        Piyasa değerleri Yahoo Finance kaynaklıdır. Ünvanlardan hisse koduna eşleştirme otomatiktir ve hatalı olabilir. NAV iskontosu bir değerleme
        göstergesidir, yatırım tavsiyesi değildir.
      </p>
    </div>
  );
}
