"""KAP (Kamuyu Aydınlatma Platformu) bildirim kaynağı.

KAP'ın `memberDisclosureQuery` JSON uç noktasına POST atar. Yanıt bir bildirim
dizisidir; alan adları zaman zaman değiştiği için savunmacı biçimde ayrıştırılır.
Bağlantı/timeout/parse hatasında örnek veriyle zarifçe geri dönülür (KAP bazı
ağlardan yavaş/erişilemez olabilir).
"""
from __future__ import annotations

from datetime import date, timedelta

import requests

from ..config import default_headers, get_logger, settings
from . import Disclosure

log = get_logger(__name__)

BASE_URL = "https://www.kap.org.tr"
QUERY_URL = f"{BASE_URL}/tr/api/memberDisclosureQuery"
# KAP yavaş yanıt verebildiği için genel timeout'tan daha cömert davranırız.
KAP_TIMEOUT = max(settings.http_timeout, 30)

IPO_KEYWORDS = ("halka arz", "fiyat tespit", "izahname")
INSIDER_KEYWORDS = ("pay alım satım", "geri alım", "içsel bilgi")


def _query_payload(days: int = 1) -> dict:
    today = date.today()
    return {
        "fromDate": (today - timedelta(days=days)).isoformat(),
        "toDate": today.isoformat(),
        "year": "", "prd": "", "term": "", "ruleType": "", "bdkReview": "",
        "disclosureClass": "", "index": "", "market": "", "isLate": "",
        "subjectList": [], "mkkMemberOidList": [], "inactiveMkkMemberOidList": [],
        "bdkMemberOidList": [], "mainSector": "", "sector": "", "subSector": "",
        "memberType": "IGS", "fromSrc": "N", "srcCategory": "", "discIndex": [],
    }


class KapSource:
    def __init__(self) -> None:
        self.headers = {**default_headers(), "Content-Type": "application/json"}

    def latest_disclosures(self, days: int = 1) -> list[Disclosure]:
        try:
            resp = requests.post(
                QUERY_URL,
                json=_query_payload(days),
                headers=self.headers,
                timeout=KAP_TIMEOUT,
            )
            resp.raise_for_status()
            rows = self._as_rows(resp.json())
            disclosures = [self._to_disclosure(r) for r in rows]
            disclosures = [d for d in disclosures if d.title]
            if disclosures:
                log.info("KAP: %d bildirim alındı.", len(disclosures))
                return disclosures
            log.warning("KAP yanıtı boş/ayrıştırılamadı; örnek veri kullanılıyor.")
        except (requests.RequestException, ValueError) as exc:
            log.warning("KAP verisi alınamadı (%s); örnek veri kullanılıyor.", exc)
        return self._sample()

    def ipo_disclosures(self, days: int = 3) -> list[Disclosure]:
        return [
            d
            for d in self.latest_disclosures(days)
            if any(
                k in d.disclosure_type.lower() or k in d.title.lower() for k in IPO_KEYWORDS
            )
        ]

    # ---- ayrıştırma ------------------------------------------------------------

    @staticmethod
    def _as_rows(data: object) -> list[dict]:
        """Yanıt liste ya da {'disclosures'/'result': [...]} olabilir."""
        if isinstance(data, list):
            return [r for r in data if isinstance(r, dict)]
        if isinstance(data, dict):
            for key in ("disclosures", "result", "data", "basic"):
                val = data.get(key)
                if isinstance(val, list):
                    return [r for r in val if isinstance(r, dict)]
        return []

    def _to_disclosure(self, row: dict) -> Disclosure:
        def first(*keys: str) -> str:
            for k in keys:
                v = row.get(k)
                if v:
                    return str(v).strip()
            return ""

        title = first("title", "kapTitle", "subject", "disclosureType")
        company = first("stockCodes", "ticker", "companyName", "kapTitle")
        dtype = first("disclosureCategory", "disclosureClass", "ruleTypeTerm", "type", "subject")
        publish = first("publishDate", "date", "disclosureDate") or date.today().isoformat()
        index = first("disclosureIndex", "basicNotificationId", "id")
        summary = first("summary", "description")

        low = f"{title} {dtype} {summary}".lower()
        is_insider = any(k in low for k in INSIDER_KEYWORDS)
        pdf_link = f"{BASE_URL}/tr/Bildirim/{index}" if index else ""

        return Disclosure(
            title=title,
            company=company,
            date=publish[:10],
            disclosure_type=dtype or "Özel Durum Açıklaması",
            pdf_link=pdf_link,
            is_insider=is_insider,
            raw_text=summary or title,
        )

    # ---- fallback --------------------------------------------------------------

    def _sample(self) -> list[Disclosure]:
        today = date.today().isoformat()
        return [
            Disclosure(
                title="TechYazılım A.Ş. Fiyat Tespit Raporu",
                company="TCHYZ",
                date=today,
                disclosure_type="Halka Arz",
                pdf_link="/tr/Bildirim/Pdf/123456",
                raw_text="TechYazılım A.Ş. halka arz fiyat tespit raporunu yayımladı.",
            ),
            Disclosure(
                title="X Holding CEO'su pay alımı gerçekleştirdi",
                company="XHOLD",
                date=today,
                disclosure_type="Pay Alım Satım Bildirimi",
                is_insider=True,
                raw_text="X Holding CEO'su borsada 1 Milyon TL'lik hisse alımı yaptı.",
            ),
        ]
