"""Halka arz izahname & fiyat tespit raporu analizörü.

Uzun KAP belgesini alır, ilgili bölümleri süzer, yapılandırılmış bir analiz (JSON)
üretir. Çıktı hem web raporunu (markdown) hem IPO PDF'ini (dict) besler.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ..config import get_logger, settings
from ..documents.sections import IPO_KEYWORDS, extract_relevant
from .client import LlmClient

log = get_logger(__name__)


@dataclass
class IpoAnalysis:
    company: str
    ticker: str
    price: str = ""
    discount_rate: str = ""
    offer_size: str = ""
    net_margin: str = ""  # Net kâr marjı — AI çıktısından parse edilir
    fund_usage: list[str] = field(default_factory=list)
    commitments: list[str] = field(default_factory=list)
    strengths: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    valuation: dict[str, str] = field(default_factory=dict)  # F/K, PD/DD, FD/FAVÖK
    verdict: str = ""
    confidence: str = "orta"  # düşük | orta | yüksek
    ai_generated: bool = True

    def discount_pct_float(self) -> float:
        """'%22,5', '%22.5', '22,5%', '22.5' gibi formatları float'a çevirir.
        Parse edilemezse 0.0 döner.
        """
        import re
        raw = self.discount_rate.strip()
        if not raw:
            return 0.0
        # Rakam+virgül/nokta kombinasyonunu bul
        m = re.search(r"(\d+[.,]\d+|\d+)", raw.replace(",", "."))
        if m:
            try:
                return float(m.group(1).replace(",", "."))
            except ValueError:
                pass
        return 0.0

    def fund_usage_summary(self, max_items: int = 3) -> str:
        """Fon kullanım kalemlerini tek satır özetine dönüştürür.
        Örn. ['Kapasite %50', 'AR-GE %30', 'Borç ödemesi %20'] → 'Kapasite %50 · AR-GE %30 · ...'
        """
        items = self.fund_usage[:max_items]
        if not items:
            return ""
        return " · ".join(items)

    def to_meta(self, disclosure_date: str = "") -> dict:
        """Web köprüsü için yapılandırılmış meta (takvim/istatistik sayfaları için).

        `web/src/lib/content-utils.ts` içindeki `IpoMeta` ile alan adları senkron
        tutulmalı. Boş değerler yazılmaz — eski/eksik alanlar JSON'da görünmez.
        """
        meta: dict = {
            "company": self.company,
            "ticker": self.ticker,
            "verdict": self.verdict,
            "confidence": self.confidence,
        }
        if disclosure_date:
            meta["disclosureDate"] = disclosure_date
        if self.price:
            meta["price"] = self.price
        if self.discount_rate:
            meta["discountRate"] = self.discount_rate
            pct = self.discount_pct_float()
            if pct:
                meta["discountPct"] = pct
        if self.offer_size:
            meta["offerSize"] = self.offer_size
        if self.net_margin:
            meta["netMargin"] = self.net_margin
        if self.valuation:
            meta["valuation"] = dict(self.valuation)
        if self.fund_usage:
            meta["fundUsage"] = list(self.fund_usage)
        if self.risks:
            meta["risks"] = list(self.risks)
        return meta

    def has_content(self) -> bool:
        """Belgeden en az bir alan ayıklandı mı? AI kapalı/başarısızken her şey boştur → yayın yapılmaz."""
        return self.ai_generated and any([
            self.price, self.discount_rate, self.offer_size, self.net_margin, self.fund_usage,
            self.commitments, self.strengths, self.risks, any(v for v in self.valuation.values()),
        ])

    def to_markdown(self) -> str:
        def bullets(items: list[str]) -> str:
            return "\n".join(f"- {i}" for i in items) if items else "- Belirtilmemiş"

        val = (
            "\n".join(f"| {k} | {v} |" for k, v in self.valuation.items())
            if self.valuation
            else "| — | — |"
        )
        return f"""## Halka Arz Özeti

| Kalem | Değer |
| --- | --- |
| Şirket | {self.company} |
| Borsa Kodu | {self.ticker} |
| Halka Arz Fiyatı | {self.price or '-'} |
| İskonto Oranı | {self.discount_rate or '-'} |
| Halka Arz Büyüklüğü | {self.offer_size or '-'} |
| Net Kâr Marjı | {self.net_margin or '-'} |

## Fonun Kullanım Yeri

{bullets(self.fund_usage)}

## Değerleme Çarpanları

| Çarpan | Değer |
| --- | --- |
{val}

## Belgede Öne Çıkarılan Bilgiler

{bullets(self.strengths)}

## Belgede Belirtilen Riskler

{bullets(self.risks)}

## Taahhütler

{bullets(self.commitments)}

## Özet

{self.verdict or 'Özet üretilemedi.'}

*Bilgi ayıklama güven düzeyi: {self.confidence}.*"""

    def to_pdf_data(self) -> dict:
        return {
            "company_name": self.company,
            "ticker": self.ticker,
            "price": self.price,
            "discount": self.discount_rate,
            "offer_size": self.offer_size,
            "net_margin": self.net_margin,
            "fund_usage": self.fund_usage,
            "commitments": self.commitments,
            "strengths": self.strengths,
            "risks": self.risks,
            "valuation": self.valuation,
            "verdict": self.verdict,
        }


_PROMPT = """Sen tarafsız bir belge özetleyicisisin. Aşağıdaki halka arz
izahnamesi / fiyat tespit raporu bölümlerinden bilgi ayıkla ve yalnızca JSON döndür.
Bulamadığın alanları boş bırak (uydurma). Yalnızca belgede yazanları aktar: halka arza
katılım önerisi, "cazip/pahalı/ucuz" gibi değerleme yargısı, fiyat veya getiri tahmini YAZMA.

