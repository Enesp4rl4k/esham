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
    fund_usage: list[str] = field(default_factory=list)
    commitments: list[str] = field(default_factory=list)
    strengths: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    valuation: dict[str, str] = field(default_factory=dict)  # F/K, PD/DD, FD/FAVÖK
    verdict: str = ""
    confidence: str = "orta"  # düşük | orta | yüksek
    ai_generated: bool = True

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

## Fonun Kullanım Yeri

{bullets(self.fund_usage)}

## Değerleme Çarpanları

| Çarpan | Değer |
| --- | --- |
{val}

## ✅ Olumlu Noktalar

{bullets(self.strengths)}

## 🚨 Dikkat Edilecek Riskler

{bullets(self.risks)}

## Taahhütler

{bullets(self.commitments)}

## Değerlendirme

{self.verdict or 'Değerlendirme üretilemedi.'}

*Analiz güven düzeyi: {self.confidence}.*"""

    def to_pdf_data(self) -> dict:
        return {
            "company_name": self.company,
            "ticker": self.ticker,
            "price": self.price,
            "discount": self.discount_rate,
            "offer_size": self.offer_size,
            "fund_usage": self.fund_usage,
            "commitments": self.commitments,
            "strengths": self.strengths,
            "risks": self.risks,
            "valuation": self.valuation,
            "verdict": self.verdict,
        }


_PROMPT = """Sen deneyimli bir sermaye piyasası analistisin. Aşağıdaki halka arz
izahnamesi / fiyat tespit raporu bölümlerini incele ve yalnızca JSON döndür.
Yatırım tavsiyesi verme; nesnel ol. Bulamadığın alanları boş bırak.

Şirket: {company} ({ticker})

Belge bölümleri:
\"\"\"
{document}
\"\"\"

Şu JSON şemasını doldur:
{{
  "price": "halka arz fiyatı (TL)",
  "discount_rate": "iskonto oranı (%)",
  "offer_size": "halka arz büyüklüğü",
  "fund_usage": ["fon kullanım kalemleri"],
  "commitments": ["fiyat istikrarı, ortak satmama, bedelli yok gibi taahhütler"],
  "strengths": ["3-5 olumlu nokta"],
  "risks": ["3-5 risk/red flag"],
  "valuation": {{"F/K": "", "PD/DD": "", "FD/FAVÖK": ""}},
  "verdict": "2-3 cümlelik nesnel değerlendirme",
  "confidence": "düşük|orta|yüksek"
}}"""


class IpoProspectusAnalyzer:
    def __init__(self) -> None:
        self.client = LlmClient(settings.gemini_model, max_output_tokens=1536)

    def analyze(self, document_text: str, company: str, ticker: str) -> IpoAnalysis:
        relevant = extract_relevant(document_text, IPO_KEYWORDS, max_chars=8000)
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
        return [str(v) for v in value if str(v).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _as_dict(value: object) -> dict[str, str]:
    if isinstance(value, dict):
        return {str(k): str(v) for k, v in value.items() if str(v).strip()}
    return {}
