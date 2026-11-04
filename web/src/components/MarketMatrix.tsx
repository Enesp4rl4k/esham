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
  up: boolean;
  href?: string;
};

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
  const btc = getTicker("BITCOIN") || { value: "$76.450", change: "-2,15%", up: false };

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
          value: xu100?.value || "10.961,67",
          change: xu100?.change || "+1,88%",
          up: xu100?.up ?? true,
          href: "/kategori/bist",
        },
        {
          label: "S&P 500",
          sublabel: "ABD Geniş Piyasa",
          value: sp500?.value || "7.541,40",
          change: sp500?.change || "-0,51%",
          up: sp500?.up ?? false,
          href: "/kategori/global",
        },
        {
          label: "NASDAQ",
          sublabel: "Teknoloji Endeksi",
          value: nasdaq?.value || "25.164,32",
          change: nasdaq?.change || "-1,07%",
          up: nasdaq?.up ?? false,
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
          value: usdtry?.value || "₺49,99",
          change: usdtry?.change || "+0,11%",
          up: usdtry?.up ?? true,
          href: "/kategori/global",
        },
        {
          label: "EUR / USD",
          sublabel: "Parite",
          value: eurusd?.value || "1,12",
          change: eurusd?.change || "+0,21%",
          up: eurusd?.up ?? true,
          href: "/kategori/global",
        },
        {
          label: "ABD 10Y Tahvil",
          sublabel: "Gösterge Faiz",
          value: abd10y?.value || "4,89%",
          change: abd10y?.change || "-0,71%",
          up: abd10y?.up ?? false,
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
          value: brent?.value || "$74,80",
          change: brent?.change || "+0,45%",
          up: brent?.up ?? true,
          href: "/tarim-emtia?tab=petrolTanker",
        },
        {
          label: "Ons Altın",
          sublabel: "XAU/USD Spot",
          value: altin?.value || "$2.780",
          change: altin?.change || "+0,45%",
          up: altin?.up ?? true,
          href: "/kategori/global",
        },
        {
          label: "TÜRİB Hububat",
          sublabel: "TRBHUB Endeksi",
          value: trbHub?.valueStr || "7.910,25",
          change: trbHub?.changeStr || "+2,12%",
          up: true,
          href: "/tarim-emtia",
        },
        {
          label: "Bitcoin",
          sublabel: "BTC/USD Kripto",
          value: btc?.value || "$76.450",
          change: btc?.change || "-2,15%",
          up: btc?.up ?? false,
          href: "/kategori/kripto",
        },
      ],
    },
  ];

  return (
    <div className="w-full my-8">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
          <h3 className="text-xs uppercase font-bold tracking-[0.15em] text-zinc-400">
            Canlı Piyasa Matrisi & Terminal Verisi
          </h3>
        </div>
        <span className="text-[11px] text-zinc-500 font-mono">
          Otomatik Senkronize · BIST & TÜRİB & Global
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
                        <p className="text-[10px] text-zinc-500 font-mono">
                          {it.sublabel}
                        </p>
                      </div>
                      <div className="text-right">
                        <p className="text-xs font-mono font-bold text-zinc-100">
                          {it.value}
                        </p>
                        <p
                          className={`text-[10px] font-mono font-semibold flex items-center justify-end gap-0.5 ${
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
