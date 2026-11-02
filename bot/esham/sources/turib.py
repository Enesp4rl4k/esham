"""TÜRİB (Türkiye Ürün İhtisas Borsası) ELÜS veri kaynağı.

Elektronik Ürün Senedi (ELÜS) tarımsal emtia piyasası:
  - Endeks serileri: TRBHUB (Hububat), TRBBGD (Buğday), TRBMSR (Mısır), TRBARP (Arpa)
    Uç: /wp-content/turib-api/getendeksmenudata.php?Code={kod} (JSON, UTF-8-SIG)
  - Ürün fiyat serileri: BUĞDAY EKMEKLİK, BUĞDAY MAKARNALIK, MISIR, ARPA vb.
    Uç: /tarihsel-veri/?ProductGroup={urun} (chartData JSON)
  - Günlük bülten: Senet (ISIN), LİDAŞ, İl/İlçe kırılımlı işlemler
    Uç: /gunluk-bulten-2/ (POST getbulletin_date=YYYY-MM-DD&submit=Getir)
  - Lisanslı depolar: /lisansli-depo-isletmesi-isin-kodlari/

Fiyatlar TL/kg, miktarlar kg/ton cinsindendir.
"""
from __future__ import annotations

import json
import re
import urllib.parse
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import requests

from ..config import default_headers, get_logger, settings
from ..formatting import tr_number as _tr_number
from ..formatting import tr_money as _tr_money
from ..http import retry_get

log = get_logger(__name__)

TURIB_BASE = "https://www.turib.com.tr"

ENDEKS_KODLARI = {
    "TRBHUB": "TÜRİB Hububat Endeksi",
    "TRBBGD": "TÜRİB Buğday Endeksi",
    "TRBBGDEKM": "TÜRİB Ekmeklik Buğday Endeksi",
    "TRBBGDMAK": "TÜRİB Makarnalık Buğday Endeksi",
    "TRBARP": "TÜRİB Arpa Endeksi",
    "TRBMSR": "TÜRİB Mısır Endeksi",
    "TRBMSR1SN": "TÜRİB Mısır 1. Sınıf Endeksi",
    "TRBMSR2SN": "TÜRİB Mısır 2. Sınıf Endeksi",
}

VARSAYILAN_URUNLER = [
    "BUĞDAY EKMEKLİK",
    "BUĞDAY MAKARNALIK",
    "MISIR",
    "ARPA",
]


@dataclass
class TuribIndexValue:
    code: str
    name: str
    price: float
    change_pct: float
    high: float
    low: float
    volume: float
    date: str


@dataclass
class TuribProductPrice:
    product: str
    price_tl_kg: float          # Son kapanış veya ağırlıklı ortalama (TL/kg)
    avg_price_tl_kg: float      # Ağırlıklı ortalama (TL/kg)
    change_pct: float           # Günlük değişim %
    volume_kg: float            # İşlem hacmi (kg)
    volume_tl: float            # İşlem hacmi (TL)
    high: float
    low: float
    date: str


@dataclass
class TuribSnapshot:
    """TÜRİB ELÜS piyasasının sabah/günlük durum özeti."""
    date: str
    indices: list[TuribIndexValue] = field(default_factory=list)
    products: list[TuribProductPrice] = field(default_factory=list)
    hububat_index: TuribIndexValue | None = None
    total_volume_tl: float = 0.0
    total_volume_tons: float = 0.0
    summary_text: str = ""


