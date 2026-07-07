"""Sabah bülteni PDF üreticisi (fpdf2).

fpdf2 saf Python, sistem bağımlılığı yok — GitHub Actions ve Render'da sorunsuz çalışır.
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

# Çıktı klasörü — web/public/reports/ altında statik olarak sunulur
_DEFAULT_OUT_DIR = Path(__file__).resolve().parents[4] / "web" / "public" / "reports"

# Renk paleti (Esham dark theme)
_BLACK    = (6,   11,  24)   # #060B18 — arkaplan
_NAVY     = (15,  23,  42)   # #0F172A — kart arkaplanı
_SLATE800 = (30,  41,  59)   # #1E293B — kenarlık
_SLATE600 = (71,  85,  105)  # #475569 — muted metin
_SLATE400 = (148, 163, 184)  # #94A3B8 — ikincil metin
_WHITE    = (241, 245, 249)  # #F1F5F9 — ana metin
_BLUE     = (59,  130, 246)  # #3B82F6 — accent
_GREEN    = (34,  197, 94)   # #22C55E — pozitif
_RED      = (239, 68,  68)   # #EF4444 — negatif


def _change_color(change: str) -> tuple[int, int, int]:
    if change and change.strip().startswith("+"):
        return _GREEN
    if change and change.strip().startswith("-"):
        return _RED
    return _SLATE400


def _strip_md(text: str) -> str:
    """Markdown işaretlerini düz metne çevirir."""
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)   # bold
    text = re.sub(r"\*(.+?)\*", r"\1", text)         # italic
    text = re.sub(r"`(.+?)`", r"\1", text)            # code
    text = re.sub(r"#+\s*", "", text)                 # başlıklar
    text = re.sub(r"^\s*[-*]\s+", "• ", text, flags=re.MULTILINE)  # listeler
    return text.strip()


def generate_pdf(
    body_md: str,
    snapshot: MarketSnapshot,
    slug: str,
    title: str = "BIST & Küresel Piyasalar Sabah Raporu",
    out_dir: Path | None = None,
) -> Path | None:
    """fpdf2 ile branded PDF sabah bülteni üretir. Path döner, başarısızsa None."""
    try:
        from fpdf import FPDF  # type: ignore[import]
    except ImportError:
        log.warning("fpdf2 kurulu değil; PDF atlanıyor. pip install fpdf2")
        return None

    out_dir = out_dir or _DEFAULT_OUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = out_dir / f"{slug}.pdf"

    try:
        today = datetime.now(timezone(timedelta(hours=3)))
        date_str = today.strftime("%d.%m.%Y")
        time_str = today.strftime("%H:%M")

        pdf = FPDF(orientation="P", unit="mm", format="A4")
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.add_page()

        # ── Karanlık başlık bandı ──────────────────────────────────────────────
        pdf.set_fill_color(*_BLACK)
        pdf.rect(0, 0, 210, 40, "F")

        # Sol: Marka adı
        pdf.set_xy(12, 8)
        pdf.set_font("Helvetica", "B", 22)
        pdf.set_text_color(*_BLUE)
        pdf.cell(12, 10, "E")
        pdf.set_text_color(*_WHITE)
        pdf.set_font("Helvetica", "B", 22)
        pdf.cell(0, 10, "sham", ln=False)

        # Tagline
        pdf.set_xy(12, 21)
        pdf.set_font("Helvetica", "", 7)
        pdf.set_text_color(*_SLATE600)
        pdf.cell(0, 5, "YAPAY ZEKA DESTEKLI PIYASA ANALIZI")

        # Sağ: Tarih ve rapor tipi
        pdf.set_xy(130, 8)
        pdf.set_font("Helvetica", "B", 8)
        pdf.set_text_color(*_BLUE)
        pdf.cell(68, 5, "SABAH BULTENI", align="R", ln=True)

        pdf.set_xy(130, 15)
        pdf.set_font("Helvetica", "B", 16)
        pdf.set_text_color(*_WHITE)
        pdf.cell(68, 8, date_str, align="R", ln=True)

        pdf.set_xy(130, 25)
        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(*_SLATE400)
        pdf.cell(68, 5, f"{time_str} TR", align="R", ln=True)

        # Accent çizgi
        pdf.set_fill_color(*_BLUE)
        pdf.rect(0, 40, 210, 1.2, "F")

        # ── Piyasa özeti bandı ─────────────────────────────────────────────────
        pdf.set_fill_color(*_NAVY)
        pdf.rect(0, 41, 210, 20, "F")

        bist = snapshot.bist
        pills: list[tuple[str, str, str]] = []
        if bist:
            pills.append((bist.index, bist.price, bist.change or ""))
        if snapshot.macro and snapshot.macro.tickers:
            for t in snapshot.macro.tickers[:4]:
                pills.append((t.label, t.value_str, ""))

        pill_x = 12.0
        pdf.set_xy(pill_x, 47)
        for label, value, change in pills[:5]:
            # Etiket
            pdf.set_font("Helvetica", "B", 7)
            pdf.set_text_color(*_SLATE400)
            pdf.set_xy(pill_x, 44)
            pdf.cell(30, 4, label.upper()[:10])
            # Değer
            pdf.set_font("Helvetica", "B", 9)
            pdf.set_text_color(*_WHITE)
            pdf.set_xy(pill_x, 49)
            pdf.cell(30, 5, str(value)[:10])
            # Değişim
            if change:
                pdf.set_font("Helvetica", "B", 7)
                pdf.set_text_color(*_change_color(change))
                pdf.set_xy(pill_x, 55)
                pdf.cell(30, 4, change[:8])
            pill_x += 38

        # ── Rapor başlığı ──────────────────────────────────────────────────────
        pdf.set_fill_color(*_WHITE[0] - 5, *(_WHITE[1] - 5,), *(_WHITE[2] - 5,))
        pdf.set_xy(0, 62)
        pdf.set_fill_color(248, 250, 252)  # #F8FAFC
        pdf.rect(0, 62, 210, 18, "F")

        # Kenarlık çizgi
        pdf.set_draw_color(*_SLATE800)
        pdf.set_line_width(0.3)
        pdf.line(0, 80, 210, 80)

        pdf.set_xy(12, 65)
        pdf.set_font("Helvetica", "B", 14)
        pdf.set_text_color(15, 23, 42)  # #0F172A
        # Türkçe karakter güvenliği: latin-1 encode
        safe_title = title.encode("latin-1", errors="replace").decode("latin-1")
        pdf.cell(0, 10, safe_title)

        # ── Ana içerik ─────────────────────────────────────────────────────────
        pdf.set_xy(12, 85)

        # Markdown satır satır işle
        lines = body_md.split("\n")
        for raw_line in lines:
            stripped = raw_line.strip()
            if not stripped:
                pdf.ln(3)
                continue

            # ## Bölüm başlığı
            if stripped.startswith("## "):
                heading = _strip_md(stripped[3:])
                # Accent çizgi sol kenarda
                pdf.set_fill_color(*_BLUE)
                x, y = pdf.get_x(), pdf.get_y()
                pdf.rect(12, y, 2.5, 7, "F")
                pdf.set_xy(16, y)
                pdf.set_font("Helvetica", "B", 10)
                pdf.set_text_color(*_NAVY)
                safe = heading.upper().encode("latin-1", errors="replace").decode("latin-1")
                pdf.multi_cell(182, 7, safe)
                pdf.ln(2)
                continue

            # ### Alt başlık
            if stripped.startswith("### "):
                heading = _strip_md(stripped[4:])
                pdf.set_font("Helvetica", "B", 9)
                pdf.set_text_color(51, 65, 85)  # #334155
                safe = heading.encode("latin-1", errors="replace").decode("latin-1")
                pdf.set_x(12)
                pdf.multi_cell(186, 6, safe)
                pdf.ln(1)
                continue

            # Liste öğesi
            if stripped.startswith(("- ", "* ", "• ")):
                item = _strip_md(stripped[2:])
                pdf.set_font("Helvetica", "", 8.5)
                pdf.set_text_color(51, 65, 85)
                pdf.set_x(16)
                safe = ("• " + item).encode("latin-1", errors="replace").decode("latin-1")
                pdf.multi_cell(182, 5.5, safe)
                continue

            # Normal paragraf
            text = _strip_md(stripped)
            pdf.set_font("Helvetica", "", 8.5)
            pdf.set_text_color(51, 65, 85)
            pdf.set_x(12)
            safe = text.encode("latin-1", errors="replace").decode("latin-1")
            pdf.multi_cell(186, 5.5, safe)
            pdf.ln(1)

        # ── Sektör tablosu (varsa) ─────────────────────────────────────────────
        if snapshot.sector:
            sectors = sorted(
                snapshot.sector,
                key=lambda s: float(getattr(s, "change_pct", 0) or 0),
                reverse=True,
            )[:8]

            if sectors:
                # Sayfada yer var mı kontrol
                if pdf.get_y() > 230:
                    pdf.add_page()

                pdf.ln(4)
                y0 = pdf.get_y()
                pdf.set_fill_color(*_BLUE)
                pdf.rect(12, y0, 2.5, 7, "F")
                pdf.set_xy(16, y0)
                pdf.set_font("Helvetica", "B", 10)
                pdf.set_text_color(*_NAVY)
                pdf.cell(0, 7, "SEKTOR GORUNUMU")
                pdf.ln(10)

                # Tablo başlık
                pdf.set_fill_color(241, 245, 249)
                pdf.rect(12, pdf.get_y(), 80, 6, "F")
                pdf.set_font("Helvetica", "B", 7.5)
                pdf.set_text_color(100, 116, 139)
                pdf.set_x(12)
                pdf.cell(60, 6, "SEKTOR")
                pdf.cell(20, 6, "DEGISIM", align="R")
                pdf.ln(6)

                for s in sectors:
                    pct = float(getattr(s, "change_pct", 0) or 0)
                    name = getattr(s, "name", "")
                    # Kenarlık
                    pdf.set_draw_color(241, 245, 249)
                    pdf.set_line_width(0.2)
                    y_row = pdf.get_y()
                    pdf.line(12, y_row + 5.5, 92, y_row + 5.5)

                    pdf.set_font("Helvetica", "", 8)
                    pdf.set_text_color(51, 65, 85)
                    pdf.set_x(12)
                    safe_name = name.encode("latin-1", errors="replace").decode("latin-1")
                    pdf.cell(60, 5.5, safe_name[:28])

                    pdf.set_font("Helvetica", "B", 8)
                    pdf.set_text_color(*(_GREEN if pct >= 0 else _RED))
                    pdf.cell(20, 5.5, f"{pct:+.2f}%", align="R")
                    pdf.ln(5.5)

        # ── Footer ────────────────────────────────────────────────────────────
        # Her sayfanın altına — set_auto_page_break ile birlikte çalışır
        footer_y = 282
        pdf.set_fill_color(*_BLACK)
        pdf.rect(0, footer_y, 210, 15, "F")
        pdf.set_draw_color(*_SLATE800)
        pdf.line(0, footer_y, 210, footer_y)

        pdf.set_xy(12, footer_y + 4)
        pdf.set_font("Helvetica", "B", 7.5)
        pdf.set_text_color(*_SLATE400)
        pdf.cell(100, 5, "esham.pages.dev")

        pdf.set_xy(110, footer_y + 4)
        pdf.set_font("Helvetica", "I", 7)
        pdf.set_text_color(*_SLATE600)
        pdf.cell(88, 5, "Bu rapor yatirim tavsiyesi degildir.", align="R")

        pdf.output(str(pdf_path))
        log.info("PDF uretildi (fpdf2): %s", pdf_path)
        return pdf_path

    except Exception as exc:
        log.warning("PDF uretilemedi: %s", exc)
        return None