ÖNEMLİ biçim kuralları:
1. "price", "discount_rate", "offer_size" ve valuation değerlerinin HER BİRİ
   birimini/sembolünü KENDİ İÇİNDE barındırmalı (örn. "45,50 TL", "%22,5",
   "500 Milyon TL"). Bu alanları gösteren şablonlar birim EKLEMEZ.
2. "discount_rate" kesinlikle yüzde biçiminde olmalı (örn. "%22,5" veya "22,5%").
   İzahnamede "halka arz fiyatı / değerleme iskonto oranı" veya "piyasa değeri /
   defter değeri" iskontosundan hesaplanan oran. Bulamazsan boş bırak.
3. "net_margin" (Net Kâr Marjı) varsa yüzde olarak ver (örn. "%18,3").
4. "valuation" içindeki değerler KISA olmalı — sadece rakam/oran (örn. "12,3"
   veya "8,1x"). Net bir rakam bulamazsan o çarpanı boş bırak.
5. "fund_usage" kalemleri mümkün olduğunca kısa tut (örn. "Kapasite artırımı %50",
   "Ar-Ge %30", "Borç ödemesi %20"). Her kalem tek satır, max 50 karakter.

Şirket: {company} ({ticker})

Belge bölümleri:
\"\"\"
{document}
\"\"\"

Şu JSON şemasını doldur:
{{
  "price": "halka arz fiyatı, birimiyle (örn. '45,50 TL')",
  "discount_rate": "iskonto oranı, yüzde işaretiyle (örn. '%22,5')",
  "offer_size": "halka arz büyüklüğü, birimiyle (örn. '500 Milyon TL')",
  "net_margin": "net kâr marjı yüzde olarak (örn. '%18,3') — bulamazsan boş",
  "fund_usage": ["kısa fon kullanım kalemleri, her biri max 50 karakter"],
  "commitments": ["fiyat istikrarı, ortak satmama, bedelli yok gibi taahhütler"],
  "strengths": ["belgede şirketin öne çıkardığı 3-5 bilgi (belgedeki ifadeyle)"],
  "risks": ["belgenin risk bölümünde yazan 3-5 risk"],
  "valuation": {{"F/K": "", "PD/DD": "", "FD/FAVÖK": ""}},
  "verdict": "belgenin 2-3 cümlelik tarafsız özeti (değerlendirme veya öneri değil)",
  "confidence": "düşük|orta|yüksek"
}}"""


class IpoProspectusAnalyzer:
    def __init__(self) -> None:
        self.client = LlmClient(settings.gemini_model, max_output_tokens=2560)

    def analyze(self, document_text: str, company: str, ticker: str) -> IpoAnalysis:
        # Gerçek fiyat tespit raporları 100-200K karakter olabilir (çok sayfalı);
        # 8000 karakterlik bütçe genelde giriş/metodoloji bölümlerini yakalayıp asıl
        # fiyat SONUCUNU (genelde dokümanın ilerleyen bir bölümünde) kaçırıyordu.
        # Gemini flash'ın bağlam penceresi bu bütçeyi rahatça karşılar; maliyet ihmal
        # edilebilir düzeyde artar ama isabet oranı önemli ölçüde yükselir.
        relevant = extract_relevant(document_text, IPO_KEYWORDS, max_chars=24000)
        if not self.client.enabled:
            log.info("IPO analizörü: AI kapalı; iskele analizi dönülüyor.")
            return self._fallback(company, ticker)

        data = self.client.generate_json(
            _PROMPT.format(company=company, ticker=ticker, document=relevant)
        )
        if not data:
            log.warning("IPO analizi üretilemedi; fallback dönülüyor.")
            return self._fallback(company, ticker)

        return IpoAnalysis(
            company=company,
            ticker=ticker,
            price=str(data.get("price", "")),
            discount_rate=str(data.get("discount_rate", "")),
            offer_size=str(data.get("offer_size", "")),
            net_margin=str(data.get("net_margin", "")),
            fund_usage=_as_list(data.get("fund_usage")),
            commitments=_as_list(data.get("commitments")),
            strengths=_as_list(data.get("strengths")),
            risks=_as_list(data.get("risks")),
            valuation=_as_dict(data.get("valuation")),
            verdict=str(data.get("verdict", "")),
            confidence=str(data.get("confidence", "orta")),
            ai_generated=True,
        )

    @staticmethod
    def _fallback(company: str, ticker: str) -> IpoAnalysis:
        return IpoAnalysis(
            company=company,
            ticker=ticker,
            verdict=(
                "Yapay zeka analizi şu an devre dışı. Belge alındı ancak otomatik "
                "değerlendirme üretilemedi."
            ),
            confidence="düşük",
            ai_generated=False,
        )


def _as_list(value: object) -> list[str]:
    if isinstance(value, list):
        # None/null öğeleri at — str(None) == "None" gibi anlamlı görünen ama
        # aslında boş bir değeri yanlışlıkla tutmayalım.
        return [str(v) for v in value if v not in (None, "") and str(v).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _as_dict(value: object) -> dict[str, str]:
    if isinstance(value, dict):
        return {
            str(k): str(v)
            for k, v in value.items()
            if v not in (None, "") and str(v).strip()
        }
    return {}