class TuribSource:
    """TÜRİB verilerini çeken, parse eden ve hata durumunda toleranslı dönen motor."""

    def __init__(self) -> None:
        self.headers = default_headers()
        self.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
            "Referer": f"{TURIB_BASE}/",
        })

    def fetch_index_series(self, code: str = "TRBHUB") -> list[dict[str, Any]]:
        """Endeks tarihsel serisini döner.
        
        Dönen format: [timestamp, open, high, low, close, avg, volume]
        """
        url = f"{TURIB_BASE}/wp-content/turib-api/getendeksmenudata.php?Code={code}"
        try:
            resp = retry_get(url, headers=self.headers, timeout=settings.http_timeout)
            resp.raise_for_status()
            text = resp.content.decode("utf-8-sig", errors="ignore")
            raw_data = json.loads(text)
            if not isinstance(raw_data, list):
                return []
            
            candles = []
            for item in raw_data:
                if len(item) >= 7:
                    dt = datetime.fromtimestamp(item[0] / 1000.0)
                    candles.append({
                        "date": dt.strftime("%Y-%m-%d"),
                        "open": float(item[1]),
                        "high": float(item[2]),
                        "low": float(item[3]),
                        "close": float(item[4]),
                        "avg": float(item[5]),
                        "volume": float(item[6]),
                    })
            return candles
        except Exception as exc:
            log.warning("TÜRİB endeks (%s) serisi çekilemedi: %s", code, exc)
            return []

    def fetch_latest_index(self, code: str = "TRBHUB") -> TuribIndexValue | None:
        """Belirtilen endeksin son günkü değerini ve değişimini hesaplar."""
        candles = self.fetch_index_series(code)
        if not candles:
            return None

        latest = candles[-1]
        prev = candles[-2] if len(candles) >= 2 else latest
        change_pct = 0.0
        if prev["close"] > 0:
            change_pct = round(((latest["close"] - prev["close"]) / prev["close"]) * 100, 2)

        name = ENDEKS_KODLARI.get(code, code)
        return TuribIndexValue(
            code=code,
            name=name,
            price=round(latest["close"], 2),
            change_pct=change_pct,
            high=round(latest["high"], 2),
            low=round(latest["low"], 2),
            volume=round(latest["volume"], 2),
            date=latest["date"],
        )

    def fetch_product_series(self, product_group: str) -> list[dict[str, Any]]:
        """Ürün grubu tarihsel serisini çeker. (BUĞDAY EKMEKLİK, MISIR vb.)"""
        encoded = urllib.parse.quote(product_group)
        url = f"{TURIB_BASE}/tarihsel-veri/?ProductGroup={encoded}"
        try:
            resp = retry_get(url, headers=self.headers, timeout=settings.http_timeout)
            resp.raise_for_status()
            html = resp.content.decode("utf-8-sig", errors="ignore")
            match = re.search(r"const chartData = (\[[\s\S]*?\]);", html)
            if not match:
                log.warning("TÜRİB %s için chartData bulunamadı.", product_group)
                return []
            raw_data = json.loads(match.group(1))
            candles = []
            for item in raw_data:
                if len(item) >= 7:
                    dt = datetime.fromtimestamp(item[0] / 1000.0)
                    candles.append({
                        "date": dt.strftime("%Y-%m-%d"),
                        "open": float(item[1]),
                        "high": float(item[2]),
                        "low": float(item[3]),
                        "close": float(item[4]),
                        "avg": float(item[5]),
                        "volume_kg": float(item[6]),
                    })
            return candles
        except Exception as exc:
            log.warning("TÜRİB ürün (%s) serisi çekilemedi: %s", product_group, exc)
            return []

    def fetch_latest_product_price(self, product_group: str) -> TuribProductPrice | None:
        """Bir ürün grubunun en son işlem fiyatını, ağırlıklı ortalamasını ve hacmini hesaplar."""
        candles = self.fetch_product_series(product_group)
        if not candles:
            return None

        latest = candles[-1]
        prev = candles[-2] if len(candles) >= 2 else latest
        change_pct = 0.0
        # Ağırlıklı ortalama varsa onun üzerinden, yoksa kapanış üzerinden değişim
        ref_curr = latest["avg"] if latest["avg"] > 0 else latest["close"]
        ref_prev = prev["avg"] if prev["avg"] > 0 else prev["close"]
        if ref_prev > 0:
            change_pct = round(((ref_curr - ref_prev) / ref_prev) * 100, 2)

        vol_kg = latest["volume_kg"]
        vol_tl = vol_kg * ref_curr

        return TuribProductPrice(
            product=product_group,
            price_tl_kg=round(latest["close"], 2),
            avg_price_tl_kg=round(ref_curr, 2),
            change_pct=change_pct,
            volume_kg=round(vol_kg, 1),
            volume_tl=round(vol_tl, 2),
            high=round(latest["high"], 2),
            low=round(latest["low"], 2),
            date=latest["date"],
        )

    def fetch_bulletin_table(self, date_str: str | None = None) -> list[dict[str, Any]]:
        """Günlük bülteni çeker (POST /gunluk-bulten-2/).
        
        date_str YYYY-AA-GG formatında olmalıdır. None verilirse bugünün veya son iş gününün verisini çeker.
        """
        if not date_str:
            date_str = datetime.now().strftime("%Y-%m-%d")

        url = f"{TURIB_BASE}/gunluk-bulten-2/"
        data = {"getbulletin_date": date_str, "submit": "Getir"}
        try:
            resp = requests.post(url, data=data, headers=self.headers, timeout=settings.http_timeout)
            resp.raise_for_status()
            html = resp.content.decode("utf-8-sig", errors="ignore")
            return self._parse_bulletin_html(html, date_str)
        except Exception as exc:
            log.warning("TÜRİB günlük bülten (%s) alınamadı: %s", date_str, exc)
            return []

    def _parse_bulletin_html(self, html: str, date_str: str) -> list[dict[str, Any]]:
        """Bülten HTML tablosunu ayrıştırır."""
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")
        tables = soup.find_all("table")
        trades = []
        for table in tables:
            rows = table.find_all("tr")
            if not rows:
                continue
            headers = [th.get_text(strip=True).lower().replace(" ", "") for th in rows[0].find_all(["th", "td"])]
            # İşlem tablosu mu kontrol et (içinde isin veya miktar barındırır)
            if any("isin" in h for h in headers) or any("miktar" in h for h in headers):
                for row in rows[1:]:
                    cols = [td.get_text(strip=True) for td in row.find_all("td")]
                    if len(cols) >= 6:
                        trades.append({
                            "date": date_str,
                            "raw_cols": cols,
                        })
        return trades

    def snapshot(self) -> TuribSnapshot:
        """Sabah raporu veya bülten için komple TÜRİB ELÜS piyasa snapshot'ı üretir (paralel)."""
        from concurrent.futures import ThreadPoolExecutor, as_completed

        today_str = datetime.now().strftime("%Y-%m-%d")
        indices: list[TuribIndexValue] = []
        products: list[TuribProductPrice] = []

        main_indices = ["TRBHUB", "TRBBGD", "TRBMSR", "TRBARP"]

        with ThreadPoolExecutor(max_workers=8) as pool:
            future_indices = {pool.submit(self.fetch_latest_index, code): code for code in main_indices}
            future_products = {pool.submit(self.fetch_latest_product_price, prod): prod for prod in VARSAYILAN_URUNLER}

            for f in as_completed(future_indices):
                res = f.result()
                if res:
                    indices.append(res)

            for f in as_completed(future_products):
                res = f.result()
                if res:
                    products.append(res)

        # Sıralama
        indices.sort(key=lambda x: main_indices.index(x.code) if x.code in main_indices else 99)
        products.sort(key=lambda x: VARSAYILAN_URUNLER.index(x.product) if x.product in VARSAYILAN_URUNLER else 99)

        hububat = next((i for i in indices if i.code == "TRBHUB"), None)

        # Toplam hacim hesapla
        total_tl = sum(p.volume_tl for p in products)
        total_kg = sum(p.volume_kg for p in products)
        total_tons = total_kg / 1000.0

        # Özet metin oluştur
        lines = []
        if hububat:
            sign = "+" if hububat.change_pct >= 0 else ""
            lines.append(f"TÜRİB Hububat Endeksi (TRBHUB): {_tr_number(hububat.price)} ({sign}{_tr_number(hububat.change_pct)}%)")

        prod_summaries = []
        for p in products:
            sign = "+" if p.change_pct >= 0 else ""
            prod_summaries.append(f"{p.product}: {_tr_number(p.avg_price_tl_kg)} TL/kg ({sign}{_tr_number(p.change_pct)}%)")
        if prod_summaries:
            lines.append(" | ".join(prod_summaries))

        if total_tons > 0:
            lines.append(f"İşlem Hacmi: {_tr_number(total_tons, 1)} Ton ({_tr_money(total_tl)})")

        summary_text = "\n".join(lines)

        return TuribSnapshot(
            date=today_str,
            indices=indices,
            products=products,
            hububat_index=hububat,
            total_volume_tl=total_tl,
            total_volume_tons=total_tons,
            summary_text=summary_text,
        )
