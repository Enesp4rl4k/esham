"""KAP'ı birincil, Yahoo'yu yedek finansal kaynak olarak seçer (saf fonksiyonlar, test edilebilir).

Kural: KAP belgesi şu koşulların hepsini sağlıyorsa KAP kullanılır:
  1. En az 4 çeyreklik dönem (TTM için) ve her ikisinde de güncel dönem Yahoo'dan eski değil
  2. Son 4 çeyrekte hasılat ve net kâr mevcut
  3. KAP/Yahoo TTM hasılat farkı ``MAX_REVENUE_DIFF_PCT`` içinde (aşarsa XBRL eşlemesinden şüphelenilir:
     ör. banka iştiraki olan holdinglerde hasılat satırı eksik kalabilir) → Yahoo'da kal, nedenini bayrakla.
Net kâr farkı BİLEREK ölçüt değildir: Yahoo'nun net kâr hataları (DOAS, PETKM) KAP'ı seçmemizin nedenidir.
"""
from __future__ import annotations

from typing import Any

from . import ratios as R

MAX_REVENUE_DIFF_PCT = 35.0


def revenue_diff_pct(kap_q: list[dict[str, Any]], yahoo_q: list[dict[str, Any]], yahoo_fx: float | None) -> float | None:
    """KAP / Yahoo TTM hasılat − 1 (%). Yahoo tabloları farklı para biriminde ise TL'ye çevrilir."""
    k = R.ttm(kap_q, "revenue")
    y = R.ttm(yahoo_q, "revenue")
    if not k or not y:
        return None
    y_try = y * (yahoo_fx or 1.0)
    if not y_try:
        return None
    return round((k / y_try - 1) * 100, 1)


def choose_source(
    kap_doc: dict[str, Any] | None,
    yahoo_q: list[dict[str, Any]],
    yahoo_fx: float | None,
) -> tuple[str, str | None]:
    """('KAP'|'Yahoo', neden). Neden yalnızca Yahoo'ya düşülürken (veya KAP seçilip uyarı gerekirken) dolu."""
    if not kap_doc:
        return "Yahoo", None  # KAP verisi üretilmemiş (finansal şirket vb.) — beklenen durum
    kq = kap_doc.get("quarterly") or []
    if len(kq) < 4:
        return "Yahoo", "kap_yetersiz_donem"
    last_kap = kq[-1]["date"]
    last_yahoo = yahoo_q[-1]["date"] if yahoo_q else ""
    if last_kap < last_yahoo:
        return "Yahoo", "kap_eski"
    if R.ttm(kq, "revenue") is None or R.ttm(kq, "net_income") is None:
        return "Yahoo", "kap_eksik_kalem"
    diff = revenue_diff_pct(kq, yahoo_q, yahoo_fx)
    if diff is not None and abs(diff) > MAX_REVENUE_DIFF_PCT:
        return "Yahoo", "kap_hasilat_farki_buyuk"
    return "KAP", None


def merge_statements(
    kap_doc: dict[str, Any],
    yahoo_q: list[dict[str, Any]],
    yahoo_a: list[dict[str, Any]],
    yahoo_currency: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """KAP seçildiğinde (çeyreklik, yıllık) tablolar. Yıllık KAP serisi kısa kalırsa ve para birimi aynıysa Yahoo yıllığı korunur."""
    kq, ka = kap_doc["quarterly"], kap_doc.get("annual") or []
    same_ccy = bool(yahoo_a) and yahoo_currency == kap_doc.get("currency")
    if len(ka) < 2 and same_ccy:
        return kq, yahoo_a
    return kq, ka
