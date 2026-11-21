import Link from "next/link";
import {
  TrendingUp,
  TrendingDown,
  Activity,
  Layers,
  Globe2,
  Wheat,
  Coins,
  ArrowRight,
} from "lucide-react";

type MatrixItem = {
  label: string;
  sublabel: string;
  value: string;
  change: string;
  up: boolean | null;
  href?: string;
};

const NO_DATA = "Veri yok";

type MarketMatrixProps = {
  tickerData?: any;
  turibData?: any;
};

export function MarketMatrix({ tickerData, turibData }: MarketMatrixProps) {
  const getTicker = (key: string) => {
    return tickerData?.tickers?.find(
      (t: any) => t.label.toUpperCase() === key.toUpperCase()
    );
  };

  const xu100 = getTicker("XU100");
  const sp500 = getTicker("S&P 500");
  const nasdaq = getTicker("NASDAQ");
  const usdtry = getTicker("USD/TRY");
  const eurusd = getTicker("EUR/USD");
  const brent = getTicker("BRENT");
  const altin = getTicker("ALTIN");
  const abd10y = getTicker("ABD 10Y");

  // TÜRİB verileri
  const trbHub = turibData?.indices?.find((i: any) => i.code === "TRBHUB");
  const bugdaySpot = turibData?.spotCommodities?.find((p: any) =>
    p.name.includes("BUĞDAY")
  );

  // Kripto verileri
  const btc = getTicker("BITCOIN"); // Bot şu an Bitcoin kotasyonu yayınlamıyor: "Veri yok" gösterilir

  // Statik sayfa: veri, botun son yayın anını taşır; "canlı" değildir.
  const asOf: string | null = tickerData?.updatedAt
    ? new Date(tickerData.updatedAt).toLocaleString("tr-TR", { timeZone: "Europe/Istanbul" })
    : null;

  const sections: {
    title: string;
    icon: any;
    items: MatrixItem[];
  }[] = [
    {
      title: "BIST & Küresel Endeksler",
      icon: Activity,
      items: [
        {
          label: "BIST 100",
          sublabel: "XU100.IS",
          value: xu100?.value ?? NO_DATA,
          change: xu100?.change ?? "",
          up: xu100?.up ?? null,
          href: "/kategori/bist",
        },
        {
          label: "S&P 500",
          sublabel: "ABD Geniş Piyasa",
          value: sp500?.value ?? NO_DATA,
          change: sp500?.change ?? "",
          up: sp500?.up ?? null,
          href: "/kategori/global",
        },
        {
          label: "NASDAQ",
          sublabel: "Teknoloji Endeksi",
          value: nasdaq?.value ?? NO_DATA,
          change: nasdaq?.change ?? "",
          up: nasdaq?.up ?? null,
          href: "/kategori/teknoloji",
        },
      ],
    },
    {
      title: "Döviz, Faiz & VİOP",
      icon: Globe2,
      items: [
        {
          label: "Dolar / TL",
          sublabel: "USD/TRY Spot",
          value: usdtry?.value ?? NO_DATA,
          change: usdtry?.change ?? "",
          up: usdtry?.up ?? null,
          href: "/kategori/global",
        },
        {
          label: "EUR / USD",
          sublabel: "Parite",
          value: eurusd?.value ?? NO_DATA,
          change: eurusd?.change ?? "",
          up: eurusd?.up ?? null,
          href: "/kategori/global",
        },
        {
          label: "ABD 10Y Tahvil",
          sublabel: "Gösterge Faiz",
          value: abd10y?.value ?? NO_DATA,
          change: abd10y?.change ?? "",
          up: abd10y?.up ?? null,
          href: "/kategori/global",
        },
      ],
    },
    {
      title: "Emtia, Petrol & Kripto",
      icon: Wheat,
      items: [
        {
          label: "Brent Petrol",
          sublabel: "Tanker & Varil Spot",
          value: brent?.value ?? NO_DATA,
          change: brent?.change ?? "",
          up: brent?.up ?? null,
          href: "/tarim-emtia?tab=petrolTanker",
        },
        {
          label: "Ons Altın",
          sublabel: "XAU/USD Spot",
          value: altin?.value ?? NO_DATA,
          change: altin?.change ?? "",
          up: altin?.up ?? null,
          href: "/kategori/global",
        },
        {
          label: "TÜRİB Hububat",
          sublabel: "TRBHUB Endeksi",
          value: trbHub?.valueStr ?? NO_DATA,
          change: trbHub?.changeStr ?? "",
          up: trbHub ? (trbHub.changePct ?? 0) >= 0 : null,
          href: "/tarim-emtia",
        },
        {
          label: "Bitcoin",
          sublabel: "BTC/USD Kripto",
          value: btc?.value ?? NO_DATA,
          change: btc?.change ?? "",
          up: btc?.up ?? null,
          href: "/kategori/kripto",
        },
      ],
    },
  ];

  return (
    <div className="w-full my-8">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-zinc-600" aria-hidden="true" />
          <h3 className="text-xs uppercase font-bold tracking-[0.15em] text-zinc-400">
            Piyasa Matrisi & Terminal Verisi
          </h3>
        </div>
        <span className="text-xs text-zinc-400 font-mono">
          {asOf ? `Veri tarihi: ${asOf}` : "Veri tarihi: yok"} · BIST & TÜRİB & Global
        </span>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {sections.map((sec, idx) => {
          const Icon = sec.icon;
          return (
            <div
              key={idx}
              className="rounded-xl border border-zinc-800/90 bg-zinc-950/60 p-4 transition-all hover:border-zinc-700/80"
              style={{
                boxShadow: "inset 0 1px 0 rgba(255,255,255,0.03)",
              }}
            >
              <div className="flex items-center justify-between pb-3 mb-3 border-b border-zinc-800/80">
                <div className="flex items-center gap-2">
                  <Icon className="w-3.5 h-3.5 text-cyan-400" />
                  <span className="text-xs font-semibold text-zinc-300">
                    {sec.title}
                  </span>
                </div>
              </div>

              <div className="space-y-2.5">
                {sec.items.map((it, itemIdx) => {
                  const content = (
                    <div className="flex items-center justify-between p-2 rounded-lg bg-zinc-900/40 hover:bg-zinc-900/80 border border-transparent hover:border-zinc-800 transition-all">
                      <div>
                        <p className="text-xs font-semibold text-white tracking-tight">
                          {it.label}
                        </p>
                        <p className="text-xs text-zinc-400 font-mono">
                          {it.sublabel}
                        </p>
                      </div>
                      <div className="text-right">
                        <p className="text-xs font-mono font-bold text-zinc-100">
                          {it.value}
                        </p>
                        {it.up !== null && it.change && (
                          <p
                            className={`text-xs font-mono font-semibold flex items-center justify-end gap-0.5 ${
                              it.up ? "text-emerald-400" : "text-rose-400"
                            }`}
                          >
                            {it.up ? (
                              <TrendingUp className="w-2.5 h-2.5 inline" />
                            ) : (
                              <TrendingDown className="w-2.5 h-2.5 inline" />
                            )}
                            {it.change}
                          </p>
                        )}
                      </div>
                    </div>
                  );

                  return it.href ? (
                    <Link key={itemIdx} href={it.href} className="block group">
                      {content}
                    </Link>
                  ) : (
                    <div key={itemIdx}>{content}</div>
                  );
                })}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
