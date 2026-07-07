"""Sabah bülteni PDF üreticisi (reportlab).

reportlab saf Python, sistem bağımlılığı yok, Türkçe desteği mükemmel.
Esham marka kimliğiyle branded, A4 formatında sabah piyasa bülteni PDF'i üretir.

Çıktı: web/public/reports/{slug}.pdf (Cloudflare Pages'te statik dosya olarak sunulur)
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ..config import get_logger, settings
from ..sources import MarketSnapshot

log = get_logger(__name__)

# Çıktı klasörü
_DEFAULT_OUT_DIR = Path(__file__).resolve().parents[4] / "web" / "public" / "reports"

# Renk paleti (Esham dark theme) — RGB 0-1 arası (reportlab formatı)
def _c(r: int, g: int, b: int):
    """0-255 RGB → reportlab Color."""
    from reportlab.lib.colors import Color  # type: ignore[import]
    return Color(r / 255, g / 255, b / 255)


def _strip_md(text: str) -> str:
    """Markdown işaretlerini düz metne çevirir."""
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"\*(.+?)\*", r"\1", text)
    text = re.sub(r"`(.+?)`", r"\1", text)
    text = re.sub(r"#+\s*", "", text)
    text = re.sub(r"^\s*[-*•]\s+", "• ", text, flags=re.MULTILINE)
    return text.strip()


def generate_pdf(
    body_md: str,
    snapshot: MarketSnapshot,
    slug: str,
    title: str = "BIST & Küresel Piyasalar Sabah Raporu",
    out_dir: Path | None = None,
) -> Path | None:
    """reportlab ile branded PDF sabah bülteni üretir. Path döner, başarısızsa None."""
    try:
        from reportlab.lib import colors  # type: ignore[import]
        from reportlab.lib.pagesizes import A4  # type: ignore[import]
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle  # type: ignore[import]
        from reportlab.lib.units import mm  # type: ignore[import]
        from reportlab.platypus import (  # type: ignore[import]
            SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
        )
        from reportlab.pdfbase import pdfmetrics  # type: ignore[import]
        from reportlab.pdfbase.ttfonts import TTFont  # type: ignore[import]
        from reportlab.lib.colors import HexColor, Color  # type: ignore[import]
    except ImportError:
        log.warning("reportlab kurulu degil; PDF atlaniyor. pip install reportlab")
        return None

    out_dir = out_dir or _DEFAULT_OUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = out_dir / f"{slug}.pdf"

    try:
        # Renk sabitleri
        C_BLACK   = HexColor("#060B18")
        C_NAVY    = HexColor("#0F172A")
        C_SLATE8  = HexColor("#1E293B")
        C_SLATE6  = HexColor("#475569")
        C_SLATE4  = HexColor("#94A3B8")
        C_WHITE   = HexColor("#F1F5F9")
        C_BLUE    = HexColor("#3B82F6")
        C_GREEN   = HexColor("#22C55E")
        C_RED     = HexColor("#EF4444")
        C_BODY    = HexColor("#334155")
        C_LIGHT   = HexColor("#F8FAFC")
        C_DARK    = HexColor("#0F172A")

        page_w, page_h = A4

        # ── Özel font kaydet (varsa) ───────────────────────────────────────────
        _FONTS_DIR = Path(__file__).resolve().parent.parent / "assets" / "fonts"
        _inter  = _FONTS_DIR / "Inter-Regular.ttf"
        _outfit = _FONTS_DIR / "Outfit-Bold.ttf"

        font_body = "Helvetica"
        font_bold = "Helvetica-Bold"
        font_head = "Helvetica-Bold"

        # reportlab kendi içinde Latin-1+ subset desteği var.
        # Türkçe için TTFont + encoding=utf8 yeterli.
        if _inter.exists():
            try:
                pdfmetrics.registerFont(TTFont("Inter", str(_inter)))
                font_body = "Inter"
            except Exception:
                pass  # variable font sorunu — Helvetica fallback

        if _outfit.exists():
            try:
                pdfmetrics.registerFont(TTFont("Outfit", str(_outfit)))
                font_head = "Outfit"
                font_bold = "Outfit"
            except Exception:
                pass

        # ── Stil tanımları ──────────────────────────────────────────────────────
        def style(name, parent="Normal", **kw):
            return ParagraphStyle(name, fontName=kw.pop("fontName", font_body),
                                  textColor=kw.pop("textColor", C_BODY), **kw)

        s_title = style("ETitle", fontName=font_head, fontSize=15,
                        textColor=C_DARK, spaceAfter=4, leading=20)
        s_h2    = style("EH2", fontName=font_bold, fontSize=10,
                        textColor=C_DARK, spaceBefore=10, spaceAfter=4,
                        leading=14, leftIndent=8,
                        borderPad=(0, 0, 0, 0))
        s_h3    = style("EH3", fontName=font_bold, fontSize=9,
                        textColor=C_BODY, spaceBefore=6, spaceAfter=3, leading=13)
        s_body  = style("EBody", fontSize=8.5, leading=13, spaceAfter=3)
        s_bullet= style("EBullet", fontSize=8.5, leading=13, spaceAfter=2,
                        leftIndent=12, bulletIndent=4)
        s_meta  = style("EMeta", fontName=font_bold, fontSize=7,
                        textColor=C_SLATE4, leading=10)
        s_footer= style("EFoot", fontSize=7, textColor=C_SLATE6, leading=9)

        # ── Belge oluştur ───────────────────────────────────────────────────────
        today = datetime.now(timezone(timedelta(hours=3)))
        date_str = today.strftime("%d.%m.%Y")
        time_str = today.strftime("%H:%M")

        # Canvas callback — başlık ve footer her sayfada
        def _on_page(canvas, doc):
            canvas.saveState()
            w, h = A4

            # ── Üst başlık bandı ────────────────────────────────────────────
            canvas.setFillColor(C_BLACK)
            canvas.rect(0, h - 42*mm, w, 42*mm, fill=1, stroke=0)

            # Marka
            canvas.setFillColor(C_BLUE)
            canvas.setFont(font_head, 22)
            canvas.drawString(12*mm, h - 16*mm, "E")
            canvas.setFillColor(C_WHITE)
            canvas.drawString(22*mm, h - 16*mm, "sham")

            canvas.setFillColor(C_SLATE6)
            canvas.setFont(font_body, 7)
            canvas.drawString(12*mm, h - 24*mm, "YAPAY ZEKA DESTEKLI PIYASA ANALIZI")

            # Sağ: tarih
            canvas.setFillColor(C_BLUE)
            canvas.setFont(font_bold, 8)
            canvas.drawRightString(w - 12*mm, h - 12*mm, "SABAH BULTENI")
            canvas.setFillColor(C_WHITE)
            canvas.setFont(font_head, 16)
            canvas.drawRightString(w - 12*mm, h - 22*mm, date_str)
            canvas.setFillColor(C_SLATE4)
            canvas.setFont(font_body, 8)
            canvas.drawRightString(w - 12*mm, h - 29*mm, f"{time_str} TR")

            # Accent çizgi
            canvas.setFillColor(C_BLUE)
            canvas.rect(0, h - 43.5*mm, w, 1.5*mm, fill=1, stroke=0)

            # ── Piyasa ticker bandı ─────────────────────────────────────────
            canvas.setFillColor(C_NAVY)
            canvas.rect(0, h - 65*mm, w, 21.5*mm, fill=1, stroke=0)

            bist = snapshot.bist
            pills = []
            if bist:
                pills.append((bist.index, bist.price, bist.change or ""))
            if snapshot.macro and snapshot.macro.tickers:
                for t in snapshot.macro.tickers[:4]:
                    pills.append((t.label, t.value_str, ""))

            px = 12 * mm
            for label, value, change in pills[:5]:
                canvas.setFillColor(C_SLATE4)
                canvas.setFont(font_bold, 7)
                canvas.drawString(px, h - 49*mm, str(label).upper()[:10])

                canvas.setFillColor(C_WHITE)
                canvas.setFont(font_bold, 9)
                canvas.drawString(px, h - 56*mm, str(value)[:12])

                if change:
                    clr = C_GREEN if str(change).startswith("+") else (C_RED if str(change).startswith("-") else C_SLATE4)
                    canvas.setFillColor(clr)
                    canvas.setFont(font_bold, 7)
                    canvas.drawString(px, h - 62*mm, str(change)[:8])

                px += 38 * mm

            # ── Rapor başlığı ────────────────────────────────────────────────
            canvas.setFillColor(C_LIGHT)
            canvas.rect(0, h - 83*mm, w, 18*mm, fill=1, stroke=0)
            canvas.setStrokeColor(C_SLATE8)
            canvas.setLineWidth(0.3)
            canvas.line(0, h - 83*mm, w, h - 83*mm)

            canvas.setFillColor(C_DARK)
            canvas.setFont(font_head, 13)
            # Başlık uzunsa kısalt
            safe_title = title[:65] + ("…" if len(title) > 65 else "")
            canvas.drawString(12*mm, h - 76*mm, safe_title)

            # ── Footer ──────────────────────────────────────────────────────
            canvas.setFillColor(C_BLACK)
            canvas.rect(0, 0, w, 12*mm, fill=1, stroke=0)
            canvas.setStrokeColor(C_SLATE8)
            canvas.setLineWidth(0.3)
            canvas.line(0, 12*mm, w, 12*mm)

            canvas.setFillColor(C_SLATE4)
            canvas.setFont(font_bold, 7.5)
            canvas.drawString(12*mm, 5*mm, "esham.pages.dev")

            canvas.setFillColor(C_SLATE6)
            canvas.setFont(font_body, 7)
            canvas.drawRightString(w - 12*mm, 5*mm, "Bu rapor yatirim tavsiyesi degildir.")

            canvas.restoreState()

        doc = SimpleDocTemplate(
            str(pdf_path),
            pagesize=A4,
            leftMargin=12*mm,
            rightMargin=12*mm,
            topMargin=88*mm,    # başlık + ticker + rapor başlığı için alan
            bottomMargin=18*mm,
        )

        # ── İçerik akışı ────────────────────────────────────────────────────
        story = []

        lines = body_md.split("\n")
        for raw_line in lines:
            stripped = raw_line.strip()

            if not stripped:
                story.append(Spacer(1, 3*mm))
                continue

            if stripped.startswith("## "):
                heading = _strip_md(stripped[3:])
                # Sol accent çizgi — tablo ile simüle
                tbl = Table(
                    [[Paragraph(heading.upper(), s_h2)]],
                    colWidths=[doc.width],
                )
                tbl.setStyle(TableStyle([
                    ("LEFTPADDING",  (0, 0), (-1, -1), 8),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                    ("TOPPADDING",   (0, 0), (-1, -1), 2),
                    ("BOTTOMPADDING",(0, 0), (-1, -1), 2),
                    ("LINEBEFORE",   (0, 0), (0, -1), 3, C_BLUE),
                    ("BACKGROUND",   (0, 0), (-1, -1), colors.white),
                ]))
                story.append(tbl)
                story.append(Spacer(1, 2*mm))
                continue

            if stripped.startswith("### "):
                heading = _strip_md(stripped[4:])
                story.append(Paragraph(heading, s_h3))
                continue

            if stripped.startswith(("- ", "* ", "• ")):
                item = _strip_md(stripped[2:])
                story.append(Paragraph(f"• {item}", s_bullet))
                continue

            # Numaralı liste
            m = re.match(r"^(\d+)\.\s+(.+)$", stripped)
            if m:
                item = _strip_md(m.group(2))
                story.append(Paragraph(f"• {item}", s_bullet))
                continue

            text = _strip_md(stripped)
            if text:
                story.append(Paragraph(text, s_body))

        # ── Sektör tablosu ───────────────────────────────────────────────────
        if snapshot.sector:
            sectors = sorted(
                snapshot.sector,
                key=lambda s: float(getattr(s, "change_pct", 0) or 0),
                reverse=True,
            )[:8]

            if sectors:
                story.append(Spacer(1, 5*mm))
                story.append(HRFlowable(width="100%", thickness=0.5,
                                        color=C_SLATE8, spaceAfter=4*mm))

                # Başlık
                tbl = Table(
                    [[Paragraph("SEKTÖR GÖRÜNÜMÜ", s_h2)]],
                    colWidths=[doc.width],
                )
                tbl.setStyle(TableStyle([
                    ("LEFTPADDING",  (0, 0), (-1, -1), 8),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                    ("TOPPADDING",   (0, 0), (-1, -1), 2),
                    ("BOTTOMPADDING",(0, 0), (-1, -1), 2),
                    ("LINEBEFORE",   (0, 0), (0, -1), 3, C_BLUE),
                    ("BACKGROUND",   (0, 0), (-1, -1), colors.white),
                ]))
                story.append(tbl)
                story.append(Spacer(1, 3*mm))

                # Tablo verileri
                header_style = ParagraphStyle(
                    "SHead", fontName=font_bold, fontSize=7.5,
                    textColor=C_SLATE4, leading=10,
                )
                cell_style = ParagraphStyle(
                    "SCell", fontName=font_body, fontSize=8,
                    textColor=C_BODY, leading=11,
                )

                tdata = [[
                    Paragraph("SEKTÖR", header_style),
                    Paragraph("DEĞİŞİM", header_style),
                ]]
                for s in sectors:
                    pct = float(getattr(s, "change_pct", 0) or 0)
                    name = getattr(s, "name", "")
                    pct_color = "#22C55E" if pct >= 0 else "#EF4444"
                    tdata.append([
                        Paragraph(name, cell_style),
                        Paragraph(
                            f'<font color="{pct_color}"><b>{pct:+.2f}%</b></font>',
                            cell_style,
                        ),
                    ])

                col_w = [doc.width * 0.75, doc.width * 0.25]
                stbl = Table(tdata, colWidths=col_w)
                stbl.setStyle(TableStyle([
                    ("BACKGROUND",   (0, 0), (-1, 0),  C_LIGHT),
                    ("ROWBACKGROUNDS",(0,1),(-1,-1),   [colors.white, HexColor("#F8FAFC")]),
                    ("LINEBELOW",    (0, 0), (-1, -1), 0.3, C_SLATE8),
                    ("TOPPADDING",   (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING",(0, 0), (-1, -1), 4),
                    ("LEFTPADDING",  (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                    ("ALIGN",        (1, 0), (1, -1),  "RIGHT"),
                ]))
                story.append(stbl)

        doc.build(story, onFirstPage=_on_page, onLaterPages=_on_page)
        log.info("PDF uretildi (reportlab): %s", pdf_path)
        return pdf_path

    except Exception as exc:
        log.warning("PDF uretilemedi: %s", exc)
        return None
