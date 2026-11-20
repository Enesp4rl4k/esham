"""KAP "Genel Bilgi Formu" → bağlı ortaklık / iştirak / iş ortaklığı pay oranları (NAV girdisi).

Kaynak: ``/tr/sirket-bilgileri/genel/<permalink>`` — "Bağlı Ortaklıklar, Finansal Duran Varlıklar ile
Finansal Yatırımlar" tablosu sayfada JSON (RSC akışı) olarak gömülü. Satır alanları:
``companyTitle``, ``ratioOfCapitalShareOfCompany`` ("39,32" = %), ``relationWithTheCompany``,
``monetaryUnit``. Şirketin permalink'i ``/tr/api/member/filter/<TICKER>`` ile bulunur.

SINIR (bilerek): tablo yalnızca şirketin DOĞRUDAN paylarını verir. Ara holdingler üzerinden gelen
dolaylı paylar (ör. KCHOL → Enerji Yatırımları → Tüpraş) bu veride yoktur; ara şirketlerin KAP
sayfaları ünvan aramasıyla güvenilir biçimde bulunamadığı için zincirleme okuma yapılmaz.
"""
from __future__ import annotations

import json
import re
import unicodedata
from typing import Any

from ..config import default_headers, get_logger
from ..http import retry_get

log = get_logger(__name__)
BASE_URL = "https://www.kap.org.tr"


def fold_title(s: str) -> str:
    """Ünvan eşleştirme anahtarı: Türkçe-duyarsız, küçük harf, A.Ş./Ltd gibi ekler ve noktalama atılır."""
    s = (s or "").replace("İ", "i").replace("I", "i").replace("ı", "i")
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    s = re.sub(r"\b(a s|a ş|as|anonim sirketi|ltd|sti|inc|b v|bv|tic|ticaret|san|sanayi|ve)\b", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def parse_pct(s: Any) -> float | None:
    """'39,32' → 39.32; '100' → 100.0; boş/geçersiz → None."""
    try:
        return float(str(s).strip().replace(".", "").replace(",", "."))
    except ValueError:
        return None


def decode_rsc(raw: bytes) -> str:
    text = raw.decode("utf-8")
    parts = re.findall(r'self\.__next_f\.push\(\[1,("(?:[^"\\]|\\.)*")\]\)', text)
    return "".join(json.loads(p) for p in parts) if parts else text


def extract_stakes(payload: str) -> list[dict[str, Any]]:
    """RSC metni → iştirak satırları. İç içe ``monetaryUnit`` nesnesi yüzünden dengeli parantezle okunur."""
    out: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for m in re.finditer(r'\{"companyTitle"\s*:\s*"', payload):
        depth, j = 0, m.start()
        while j < len(payload):
            ch = payload[j]
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    break
            j += 1
        try:
            row = json.loads(payload[m.start(): j + 1])
        except json.JSONDecodeError:
            continue
        pct = parse_pct(row.get("ratioOfCapitalShareOfCompany"))
        title = str(row.get("companyTitle") or "").strip()
        if not title or pct is None:
            continue
        key = (title, str(pct))
        if key in seen:  # sayfada aynı tablo iki kez render edilebilir
            continue
        seen.add(key)
        out.append({
            "title": title,
            "pct": pct,
            "relation": str(row.get("relationWithTheCompany") or "").strip(),
            "currency": (row.get("monetaryUnit") or {}).get("key") if isinstance(row.get("monetaryUnit"), dict) else None,
        })
    return out


def _tokens(title: str) -> frozenset[str]:
    """Ünvan jetonları, ilk 5 harfe kısaltılmış ('Makinaları'/'Makineleri' → 'makin')."""
    return frozenset(w[:5] for w in fold_title(title).split() if w)


def match_listed(stakes: list[dict[str, Any]], title_to_ticker: dict[str, str]) -> list[dict[str, Any]]:
    """Ünvanı ``title_to_ticker`` (katlanmış ünvan → ticker) ile eşleştirip ``ticker`` alanını doldurur.

    1) Tam (katlanmış) eşleşme. 2) Yoksa jeton kümesi eşleşmesi: iştirak ünvanının jetonları (≥ 2) KAP
    ünvanının jetonlarında bulunuyor ve TEK bir şirkette bulunuyorsa eşleşir (ör. "Türkiye Petrol
    Rafinerileri" ⊂ "Tüpraş-Türkiye Petrol Rafinerileri"). Birden çok aday varsa eşleştirilmez.
    """
    index = [(_tokens(t), tick) for t, tick in title_to_ticker.items()]
    res = []
    for s in stakes:
        t = title_to_ticker.get(fold_title(s["title"]))
        if t is None:
            toks = _tokens(s["title"])
            if len(toks) >= 2:
                cands = {tick for tk, tick in index if toks <= tk or tk <= toks and len(tk) >= 2}
                if len(cands) == 1:
                    t = next(iter(cands))
        res.append({**s, "ticker": t})
    return res


class KapHoldings:
    def __init__(self) -> None:
        self.headers = {**default_headers(), "Accept": "application/json"}

    def permalink(self, ticker: str, name_hint: str | None = None) -> str | None:
        """Üye araması kod alt dizesiyle eşleşir ("ALARK" → Alarko Carrier de döner): ``name_hint`` varsa
        ünvanı bu ada en çok benzeyen sonuç seçilir."""
        try:
            r = retry_get(f"{BASE_URL}/tr/api/member/filter/{ticker}", headers=self.headers, timeout=30)
            r.raise_for_status()
            rows = r.json()
        except Exception as exc:
            log.warning("KAP üye araması başarısız %s: %s", ticker, exc)
            return None
        if not isinstance(rows, list) or not rows:
            return None
        if name_hint and len(rows) > 1:
            want = _tokens(name_hint)
            rows = sorted(rows, key=lambda x: (len(want & _tokens(x.get("title", ""))), -len(_tokens(x.get("title", "")))), reverse=True)
        return rows[0]["permaLink"]

    def stakes(self, ticker: str, name_hint: str | None = None) -> list[dict[str, Any]] | None:
        link = self.permalink(ticker, name_hint)
        if not link:
            return None
        try:
            r = retry_get(f"{BASE_URL}/tr/sirket-bilgileri/genel/{link}", headers=default_headers(), timeout=60)
            r.raise_for_status()
            return extract_stakes(decode_rsc(r.content))
        except Exception as exc:
            log.warning("KAP Genel Bilgi alınamadı %s: %s", ticker, exc)
            return None
