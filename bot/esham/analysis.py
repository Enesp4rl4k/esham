"""Belge analiz orkestrasyonu.

Bir KAP belgesini (izahname, fiyat tespit, faaliyet raporu) alır, yapılandırılmış
analiz üretir ve sonucu yayınlar: web raporu (markdown) + halka arzsa ayrıca PDF +
gerçek analiz verisine dayalı marka kartı (aynı kart hem web hero'da hem tweet'te
kullanılır).
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
from .publishing.cards import CardGenerator, CardSpec
from .publishing.ipo_pdf import IpoPdfGenerator

log = get_logger(__name__)

_cards = CardGenerator()


def _render_card(spec: CardSpec) -> Path | None:
    try:
        return _cards.render(spec)
    except Exception as exc:  # kart üretimi asla analizi/yayını durdurmasın
        log.warning("Kart görseli üretilemedi (%s); görselsiz devam ediliyor.", exc)
        return None


@dataclass
class IpoResult:
    analysis: IpoAnalysis
    slug: str | None = None
    report_path: Path | None = None
    pdf_path: Path | None = None
    image_path: Path | None = None


def _ipo_card_spec(company: str, ticker: str, analysis: IpoAnalysis) -> CardSpec:
    """IpoAnalysis nesnesinden IPO kart spesifikasyonu üretir.

    Kart ızgarası (4 hücre, soldan sağa):
      1. Fiyat        — halka arz fiyatı (TL birimi dahil)
      2. İskonto      — yüzde oranı
      3. Hasılat      — halka arz büyüklüğü
      4. Marj / F/K   — net kâr marjı varsa, yoksa ilk değerleme çarpanı

    Büyük iskonto rozeti: discount_pct_float() > 20 ise _render_ipo sağ kenarda gösterir.
    Fon kullanımı özeti: fund_usage_summary(3) → kartın alt satırı.
    """
    metrics: list[tuple[str, str]] = []

    if analysis.price:
        price_str = analysis.price
        if "TL" not in price_str and "tl" not in price_str.lower():
            price_str = f"{price_str} TL"
        metrics.append(("Fiyat", price_str))

    if analysis.discount_rate:
        metrics.append(("İskonto", analysis.discount_rate))

    if analysis.offer_size:
        metrics.append(("Hasılat", analysis.offer_size))

    # 4. hücre: Net Kâr Marjı öncelikli, yoksa ilk değerleme çarpanı
    if analysis.net_margin:
        metrics.append(("Marj", analysis.net_margin))
    else:
        for name, value in list(analysis.valuation.items())[:1]:
            if value:
                metrics.append((name, value))

    return CardSpec(
        category="ipo",
        kicker="Halka Arz Analizi",
        headline=company,
        ticker=ticker,
        metrics=metrics,
        discount_pct=analysis.discount_pct_float(),
        fund_usage=analysis.fund_usage_summary(max_items=3),
        template="ipo" if metrics else "bist",
    )


def analyze_ipo_document(
    source: str,
    company: str,
    ticker: str,
    *,
    publish: bool = True,
    make_pdf: bool = True,
    disclosure_date: str = "",
) -> IpoResult:
    """`source`: PDF yolu/URL, KAP linki veya ham metin.

    `disclosure_date`: KAP bildirim tarihi (`YYYY-MM-DD`) — rapor JSON'undaki
    `ipo.disclosureDate` alanına yazılır, halka arz takvimi sayfası bunu kullanır.
    """
    log.info("Halka arz analizi başlıyor: %s (%s)", company, ticker)
    text = load_document_text(source)
    if not text:
        log.warning("Belge metni boş; analiz yine de denenecek (fallback olası).")

    analysis = IpoProspectusAnalyzer().analyze(text, company, ticker)
    result = IpoResult(analysis=analysis)
    result.image_path = _render_card(_ipo_card_spec(company, ticker, analysis))

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
            image_path=result.image_path,
            ipo=analysis.to_meta(disclosure_date),
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
        card_path = _render_card(
            CardSpec(
                category="bist",
                kicker=f"Finansal Analiz{' — ' + period if period else ''}",
                headline=f"{company}: {analysis.summary}" if analysis.summary else company,
                metrics=list(analysis.ratios.items())[:3],
                radar_scores=analysis.radar_scores,
            )
        )
        ContentStore().publish(
            ReportDraft(
                title=title,
                category="bist",
                summary=(analysis.summary or f"{company} finansal tablo analizi.")[:200],
                body=analysis.to_markdown(),
                sources=["KAP", "Finansal Tablolar"],
                tags=[company, "Bilanço", "Analiz"],
                ai_generated=analysis.ai_generated,
                image_path=card_path,
            )
        )

    log.info("Finansal analiz tamam: %s", company)
    return analysis
