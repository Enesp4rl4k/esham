import math
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import squarify

from ..config import default_headers, get_logger, settings
from ..http import retry_get

matplotlib.use("Agg")  # Headless mode
log = get_logger(__name__)

# BIST30 Bileşenlerinden en popüler 20 hisse
BIST30_SYMBOLS = [
    "THYAO.IS", "TUPRS.IS", "KCHOL.IS", "AKBNK.IS", "YKBNK.IS",
    "ISCTR.IS", "GARAN.IS", "EREGL.IS", "ASELS.IS", "BIMAS.IS",
    "SAHOL.IS", "SISE.IS", "FROTO.IS", "TOASO.IS", "TCELL.IS",
    "ENKAI.IS", "PGSUS.IS", "KRDMD.IS", "PETKM.IS", "TTKOM.IS",
]

from concurrent.futures import ThreadPoolExecutor, as_completed

def _fetch_one(symbol: str) -> dict | None:
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
    try:
        resp = retry_get(url, headers=default_headers(), timeout=settings.http_timeout)
        resp.raise_for_status()
        meta = resp.json()["chart"]["result"][0]["meta"]
        price = meta.get("regularMarketPrice")
        prev = meta.get("chartPreviousClose") or meta.get("previousClose")
        vol = meta.get("regularMarketVolume", 0)
        if price is None or not vol:
            return None
        change_pct = ((price - prev) / prev * 100) if prev else 0.0
        return {
            "symbol": symbol.replace(".IS", ""),
            "price": price,
            "change_pct": change_pct,
            "volume": vol
        }
    except Exception:
        return None

def generate_heatmap(out_path: Path) -> bool:
    """BIST30 hacim/fiyat verisini çeker ve squarify ile Isı Haritası çizer."""
    try:
        results = []
        with ThreadPoolExecutor(max_workers=10) as pool:
            future_to_sym = {pool.submit(_fetch_one, sym): sym for sym in BIST30_SYMBOLS}
            for future in as_completed(future_to_sym):
                res = future.result()
                if res:
                    results.append(res)

        if not results:
            log.warning("Isı haritası için veri bulunamadı.")
            return False

        labels = []
        sizes = []
        colors = []

        for q in results:
            symbol = q["symbol"]
            price = q["price"]
            change_pct = q["change_pct"]
            volume = q["volume"]

            sizes.append(volume * price)  # İşlem Hacmi (TL bazlı ciro tahmini)
            
            # Etiket: Hisse \n %Değişim
            label = f"{symbol}\n{change_pct:+.2f}%"
            labels.append(label)

            # Renk skalası: Koyu kırmızı (-5%), Nötr (Gri), Koyu Yeşil (+5%)
            if change_pct >= 0:
                intensity = min(1.0, change_pct / 5.0)
                # Green gradient
                r, g, b = 0.1, 0.4 + (0.4 * intensity), 0.2
            else:
                intensity = min(1.0, abs(change_pct) / 5.0)
                # Red gradient
                r, g, b = 0.5 + (0.4 * intensity), 0.1, 0.1
                
            colors.append((r, g, b, 1.0))

        if not sizes:
            return False

        # Çizim
        fig, ax = plt.subplots(figsize=(12, 8), dpi=150)
        ax.axis('off')
        
        # Siyah arka plan
        fig.patch.set_facecolor('#18181b')
        
        squarify.plot(
            sizes=sizes,
            label=labels,
            color=colors,
            alpha=0.9,
            ax=ax,
            text_kwargs={'fontsize': 10, 'color': 'white', 'fontweight': 'bold'},
            pad=True,
        )

        plt.title("BIST30 Hacim Isı Haritası", fontsize=18, color='white', pad=20, fontweight='bold')
        plt.tight_layout()
        plt.savefig(out_path, facecolor='#18181b', bbox_inches='tight', edgecolor='none')
        plt.close()
        
        return True

    except Exception as exc:
        log.warning("Isı haritası üretilemedi: %s", exc)
        return False
