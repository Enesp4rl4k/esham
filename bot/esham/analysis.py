"""Belge analiz orkestrasyonu.

Bir KAP belgesini (izahname, fiyat tespit, faaliyet raporu) alır, yapılandırılmış
analiz üretir ve sonucu yayınlar: web raporu (markdown) + halka arzsa ayrıca PDF.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .ai import (
    FinancialAnalysis,
    FinancialReportAnalyzer,
    IpoAnalysis,
    IpoProspectusAnalyzer,
)
from .config import get_logger
from .documents import load_document_text
from .publishing import ContentStore, ReportDraft
from .publishing.ipo_pdf import IpoPdfGenerator

log = get_logger(__name__)


@dataclass
class IpoResult:
    analysis: IpoAnalysis
    slug: str | None = None
    report_path: Path | None = None
    pdf_path: Path | None = None


def analyze_ipo_document(
    source: str,
    company: str,
    ticker: str,
    *,
    publish: bool = True,
    make_pdf: bool = True,
) -> IpoResult:
    """`source`: PDF yolu/URL, KAP linki veya ham metin."""
    log.info("Halka arz analizi başlıyor: %s (%s)", company, ticker)
    text = load_document_text(source)
    if not text:
        log.warning("Belge metni boş; analiz yine de denenecek (fallback olası).")

    analysis = IpoProspectusAnalyzer().analyze(text, company, ticker)
    result = IpoResult(analysis=analysis)

    if publish:
        summary = analysis.verdict or f"{company} halka arzı için yapılandırılmış analiz."
        draft = ReportDraft(
            title=f"{company} Halka Arz Analizi",
            category="ipo",
            summary=summary[:200],
            body=analysis.to_markdown(),
            sources=["KAP", "İzahname", "Fiyat Tespit Raporu"],
            tags=[ticker, "Halka Arz"],
            ai_generated=analysis.ai_generated,
        )
        result.report_path = ContentStore().publish(draft)
        # Yayın guardrail'a takıldıysa slug atama — var olmayan rapora link verilmesin.
        if result.report_path is not None:
            result.slug = draft.resolved_slug()
        else:
            log.error("Halka arz raporu guardrail'a takıldı; web yayını iptal.")

    if make_pdf:
        result.pdf_path = IpoPdfGenerator().create(analysis.to_pdf_data())

    log.info("Halka arz analizi tamam: %s", ticker)
    return result


def analyze_company_report(
    source: str,
    company: str,
    period: str = "",
    *,
    publish: bool = True,
) -> FinancialAnalysis:
    """Şirket finansal/faaliyet raporu analizi."""
    log.info("Finansal analiz başlıyor: %s (%s)", company, period)
    text = load_document_text(source)
    analysis = FinancialReportAnalyzer().analyze(text, company, period)

    if publish:
        title = f"{company} Finansal Analiz" + (f" — {period}" if period else "")
        ContentStore().publish(
            ReportDraft(
                title=title,
                category="bist",
                summary=(analysis.summary or f"{company} finansal tablo analizi.")[:200],
                body=analysis.to_markdown(),
                sources=["KAP", "Finansal Tablolar"],
                tags=[company, "Bilanço", "Analiz"],
                ai_generated=analysis.ai_generated,
            )
        )

    log.info("Finansal analiz tamam: %s", company)
    return analysis
