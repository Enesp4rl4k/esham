import type { ReactNode } from "react";

/** Yasal/kurumsal sayfalar için ortak, okunaklı düzen. */
export function LegalPage({ title, updated, children }: { title: string; updated: string; children: ReactNode }) {
  return (
    <div className="container mx-auto px-6 py-10 max-w-3xl">
      <h1 className="text-3xl md:text-4xl font-display font-bold mb-2">{title}</h1>
      <p className="text-sm text-zinc-400 mb-8">Son güncelleme: {updated}</p>
      <div className="space-y-4 text-base text-zinc-300 leading-relaxed [&_h2]:text-xl [&_h2]:font-display [&_h2]:font-semibold [&_h2]:text-white [&_h2]:mt-8 [&_h2]:mb-2 [&_ul]:list-disc [&_ul]:pl-5 [&_ul]:space-y-1.5 [&_a]:underline">
        {children}
      </div>
    </div>
  );
}
