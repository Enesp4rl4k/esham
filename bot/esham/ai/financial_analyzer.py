"""Şirket finansal/faaliyet raporu analizörü.

Bilanço, gelir tablosu ve dipnotları alır; küçük yatırımcının gözden kaçırabileceği
olumlu noktaları ve gizli riskleri (red flags) yapılandırılmış biçimde çıkarır.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ..config import get_logger, settings
from ..documents.sections import FINANCIAL_KEYWORDS, extract_relevant
from .client import LlmClient

log = get_logger(__name__)


@dataclass
class FinancialAnalysis:
    company: str
    period: str = ""
    summary: str = ""
    strengths: list[str] = field(default_factory=list)
    red_flags: list[str] = field(default_factory=list)
    ratios: dict[str, str] = field(default_factory=dict)  # Net Kâr Marjı, Cari Oran, Net Borç/FAVÖK
    ai_generated: bool = True

    def to_markdown(self) -> str:
        def bullets(items: list[str]) -> str:
            return "\n".join(f"- {i}" for i in items) if items else "- Belirtilmemiş"

        ratios = (
            "\n".join(f"| {k} | {v} |" for k, v in self.ratios.items())
            if self.ratios
            else "| — | — |"
        )
        return f"""## Genel Görünüm

{self.summary or 'Özet üretilemedi.'}

## Temel Oranlar

| Oran | Değer |
| --- | --- |
{ratios}

## ✅ Olumlu Noktalar

{bullets(self.strengths)}

## 🚨 Gizli Tehlikeler / Red Flags

{bullets(self.red_flags)}"""


_PROMPT = """Sen kıdemli bir finansal analistsin. Aşağıdaki finansal tablo/faaliyet
raporu bölümlerini incele ve yalnızca JSON döndür. Yatırım tavsiyesi verme; nesnel ol.
Küçük yatırımcının gözden kaçırabileceği noktalara odaklan.

Şirket: {company} — Dönem: {period}

Belge bölümleri:
\"\"\"
{document}
\"\"\"

Şu JSON şemasını doldur:
{{
  "summary": "2-3 cümlelik genel görünüm",
  "ratios": {{"Net Kâr Marjı": "", "Cari Oran": "", "Net Borç/FAVÖK": "", "Özkaynak Kârlılığı": ""}},
  "strengths": ["3 olumlu nokta"],
  "red_flags": ["3 gizli tehlike/riskli nokta"]
}}"""


class FinancialReportAnalyzer:
    def __init__(self) -> None:
        self.client = LlmClient(settings.gemini_model, max_output_tokens=1280)

    def analyze(self, document_text: str, company: str, period: str = "") -> FinancialAnalysis:
        relevant = extract_relevant(document_text, FINANCIAL_KEYWORDS, max_chars=8000)
        if not self.client.enabled:
            log.info("Finansal analizör: AI kapalı; iskele analizi dönülüyor.")
            return FinancialAnalysis(
                company=company,
                period=period,
                summary="Yapay zeka analizi şu an devre dışı.",
                ai_generated=False,
            )

        data = self.client.generate_json(
            _PROMPT.format(company=company, period=period or "-", document=relevant)
        )
        if not data:
            return FinancialAnalysis(
                company=company,
                period=period,
                summary="Analiz üretilemedi.",
                ai_generated=False,
            )

        return FinancialAnalysis(
            company=company,
            period=period,
            summary=str(data.get("summary", "")),
            strengths=_as_list(data.get("strengths")),
            red_flags=_as_list(data.get("red_flags")),
            ratios={str(k): str(v) for k, v in (data.get("ratios") or {}).items() if str(v).strip()},
            ai_generated=True,
        )


def _as_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(v) for v in value if str(v).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []
