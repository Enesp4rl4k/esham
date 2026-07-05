"""BIST endeks özeti kaynağı.

Yahoo Finance'in kırılgan HTML'i yerine dayanıklı JSON chart API'si kullanılır:
`query1.finance.yahoo.com/v8/finance/chart/XU100.IS`. Hata durumunda örnek veriyle
zarifçe geri dönülür.
"""
from __future__ import annotations

import requests
from datetime import datetime
import tempfile
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

from ..config import default_headers, get_logger, settings
from ..formatting import tr_money as _tr_volume
from ..formatting import tr_number as _tr_number
from . import MarketSummary

log = get_logger(__name__)

CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"


class BistSource:
    def __init__(self, symbol: str = "XU100.IS") -> None:
        self.symbol = symbol
        self.headers = default_headers()

    def market_summary(self) -> MarketSummary:
        try:
            resp = requests.get(
                CHART_URL.format(symbol=self.symbol),
                headers=self.headers,
                timeout=settings.http_timeout,
            )
            resp.raise_for_status()
            summary = self._parse(resp.json())
            if summary:
                return summary
            log.warning("BIST verisi ayrıştırılamadı; örnek veri kullanılıyor.")
        except (requests.RequestException, ValueError) as exc:
            log.warning("BIST verisi alınamadı (%s); örnek veri kullanılıyor.", exc)
        return self._sample()

    def _parse(self, payload: dict) -> MarketSummary | None:
        try:
            meta = payload["chart"]["result"][0]["meta"]
        except (KeyError, IndexError, TypeError):
            return None

        price = meta.get("regularMarketPrice")
        prev = meta.get("chartPreviousClose") or meta.get("previousClose")
        if price is None:
            return None

        change = ""
        if prev:
            pct = (price - prev) / prev * 100
            change = f"{'+' if pct >= 0 else ''}{_tr_number(pct, 2)}%"

        volume = meta.get("regularMarketVolume")
        index = meta.get("symbol", self.symbol).replace(".IS", "")
        return MarketSummary(
            index=index,
            price=_tr_number(float(price)),
            change=change,
            volume=_tr_volume(float(volume)) if volume else "",
        )

    def _sample(self) -> MarketSummary:
        return MarketSummary(
            index="XU100",
            price="10.450,23",
            change="+1,2%",
            volume="120 Milyar TL",
        )

    def generate_chart_image(self, range_str: str = "1d", interval: str = "5m") -> Path | None:
        """BIST 100 endeksinin gerçek verileriyle bir çizgi grafik oluşturur ve yolunu döner."""
        try:
            url = f"{CHART_URL.format(symbol=self.symbol)}?range={range_str}&interval={interval}"
            resp = requests.get(url, headers=self.headers, timeout=settings.http_timeout)
            resp.raise_for_status()
            payload = resp.json()

            result = payload["chart"]["result"][0]
            timestamps = result.get("timestamp", [])
            quotes = result["indicators"]["quote"][0]
            close_prices = quotes.get("close", [])

            # None değerleri filtrele
            valid_data = [(ts, close) for ts, close in zip(timestamps, close_prices) if close is not None]
            if not valid_data:
                log.warning("Grafik için geçerli veri bulunamadı.")
                return None

            ts_list, close_list = zip(*valid_data)
            dates = [datetime.fromtimestamp(ts) for ts in ts_list]

            # Grafik Çizimi (Midnight Blue Tema)
            plt.style.use("dark_background")
            fig, ax = plt.subplots(figsize=(10, 5), facecolor="#090e1a")
            ax.set_facecolor("#090e1a")

            # Fiyat Çizgisi
            ax.plot(dates, close_list, color="#38bdf8", linewidth=2.5, label="BIST 100")
            # Altını hafifçe doldur (Alan Grafiği)
            ax.fill_between(dates, close_list, min(close_list) * 0.999, color="#38bdf8", alpha=0.1)

            # Eksen formatlaması
            if range_str == "1d":
                ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
            else:
                ax.xaxis.set_major_formatter(mdates.DateFormatter("%d %b"))

            ax.tick_params(colors="#64748b", labelsize=10)
            ax.grid(True, color="#1e293b", linestyle="--", alpha=0.5)

            # Üst ve sağ çerçeveleri kaldır
            for spine in ["top", "right"]:
                ax.spines[spine].set_visible(False)
            ax.spines["left"].set_color("#1e293b")
            ax.spines["bottom"].set_color("#1e293b")

            # Başlık
            title_text = "BIST 100 Günlük Grafik" if range_str == "1d" else "BIST 100 5 Günlük Trend"
            ax.set_title(title_text, fontsize=14, color="#ffffff", fontweight="bold", pad=15)

            tmp = Path(tempfile.gettempdir()) / f"bist_chart_{range_str}.png"
            plt.savefig(tmp, bbox_inches="tight", dpi=150, facecolor="#090e1a")
            plt.close()
            return tmp
        except Exception as exc:
            log.warning("BIST grafik resmi oluşturulamadı: %s", exc)
            return None
