"""KAP (Kamuyu Aydınlatma Platformu) bildirim kaynağı.

KAP 2026 itibarıyla Next.js tabanlı bir SPA'ye geçmiş; eski `memberDisclosureQuery`
uç noktası artık YOK (WAF tanınmayan API yollarını sessizce yutuyor — bu yüzden
timeout alıyorduk). Gerçek uç noktalar, headless tarayıcı (Playwright) ile ağ
trafiği izlenerek bulundu ve doğrulandı:

    POST https://www.kap.org.tr/tr/api/disclosure/members/byCriteria   (bildirim listesi)
    GET  https://www.kap.org.tr/tr/Bildirim/{disclosureIndex}          (detay sayfası)
    GET  https://www.kap.org.tr/tr/api/BildirimPdf/{disclosureIndex}   (KAP'ın kendi
         bildirim KAPAĞI — birkaç yüz karakter, gerçek belge İÇERİĞİ DEĞİL)
    GET  https://www.kap.org.tr/tr/api/file/download/{hash}            (GERÇEK ek dosya
         — izahname/fiyat tespit raporu gibi çok sayfalı belgeler burada; hash SADECE
         detay sayfasının HTML'sinde bulunur, arama sonucunda yoktur)

Bağlantı/timeout/parse hatasında örnek veriyle zarifçe geri dönülür (KAP bazı
ağlardan yavaş/erişilemez olabilir; ayrıca site tekrar değişebilir).
"""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta

import requests

from ..config import default_headers, get_logger, settings
from ..kap_http import kap_get, kap_post
from ..turkish import repair_lost_apostrophes, tr_fold
from . import Disclosure

log = get_logger(__name__)

BASE_URL = "https://www.kap.org.tr"
QUERY_URL = f"{BASE_URL}/tr/api/disclosure/members/byCriteria"
# KAP yavaş yanıt verebildiği için genel timeout'tan daha cömert davranırız.
KAP_TIMEOUT = max(settings.http_timeout, 30)

IPO_KEYWORDS = ("halka arz", "fiyat tespit", "izahname")
INSIDER_KEYWORDS = ("pay alım satım", "geri alım", "içsel bilgi")

_PUBLISH_DATE_FMT = "%d.%m.%Y %H:%M:%S"  # KAP: "05.07.2026 18:21:10"
_ATTACHMENT_RE = re.compile(r"/tr/api/file/download/[a-f0-9]+")

# Bir aracı kurumun başka bir şirket adına yayınladığı bildirimlerin `summary`
# alanı "Şirket Adı A.Ş. Fiyat Tespit Raporu" gibi kalıplarla biter — gerçek
# şirket adını çıkarmak için bu ekleri kırparız.
_DISCLOSURE_SUFFIX_RE = re.compile(
    r"\s+(fiyat tespit raporu.*|fiyat tespit raporu\.?|i̇zahname.*|izahname.*|"
    r"paylarının halka arzına.*|halka arzına iliş[kc]in.*)\s*$",
    re.IGNORECASE,
)


def pick_ticker(codes: str) -> str:
    """KAP ``stockCodes`` listesinden işlem gören kodu seçer.

    KAP, çok pay gruplu şirketlerde tüm kodları verir (İş Bankası: "ISATR, ISBTR, ISCTR, ...").
    Eskiden ilki alınıyordu → ISATR (kurucu pay, fiyatı ~4,95 milyon TL) rapor/kartlara yansıyordu.
    Tek kod varsa o kod; birden çok kod varsa evrende (universe) olan kod. Evren dışı çok pay gruplu
    şirkette hangi kodun işlem gördüğü bilinemediği için TAHMİN EDİLMEZ: "" döner ve kod gösterilmez.
    """
    items = [c.strip().upper() for c in (codes or "").split(",") if c.strip()]
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    try:
        from ..universe import load_universe

        known = {str(u["ticker"]) for u in load_universe()}
    except Exception:  # noqa: BLE001
        known = set()
    matches = [c for c in items if c in known]
    return matches[0] if len(matches) == 1 else ""


def _strip_disclosure_suffix(text: str) -> str:
    return _DISCLOSURE_SUFFIX_RE.sub("", text).strip()


def _query_payload(days: int = 1) -> dict:
    today = date.today()
    return {
        "fromDate": (today - timedelta(days=days)).isoformat(),
        "toDate": today.isoformat(),
        "memberType": "IGS",
        "mkkMemberOidList": [],
        "inactiveMkkMemberOidList": [],
        "disclosureClass": "",
        "subjectList": [],
        "isLate": "",
        "mainSector": "",
        "sector": "",
        "subSector": "",
        "marketOid": "",
        "index": "",
        "bdkReview": "",
        "bdkMemberOidList": [],
        "year": "",
        "term": "",
        "ruleType": "",
        "period": "",
        "fromSrc": False,
        "srcCategory": "",
        "disclosureIndexList": [],
    }


