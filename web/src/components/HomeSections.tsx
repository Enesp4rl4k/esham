"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";
import { ArrowDown, ArrowUp, RotateCcw, SlidersHorizontal, X } from "lucide-react";
import { PRE_PAINT_SCRIPT, clear, move, normalize, read, toggle, visibleOrder, write, type HomeLayout } from "@/lib/home-layout";

export interface HomeSection {
  id: string;
  label: string;
  description: string;
  node: ReactNode;
}

export interface HomePreset {
  id: string;
  label: string;
  hint: string;
  layout: HomeLayout;
}

/**
 * Ana sayfa bölümleri: kullanıcı sırayı değiştirir, bölüm gizler/gösterir, hazır düzen seçer.
 * Tercih tarayıcıda saklanır (localStorage); yoksa varsayılan (haber odaklı) düzen.
 * Bölümler sunucuda üretilip ``node`` olarak gelir, burada yalnızca yerleştirilir.
 */
export function HomeSections({ sections, defaults, presets }: { sections: HomeSection[]; defaults: HomeLayout; presets: HomePreset[] }) {
  const ids = sections.map((s) => s.id);
  const [layout, setLayout] = useState<HomeLayout>(defaults);
  const [custom, setCustom] = useState(false); // kullanıcı varsayılandan farklı bir düzen mi seçmiş
  const dialog = useRef<HTMLDialogElement>(null);
  const opener = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    // ön-boyama stili görevini yaptı: şimdi düzen React/DOM sırasıyla uygulanır
    const stored = read(ids, defaults);
    setLayout(stored);
    setCustom(JSON.stringify(stored) !== JSON.stringify(normalize(null, ids, defaults)));
    document.getElementById("home-pre")?.remove();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const apply = (l: HomeLayout) => {
    setLayout(l);
    write(l);
    setCustom(JSON.stringify(l) !== JSON.stringify(defaults));
  };
  const reset = () => {
    clear();
    setLayout(defaults);
    setCustom(false);
  };

  const byId = new Map(sections.map((s) => [s.id, s]));
  const shown = visibleOrder(layout);

  const open = () => dialog.current?.showModal();
  const close = () => dialog.current?.close();

  return (
    <>
      <div className="container mx-auto px-6">
        <div className="flex items-center justify-end gap-3 pt-3">
          {custom && <span className="text-xs text-zinc-400">Özel düzen kullanılıyor</span>}
          <button
            ref={opener}
            type="button"
            onClick={open}
            className="inline-flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm border border-zinc-800 bg-zinc-900 text-zinc-300 hover:text-white hover:border-zinc-600 transition-colors"
          >
            <SlidersHorizontal className="w-4 h-4" aria-hidden="true" /> Sayfayı düzenle
          </button>
        </div>
      </div>

      <div className="flex flex-col">
        {shown.map((id) => (
          <div key={id} data-home-section={id}>
            {byId.get(id)?.node}
          </div>
        ))}
      </div>
      <script dangerouslySetInnerHTML={{ __html: PRE_PAINT_SCRIPT }} />

      <dialog
        ref={dialog}
        onClick={(e) => e.target === dialog.current && close()}
        onKeyDown={(e) => e.key === "Escape" && close()}
        onClose={() => opener.current?.focus()}
        aria-labelledby="home-edit-title"
        className="m-auto w-[min(40rem,calc(100vw-2rem))] max-h-[85vh] overflow-y-auto rounded-2xl border border-zinc-800 bg-zinc-950 p-0 text-zinc-100 shadow-2xl backdrop:bg-black/70"
      >
        <div className="sticky top-0 z-10 flex items-center justify-between gap-3 border-b border-zinc-800 bg-zinc-950 px-5 py-4">
          <h2 id="home-edit-title" className="text-lg font-display font-bold">Ana sayfayı düzenle</h2>
          <button type="button" onClick={close} aria-label="Kapat" className="p-2 rounded-lg text-zinc-300 hover:text-white hover:bg-zinc-900">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="px-5 py-4 space-y-6">
          <section aria-labelledby="home-presets">
            <h3 id="home-presets" className="text-sm font-semibold text-zinc-200 mb-2">Hazır düzenler</h3>
            <div className="grid gap-2 sm:grid-cols-3">
              {presets.map((p) => (
                <button
                  key={p.id}
                  type="button"
                  onClick={() => apply(normalize(p.layout, ids, defaults))}
                  className="text-left p-3 rounded-xl border border-zinc-800 bg-zinc-900 hover:border-amber-500/50 transition-colors"
                >
                  <span className="block text-sm font-medium text-white">{p.label}</span>
                  <span className="block text-xs text-zinc-400 mt-0.5">{p.hint}</span>
                </button>
              ))}
            </div>
          </section>

          <section aria-labelledby="home-sections">
            <h3 id="home-sections" className="text-sm font-semibold text-zinc-200 mb-2">Bölümler</h3>
            <ol className="divide-y divide-zinc-900 rounded-xl border border-zinc-800">
              {layout.order.map((id, i) => {
                const s = byId.get(id);
                if (!s) return null;
                const on = !layout.hidden.includes(id);
                return (
                  <li key={id} className="flex items-center gap-3 px-3 py-2.5">
                    <input
                      id={`home-toggle-${id}`}
                      type="checkbox"
                      checked={on}
                      onChange={() => apply(toggle(layout, id))}
                      className="h-5 w-5 accent-amber-400 shrink-0"
                    />
                    <label htmlFor={`home-toggle-${id}`} className="flex-1 min-w-0 cursor-pointer">
                      <span className={`block text-sm font-medium ${on ? "text-white" : "text-zinc-400"}`}>{s.label}</span>
                      <span className="block text-xs text-zinc-400 truncate">{s.description}</span>
                    </label>
                    <div className="flex gap-1 shrink-0">
                      <button
                        type="button"
                        onClick={() => apply(move(layout, id, -1))}
                        disabled={i === 0}
                        aria-label={`${s.label} bölümünü yukarı taşı`}
                        className="p-2 rounded-lg border border-zinc-800 text-zinc-300 hover:text-white hover:border-zinc-600 disabled:opacity-30 disabled:cursor-not-allowed"
                      >
                        <ArrowUp className="w-4 h-4" />
                      </button>
                      <button
                        type="button"
                        onClick={() => apply(move(layout, id, 1))}
                        disabled={i === layout.order.length - 1}
                        aria-label={`${s.label} bölümünü aşağı taşı`}
                        className="p-2 rounded-lg border border-zinc-800 text-zinc-300 hover:text-white hover:border-zinc-600 disabled:opacity-30 disabled:cursor-not-allowed"
                      >
                        <ArrowDown className="w-4 h-4" />
                      </button>
                    </div>
                  </li>
                );
              })}
            </ol>
          </section>
        </div>

        <div className="sticky bottom-0 flex items-center justify-between gap-3 border-t border-zinc-800 bg-zinc-950 px-5 py-3">
          <button type="button" onClick={reset} className="inline-flex items-center gap-2 text-sm text-zinc-300 hover:text-white">
            <RotateCcw className="w-4 h-4" aria-hidden="true" /> Varsayılana dön
          </button>
          <button type="button" onClick={close} className="px-4 py-2 rounded-lg text-sm font-semibold text-black" style={{ background: "var(--accent)" }}>
            Tamam
          </button>
        </div>
        <p className="px-5 pb-4 text-xs text-zinc-400">Tercihleriniz yalnızca bu tarayıcıda saklanır.</p>
      </dialog>
    </>
  );
}
