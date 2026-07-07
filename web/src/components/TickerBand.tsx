/**
 * Canlı fiyat bandı — /public/data/market-ticker.json'dan okur.
 *
 * Statik export uyumlu: Next.js API route yerine bot tarafından her 15 dk'da
 * bir güncellenen JSON dosyasını build sırasında okur. Dosya yoksa veya
 * bozuksa kategori linkleri fallback'e düşer.
 */
import Link from "next/link";
import { promises as fs } from "fs";
import path from "path";
import { TrendingUp, TrendingDown, Minus } from "lucide-react";
import { CATEGORIES, type CategorySlug } from "@/lib/content";

interface TickerItem {
  label: string;
  value: string;
  change: string;
  up: boolean;
}

interface TickerData {
  updatedAt: string;
  tickers: TickerItem[];
}

async function loadTickerData(): Promise<TickerData | null> {
  try {
    const filePath = path.join(process.cwd(), "public", "data", "market-ticker.json");
    const raw = await fs.readFile(filePath, "utf-8");
    return JSON.parse(raw) as TickerData;
  } catch {
    return null;
  }
}

/** Değişim rengini belirle */
function changeColor(up: boolean, change: string): string {
  if (change === "0,00%" || change === "+0,00%") return "var(--text-muted)";
  return up ? "var(--color-up, #22c55e)" : "var(--color-down, #ef4444)";
}

export async function TickerBand() {
  const data = await loadTickerData();

  // Fiyat verisi varsa canlı ticker göster
  if (data && data.tickers.length > 0) {
    const items = data.tickers;

    return (
      <div
        className="border-b overflow-hidden"
        style={{ borderColor: "var(--border)", background: "var(--surface)" }}
        role="marquee"
        aria-label="Piyasa fiyatları"
      >
        <div className="flex whitespace-nowrap ticker-tape">
          {[...Array(3)].map((_, i) => (
            <div
              key={i}
              className="flex items-center gap-6 px-8 py-2 text-xs"
              aria-hidden={i > 0}
            >
              {items.map((item) => {
                const color = changeColor(item.up, item.change);
                return (
                  <span
                    key={`${i}-${item.label}`}
                    className="flex items-center gap-2"
                    style={{ color: "var(--text-secondary)" }}
                  >
                    <span
                      className="font-bold tracking-wider text-[10px] uppercase"
                      style={{ color: "var(--text-muted)" }}
                    >
                      {item.label}
                    </span>
                    <span className="font-semibold" style={{ color }}>
                      {item.value}
                    </span>
                    <span
                      className="flex items-center gap-0.5 text-[10px]"
                      style={{ color }}
                    >
                      {item.change.startsWith("+") ? (
                        <TrendingUp className="w-3 h-3" aria-hidden="true" />
                      ) : item.change.startsWith("-") ? (
                        <TrendingDown className="w-3 h-3" aria-hidden="true" />
                      ) : (
                        <Minus className="w-3 h-3" aria-hidden="true" />
                      )}
                      {item.change}
                    </span>
                    <span
                      className="opacity-20 select-none"
                      aria-hidden="true"
                    >
                      ·
                    </span>
                  </span>
                );
              })}
              <span
                style={{ color: "var(--accent)" }}
                className="font-medium text-[10px]"
                aria-hidden="true"
              >
                Esham — Yapay Zeka Piyasa Analizi
              </span>
              <span className="opacity-20 select-none" aria-hidden="true">·</span>
            </div>
          ))}
        </div>
        {/* Güncelleme zamanı — ekran okuyucu için gizli */}
        <span className="sr-only">
          Son güncelleme: {new Date(data.updatedAt).toLocaleString("tr-TR")}
        </span>
      </div>
    );
  }

  // Fallback: kategori linkleri (eski davranış)
  const catColors: Record<CategorySlug, string> = {
    bist:      "text-sky-400",
    global:    "text-violet-400",
    ipo:       "text-emerald-400",
    viop:      "text-orange-400",
    gundem:    "text-amber-400",
    kripto:    "text-orange-300",
    teknoloji: "text-pink-400",
  };

  return (
    <div
      className="border-b overflow-hidden"
      style={{ borderColor: "var(--border)", background: "var(--surface)" }}
    >
      <div className="flex whitespace-nowrap ticker-tape">
        {[...Array(2)].map((_, i) => (
          <div
            key={i}
            className="flex items-center gap-8 px-8 py-2 text-xs"
            style={{ color: "var(--text-muted)" }}
            aria-hidden={i > 0}
          >
            {(Object.keys(CATEGORIES) as CategorySlug[]).map((slug) => (
              <Link
                key={slug}
                href={`/kategori/${slug}`}
                className={`flex items-center gap-2 hover:opacity-70 transition-opacity ${catColors[slug]}`}
              >
                <span className="font-semibold uppercase tracking-wider text-[10px]">
                  {CATEGORIES[slug].label}
                </span>
              </Link>
            ))}
            <span className="opacity-30" aria-hidden="true">·</span>
            <span style={{ color: "var(--accent)" }} className="font-medium">
              Esham — Yapay Zeka Piyasa Analizi
            </span>
            <span className="opacity-30" aria-hidden="true">·</span>
          </div>
        ))}
      </div>
    </div>
  );
}