class KapSource:
    def __init__(self) -> None:
        self.headers = {
            **default_headers(),
            "Content-Type": "application/json",
            "Referer": f"{BASE_URL}/tr/bildirim-sorgu",
        }

    def latest_disclosures(self, days: int = 1) -> list[Disclosure]:
        try:
            resp = kap_post(
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
            log.warning("KAP yanıtı boş/ayrıştırılamadı; bildirim yok (örnek veri üretilmiyor).")
        except (requests.RequestException, ValueError) as exc:
            log.warning("KAP verisi alınamadı (%s); bildirim yok (örnek veri üretilmiyor).", exc)
        return self._sample()

    def resolve_attachment_url(self, disclosure_index: str) -> str | None:
        """Detay sayfasını çekip GERÇEK ek dosya (izahname/fiyat tespit raporu vb.)
        linkini bulur. `/tr/api/BildirimPdf/{index}` sadece KAP'ın kendi bildirim
        kapağını verir (birkaç yüz karakter); asıl çok sayfalı belge ayrı bir ek
        dosyadır ve hash'i sadece bu detay sayfasının HTML'sinde bulunur.
        """
        if not disclosure_index:
            return None
        try:
            resp = kap_get(
                f"{BASE_URL}/tr/Bildirim/{disclosure_index}",
                headers=default_headers(),
                timeout=KAP_TIMEOUT,
            )
            resp.raise_for_status()
            match = _ATTACHMENT_RE.search(resp.text)
            if match:
                return f"{BASE_URL}{match.group(0)}"
            log.info("Bildirim %s için ek dosya linki bulunamadı.", disclosure_index)
        except (requests.RequestException, ValueError) as exc:
            log.warning("KAP detay çekme hatası (%s): %s", disclosure_index, exc)
            return None

    def get_detail_text(self, disclosure_index: str) -> str:
        """Bildirimin detay sayfasından tam metnini çeker.
        (Örn: Kredi notu güncellemelerinde notun ne olduğu sadece bu metindedir)."""
        if not disclosure_index:
            return ""
        try:
            resp = kap_get(
                f"{BASE_URL}/tr/Bildirim/{disclosure_index}",
                headers=default_headers(),
                timeout=KAP_TIMEOUT,
            )
            resp.raise_for_status()
            
            # HTML'den düz metni basitçe ayıklayalım
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(resp.text, 'html.parser')
            text = soup.get_text(separator=" ", strip=True)
            return text
        except Exception as exc:
            log.warning("Detay metni çekilemedi (index=%s): %s", disclosure_index, exc)
            return ""

    def ipo_disclosures(self, days: int = 3) -> list[Disclosure]:
        return [
            d
            for d in self.latest_disclosures(days)
            if any(
                k in tr_fold(d.disclosure_type) or k in tr_fold(d.title)
                for k in map(tr_fold, IPO_KEYWORDS)
            )
        ]

    # ---- ayrıştırma ------------------------------------------------------------

    @staticmethod
    def _as_rows(data: object) -> list[dict]:
        """Yanıt liste ya da {'disclosures'/'result': [...]} olabilir (dayanıklılık)."""
        if isinstance(data, list):
            return [r for r in data if isinstance(r, dict)]
        if isinstance(data, dict):
            for key in ("disclosures", "result", "data", "content"):
                val = data.get(key)
                if isinstance(val, list):
                    return [r for r in val if isinstance(r, dict)]
        return []

    def _to_disclosure(self, row: dict) -> Disclosure:
        # KAP verisindeki kayıp kesme işareti ("Bulgaristan?da") kaynağında onarılır; bkz. turkish.py.
        kap_title = repair_lost_apostrophes(str(row.get("kapTitle") or "").strip())
        subject = repair_lost_apostrophes(str(row.get("subject") or "").strip())
        summary = repair_lost_apostrophes(str(row.get("summary") or "").strip())
        index = row.get("disclosureIndex")
        stock_codes = str(row.get("stockCodes") or "").strip()
        related_stocks = str(row.get("relatedStocks") or "").strip()

        content = summary or subject or "Bildirim"

        # `relatedStocks` doluysa bildirim BAŞKA bir şirket adına yayınlanmıştır
        # (ör. bir aracı kurumun halka arz ettiği şirket için hazırladığı fiyat
        # tespit raporu/izahname). Bu durumda `kapTitle` yayıncı aracı kurumdur,
        # gerçek ihraççı DEĞİLDİR — ticker'ı relatedStocks'tan, şirket adını da
        # içerikten (aracı kurum adı değil) almalıyız.
        if related_stocks:
            ticker = pick_ticker(related_stocks)
            company = _strip_disclosure_suffix(content) or kap_title
        else:
            ticker = pick_ticker(stock_codes)
            company = kap_title

        title = f"{company}: {content}" if company and company not in content else content

        publish = self._parse_date(row.get("publishDate"))
        attachment_count = row.get("attachmentCount") or 0
        pdf_link = f"{BASE_URL}/tr/api/BildirimPdf/{index}" if index and attachment_count else ""

        low = tr_fold(f"{subject} {summary}")
        is_insider = any(tr_fold(k) in low for k in INSIDER_KEYWORDS)

        return Disclosure(
            title=title,
            company=company or ticker or "Bilinmiyor",
            date=publish,
            disclosure_type=subject or "Özel Durum Açıklaması",
            pdf_link=pdf_link,
            is_insider=is_insider,
            raw_text=content,
            ticker=ticker,
            disclosure_index=str(index) if index else "",
        )

    @staticmethod
    def _parse_date(value: object) -> str:
        """KAP tarihi 'DD.MM.YYYY HH:MM:SS' -> 'YYYY-MM-DD'."""
        if isinstance(value, str) and value.strip():
            try:
                return datetime.strptime(value.strip(), _PUBLISH_DATE_FMT).date().isoformat()
            except ValueError:
                pass
        return date.today().isoformat()

    # ---- fallback --------------------------------------------------------------

    def _sample(self) -> list[Disclosure]:
        # Hata durumunda sahte haber yayınlamamak için boş liste dönüyoruz.
        return []
