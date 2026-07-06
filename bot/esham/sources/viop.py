"""VİOP (Vadeli İşlem ve Opsiyon Piyasası) veri kaynağı.

İki tür veri:
1. Piyasa kotasyonu — BIST30 endeksi (XU030) ve vadeli (XU030D) TradingView
   scanner API'sinden (canlı, sağlam).
2. Marketwide teminat agregatı — Takasbank'tan (teminatlı hesap sayısı, margin-call
   toplamı, gereken teminat). Takasbank doğrudan erişimi captcha/WAF ile kısıtlı
   olduğundan endpoint opsiyoneldir; yoksa gerçek yapıda örnek veri döner.

`margin_call_to_required_pct` marketwide stres sinyalidir: önceki güne göre yükselmesi
CCP'nin teminatı sıkılaştırdığını, brokerların margin-call çıkaracağını gösterir.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

import requests

from ..config import default_headers, get_logger, settings
from ..http import retry_get, retry_post
from ..formatting import tr_money, tr_number

log = get_logger(__name__)

TV_SCAN_URL = "https://scanner.tradingview.com/turkey/scan"


@dataclass
class ViopQuote:
    index_symbol: str
    index_price: str
    index_change: str
    futures_symbol: str = ""
    futures_price: str = ""
    futures_change: str = ""
    futures_volume: str = ""


@dataclass
class ViopMarginSnapshot:
    as_of: str
    margined_account_count: int
    margin_call_total_tl: float
    required_margin_total_tl: float
    margin_call_to_required_pct: float
    futures_oi_value_tl: float = 0.0
    futures_volume_tl: float = 0.0
    options_volume_tl: float = 0.0
    profit_loss_total_tl: float = 0.0
    is_sample: bool = False

    def margin_call_pretty(self) -> str:
        return tr_money(self.margin_call_total_tl)

    def required_pretty(self) -> str:
        return tr_money(self.required_margin_total_tl)


@dataclass
class MarginStress:
    level: str  # "Yükseliyor" | "Sabit" | "Geriliyor" | "Bilinmiyor"
    note: str


def _change_str(pct: float) -> str:
    return f"{'+' if pct >= 0 else ''}{tr_number(pct, 2)}%"


class ViopSource:
    def __init__(self) -> None:
        self.headers = default_headers()

    # ---- piyasa kotasyonu ------------------------------------------------------

    def market_quote(self) -> ViopQuote:
        try:
            resp = retry_post(
                TV_SCAN_URL,
                json={
                    "symbols": {"tickers": ["BIST:XU030", "BIST:XU030D"]},
                    "columns": ["name", "close", "change", "volume"],
                },
                headers=self.headers,
                timeout=settings.http_timeout,
            )
            resp.raise_for_status()
            quote = self._parse_quote(resp.json())
            if quote:
                return quote
            log.warning("VİOP kotasyonu ayrıştırılamadı; örnek veri kullanılıyor.")
        except (requests.RequestException, ValueError) as exc:
            log.warning("VİOP kotasyonu alınamadı (%s); örnek veri kullanılıyor.", exc)
        return self._sample_quote()

    def _parse_quote(self, payload: dict) -> ViopQuote | None:
        rows = {r["s"]: r["d"] for r in payload.get("data", []) if "s" in r and "d" in r}
        idx = rows.get("BIST:XU030")
        fut = rows.get("BIST:XU030D")
        if not idx:
            return None
        # d = [name, close, change, volume]
        q = ViopQuote(
            index_symbol="XU030",
            index_price=tr_number(float(idx[1])) if idx[1] is not None else "",
            index_change=_change_str(float(idx[2])) if idx[2] is not None else "",
        )
        if fut:
            q.futures_symbol = "XU030D"
            q.futures_price = tr_number(float(fut[1])) if fut[1] is not None else ""
            q.futures_change = _change_str(float(fut[2])) if fut[2] is not None else ""
            q.futures_volume = tr_money(float(fut[3])) if fut[3] else ""
        return q

    def _sample_quote(self) -> ViopQuote:
        return ViopQuote(
            index_symbol="XU030",
            index_price="16.740,68",
            index_change="-0,31%",
            futures_symbol="XU030D",
            futures_price="16.910,00",
            futures_change="-0,28%",
            futures_volume="113,5 Milyar TL",
        )

    # ---- marketwide teminat agregatı ------------------------------------------

    def margin_snapshot(self) -> ViopMarginSnapshot:
        url = settings.takasbank_viop_url
        if url:
            try:
                resp = retry_get(url, headers=self.headers, timeout=settings.http_timeout)
                resp.raise_for_status()
                snap = self._parse_margin(resp.json())
                if snap:
                    return snap
                log.warning("Takasbank yanıtı ayrıştırılamadı; örnek veri kullanılıyor.")
            except (requests.RequestException, ValueError) as exc:
                log.warning("Takasbank verisi alınamadı (%s); örnek veri kullanılıyor.", exc)
        else:
            log.info("Takasbank URL tanımlı değil; örnek VİOP teminat verisi kullanılıyor.")
        return self._sample_margin()

    def _parse_margin(self, payload: dict) -> ViopMarginSnapshot | None:
        snap = payload.get("snapshot", payload)
        if not isinstance(snap, dict) or "required_margin_total_tl" not in snap:
            return None

        def num(key: str) -> float:
            v = snap.get(key, 0)
            return float(v) if isinstance(v, (int, float)) else 0.0

        required = num("required_margin_total_tl")
        call = num("margin_call_total_tl")
        pct = snap.get("margin_call_to_required_pct")
        if not isinstance(pct, (int, float)):
            pct = (call / required * 100) if required else 0.0
        return ViopMarginSnapshot(
            as_of=str(payload.get("as_of", datetime.now(timezone.utc).isoformat())),
            margined_account_count=int(num("margined_account_count")),
            margin_call_total_tl=call,
            required_margin_total_tl=required,
            margin_call_to_required_pct=float(pct),
            futures_oi_value_tl=num("futures_oi_value_tl"),
            futures_volume_tl=num("futures_volume_tl"),
            options_volume_tl=num("options_volume_tl"),
            profit_loss_total_tl=num("profit_loss_total_tl"),
        )

    def _sample_margin(self) -> ViopMarginSnapshot:
        # Gerçek Takasbank yapısıyla, temsili değerler.
        return ViopMarginSnapshot(
            as_of=datetime.now(timezone.utc).isoformat(),
            margined_account_count=116_502,
            margin_call_total_tl=558_211_906.08,
            required_margin_total_tl=119_575_509_403.59,
            margin_call_to_required_pct=0.4668,
            futures_oi_value_tl=547_411_685_962.13,
            futures_volume_tl=113_486_759_846.02,
            options_volume_tl=4_620_441_562.0,
            profit_loss_total_tl=2_144_074_802.38,
            is_sample=True,
        )


def assess_margin_stress(
    today_pct: float, prior_pct: float | None = None, *, jump_threshold: float = 0.05
) -> MarginStress:
    """margin_call/required oranını önceki günle kıyaslayarak stres yönünü çıkarır.

    `jump_threshold`: oranın yüzde-puan bazında anlamlı değişim eşiği.
    """
    if prior_pct is None:
        return MarginStress("Bilinmiyor", "Karşılaştırma için önceki gün verisi yok.")
    delta = today_pct - prior_pct
    if delta >= jump_threshold:
        return MarginStress(
            "Yükseliyor",
            f"Margin-call/gereken teminat oranı {tr_number(prior_pct, 2)}% → "
            f"{tr_number(today_pct, 2)}%. CCP teminatı sıkılaştırıyor; margin-call dalgası olası.",
        )
    if delta <= -jump_threshold:
        return MarginStress(
            "Geriliyor",
            f"Oran {tr_number(prior_pct, 2)}% → {tr_number(today_pct, 2)}%. Teminat baskısı azalıyor.",
        )
    return MarginStress("Sabit", f"Oran ~{tr_number(today_pct, 2)}% seviyesinde yatay.")
