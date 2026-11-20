import { SITE_URL } from "@/lib/config";
import { Suspense } from "react";
import type { Metadata } from "next";
import Link from "next/link";
import { FundScreener } from "@/components/FundScreener";
import { FundDisclaimer } from "@/components/FundDisclaimer";
import { categoryGroups, fmtPct, topBy } from "@/lib/funds";
import { loadFundUniverse } from "@/lib/funds-data";

export const metadata: Metadata = {
  title: "Yatırım Fonları Tarayıcı — Getiri, Risk, Büyüklük",
  description:
    "TEFAS'ta işlem gören en büyük yatırım fonlarını getiri, reel getiri, oynaklık, maksimum düşüş ve yönetim ücretine göre sıralayın. Yatırım tavsiyesi değildir.",
  alternates: { canonical: `${SITE_URL}/fonlar` },
};

export default function FonlarPage() {
  const u = loadFundUniverse();
  const cats = u ? categoryGroups(u.funds) : [];
  const leaders = u ? topBy(u.funds, "r1y", 5) : [];

  return (
    <div className="container mx-auto px-6 py-10">
      <header className="mb-8 max-w-2xl">
        <h1 className="text-3xl md:text-4xl font-display font-bold mb-3">Fon Tarayıcı</h1>
        <p className="text-sm text-zinc-400 leading-relaxed">
          {u ? `TEFAS'ta işlem gören en büyük ${u.count} yatırım fonu` : "TEFAS fonları"}: getiri, reel getiri, oynaklık ve maksimum düşüş. Başlıklara
          tıklayarak sıralayın, kategoriyle daraltın, fonun adına tıklayıp ayrıntısına gidin.
        </p>
      </header>

      {u ? (
        <>
          <nav aria-label="Fon kategorileri" className="flex flex-wrap gap-2 mb-6">
            {cats.map((c) => (
              <Link key={c.slug} href={`/fonlar/kategori/${c.slug}`} className="px-3 py-2 rounded-full text-xs border border-zinc-800 bg-zinc-900 text-zinc-300 hover:text-white hover:border-zinc-600 min-h-[44px] inline-flex items-center">
                {c.name} <span className="ml-1.5 text-zinc-400">({c.funds.length})</span>
              </Link>
            ))}
          </nav>

          {leaders.length > 0 && (
            <p className="text-xs text-zinc-400 mb-4">
              Son 1 yılda en yüksek getiri:{" "}
              {leaders.map((l, i) => (
                <span key={l.code}>
                  {i > 0 && ", "}
                  <Link href={`/fon/${l.code}`} className="font-mono text-zinc-200 hover:text-white underline-offset-2 hover:underline">{l.code}</Link> {fmtPct(l.r1y)}
                </span>
              ))}
              . Geçmiş getiri gelecekteki getiriyi garanti etmez.
            </p>
          )}

          <Suspense fallback={<p className="text-sm text-zinc-400">Yükleniyor…</p>}>
            <FundScreener funds={u.funds} categories={cats.map((c) => c.name)} />
          </Suspense>
        </>
      ) : (
        <p className="text-sm text-zinc-400">Fon verisi henüz üretilmedi.</p>
      )}

      <div className="mt-8 max-w-3xl">
        <FundDisclaimer updatedAt={u?.updated_at} />
      </div>
    </div>
  );
}
