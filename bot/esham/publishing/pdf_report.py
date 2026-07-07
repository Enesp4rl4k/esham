"""Sabah bülteni PDF üreticisi (fpdf2).

fpdf2 saf Python, sistem bağımlılığı yok — GitHub Actions ve Render'da sorunsuz çalışır.
Esham marka kimliğiyle branded, A4 formatında sabah piyasa bülteni PDF'i üretir.
Türkçe karakter desteği için projede mevcut Inter-Regular.ttf kullanılır.

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

# Font dosyaları — cards.py ile aynı assets/fonts klasörü
_FONTS_DIR = Path(__file__).resolve().parent.parent / "assets" / "fonts"
_INTER_TTF   = _FONTS_DIR / "Inter-Regular.ttf"
_OUTFIT_TTF  = _FONTS_DIR / "Outfit-Bold.ttf"

# Renk paleti (Esham dark theme)
_BLACK    = (6,   11,  24)
_NAVY     = (15,  23,  42)
_SLATE800 = (30,  41,  59)
_SLATE600 = (71,  85,  105)
_SLATE400 = (148, 163, 184)
_WHITE    = (241, 245, 249)
_BLUE     = (59,  130, 246)
_GREEN    = (34,  197, 94)
_RED      = (239, 68,  68)
_LIGHT_BG = (248, 250, 252)
_DARK_TEXT= (15,  23,  42)
_BODY_TEXT= (51,  65,  85)


def _change_color(change: str) -> tuple[int, int, int]:
    if change and change.strip().startswith("+"):
        return _GREEN
    if change and change.strip().startswith("-"):
        return _RED
    return _SLATE400


def _strip_md(text: str) -> str:
    """Markdown işaretlerini düz metne çevirir."""
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"\*(.+?)\*",     r"\1", text)
    text = re.sub(r"`(.+?)`",        r"\1", text)
    text = re.sub(r"#+\s*",          "",    text)
    text = re.sub(r"^\s*[-*•]\s+",  "• ",  text, flags=re.MULTILINE)
    return text.strip()


class _EshamPDF:
    """fpdf2 FPDF wrapper — font kayıt ve temel çizim yardımcıları."""

    def __init__(self) -> None:
        from fpdf import FPDF  # type: ignore[import]

        self.pdf = FPDF(orientation="P", unit="mm", format="A4")
        self.pdf.set_auto_page_break(auto=True, margin=18)

        # Unicode fontları kaydet
        self._has_inter  = False
        self._has_outfit = False

        if _INTER_TTF.exists():
            self.pdf.add_font("Inter",  "",  str(_INTER_TTF),  uni=True)
            self.pdf.add_font("Inter",  "B", str(_INTER_TTF),  uni=True)
            self._has_inter = True

        if _OUTFIT_TTF.exists():
            self.pdf.add_font("Outfit", "B", str(_OUTFIT_TTF), uni=True)
            self._has_outfit = True

    def _set_font(self, family: str, bold: bool, size: float) -> None:
        style = "B" if bold else ""
        if family == "outfit" and self._has_outfit:
            self.pdf.set_font("Outfit", style, size)
        elif self._has_inter:
            self.pdf.set_font("Inter", style, size)
        else:
            self.pdf.set_font("Helvetica", style, size)

    def _set_color(self, r: int, g: int, b: int) -> None:
        self.pdf.set_text_color(r, g, b)

    def _fill(self, r: int, g: int, b: int) -> None:
        self.pdf.set_fill_color(r, g, b)

    def _draw_color(self, r: int, g: int, b: int) -> None:
        self.pdf.set_draw_color(r, g, b)

    def text(self, x: float, y: float, txt: str) -> None:
        self.pdf.set_xy(x, y)
        self.pdf.cell(0, 5, txt)

    def multiline(self, x: float, y: float, w: float, txt: str, line_h: float = 5.5) -> float:
        """Çok satırlı metin yazar; son Y konumunu döner."""
        self.pdf.set_xy(x, y)
        self.pdf.multi_cell(w, line_h, txt)
        return self.pdf.get_y()

    def rect_fill(self, x: float, y: float, w: float, h: float) -> None:
        self.pdf.rect(x, y, w, h, "F")

    def line(self, x1: float, y1: float, x2: float, y2: float) -> None:
        self.pdf.line(x1, y1, x2, y2)


def generate_pdf(
    body_md: str,
    snapshot: MarketSnapshot,
    slug: str,
    title: str = "BIST & Küresel Piyasalar Sabah Raporu",
    out_dir: Path | None = None,
) -> Path | None:
    """fpdf2 ile branded PDF sabah bülteni üretir. Path döner, başarısızsa None."""
    try:
        from fpdf import FPDF  # noqa: F401 — sadece import testi
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

        e = _EshamPDF()
        p = e.pdf
        p.add_page()

        # ── Başlık bandı (koyu arkaplan) ───────────────────────────────────────
        e._fill(*_BLACK)
        e.rect_fill(0, 0, 210, 42)

        # Marka: "E" accent, "sham" beyaz
        e._set_font("outfit", True, 24)
        e._set_color(*_BLUE)
        p.set_xy(12, 9)
        p.cell(10, 10, "E")

        e._set_color(*_WHITE)
        p.set_xy(21, 9)
        p.cell(0, 10, "sham")

        # Tagline
        e._set_font("inter", False, 7)
        e._set_color(*_SLATE600)
        p.set_xy(12, 22)
        p.cell(0, 5, "YAPAY ZEKA DESTEKLI PIYASA ANALIZI")

        # Sağ: Rapor tipi + tarih
        e._set_font("inter", True, 8)
        e._set_color(*_BLUE)
        p.set_xy(130, 9)
        p.cell(68, 5, "SABAH BULTENI", align="R")

        e._set_font("outfit", True, 16)
        e._set_color(*_WHITE)
        p.set_xy(130, 16)
        p.cell(68, 8, date_str, align="R")

        e._set_font("inter", False, 8)
        e._set_color(*_SLATE400)
        p.set_xy(130, 26)
        p.cell(68, 5, f"{time_str} TR", align="R")

        # Accent çizgi
        e._fill(*_BLUE)
        e.rect_fill(0, 42, 210, 1.2)

        # ── Piyasa ticker bandı ────────────────────────────────────────────────
        e._fill(*_NAVY)
        e.rect_fill(0, 43, 210, 22)

        bist = snapshot.bist
        pills: list[tuple[str, str, str]] = []
        if bist:
            pills.append((bist.index, bist.price, bist.change or ""))
        if snapshot.macro and snapshot.macro.tickers:
            for t in snapshot.macro.tickers[:4]:
                pills.append((t.label, t.value_str, ""))

        pill_x = 12.0
        for label, value, change in pills[:5]:
            e._set_font("inter", True, 7)
            e._set_color(*_SLATE400)
            p.set_xy(pill_x, 46)
            p.cell(35, 4, label.upper()[:10])

            e._set_font("inter", True, 9)
            e._set_color(*_WHITE)
            p.set_xy(pill_x, 51)
            p.cell(35, 5, str(value)[:12])

            if change:
                e._set_font("inter", True, 7)
                e._set_color(*_change_color(change))
                p.set_xy(pill_x, 57)
                p.cell(35, 4, change[:8])

            pill_x += 38

        # ── Rapor başlığı ──────────────────────────────────────────────────────
        e._fill(*_LIGHT_BG)
        e.rect_fill(0, 65, 210, 20)

        e._draw_color(*_SLATE800)
        p.set_line_width(0.3)
        e.line(0, 85, 210, 85)

        e._set_font("outfit", True, 14)
        e._set_color(*_DARK_TEXT)
        p.set_xy(12, 68)
        p.multi_cell(186, 8, title)

        # ── Ana içerik ─────────────────────────────────────────────────────────
        p.set_xy(12, 90)

        lines = body_md.split("\n")
        for raw_line in lines:
            stripped = raw_line.strip()

            if not stripped:
                p.ln(3)
                continue

            # ## Bölüm başlığı
            if stripped.startswith("## "):
                heading = _strip_md(stripped[3:])
                y0 = p.get_y()
                if y0 > 265:
                    p.add_page()
                    y0 = p.get_y()
                e._fill(*_BLUE)
                e.rect_fill(12, y0, 2.5, 7)
                e._set_font("inter", True, 10)
                e._set_color(*_DARK_TEXT)
                p.set_xy(16, y0)
                p.multi_cell(182, 7, heading.upper())
                p.ln(2)
                continue

            # ### Alt başlık
            if stripped.startswith("### "):
                heading = _strip_md(stripped[4:])
                e._set_font("inter", True, 9)
                e._set_color(*_BODY_TEXT)
                p.set_x(12)
                p.multi_cell(186, 6, heading)
                p.ln(1)
                continue

            # Liste öğesi
            if stripped.startswith(("- ", "* ", "• ")):
                item = _strip_md(stripped[2:])
                e._set_font("inter", False, 8.5)
                e._set_color(*_BODY_TEXT)
                p.set_x(16)
                p.multi_cell(182, 5.5, "• " + item)
                continue

            # Normal paragraf
            text = _strip_md(stripped)
            if not text:
                continue
            e._set_font("inter", False, 8.5)
            e._set_color(*_BODY_TEXT)
            p.set_x(12)
            p.multi_cell(186, 5.5, text)
            p.ln(1)

        # ── Sektör tablosu (varsa) ─────────────────────────────────────────────
        if snapshot.sector:
            sectors = sorted(
                snapshot.sector,
                key=lambda s: float(getattr(s, "change_pct", 0) or 0),
                reverse=True,
            )[:8]

            if sectors:
                if p.get_y() > 240:
                    p.add_page()

                p.ln(4)
                y0 = p.get_y()
                e._fill(*_BLUE)
                e.rect_fill(12, y0, 2.5, 7)
                e._set_font("inter", True, 10)
                e._set_color(*_DARK_TEXT)
                p.set_xy(16, y0)
                p.cell(0, 7, "SEKTOR GORUNUMU")
                p.ln(10)

                # Tablo başlığı
                e._fill(241, 245, 249)
                e.rect_fill(12, p.get_y(), 82, 6)
                e._set_font("inter", True, 7.5)
                e._set_color(100, 116, 139)
                p.set_x(12)
                p.cell(62, 6, "SEKTOR")
                p.cell(20, 6, "DEGISIM", align="R")
                p.ln(6)

                for s in sectors:
                    pct = float(getattr(s, "change_pct", 0) or 0)
                    name = getattr(s, "name", "")

                    e._set_font("inter", False, 8)
                    e._set_color(*_BODY_TEXT)
                    p.set_x(12)
                    p.cell(62, 5.5, name[:30])

                    e._set_font("inter", True, 8)
                    e._set_color(*(_GREEN if pct >= 0 else _RED))
                    p.cell(20, 5.5, f"{pct:+.2f}%", align="R")
                    p.ln(5.5)

                    # ince ayırıcı
                    e._draw_color(241, 245, 249)
                    p.set_line_width(0.15)
                    e.line(12, p.get_y(), 94, p.get_y())

        # ── Footer ────────────────────────────────────────────────────────────
        # Mevcut sayfanın altına mutlak konumda çiz
        footer_y = 285
        e._fill(*_BLACK)
        e.rect_fill(0, footer_y, 210, 12)

        e._draw_color(*_SLATE800)
        p.set_line_width(0.3)
        e.line(0, footer_y, 210, footer_y)

        e._set_font("inter", True, 7.5)
        e._set_color(*_SLATE400)
        p.set_xy(12, footer_y + 3.5)
        p.cell(100, 5, "esham.pages.dev")

        e._set_font("inter", False, 7)
        e._set_color(*_SLATE600)
        p.set_xy(110, footer_y + 3.5)
        p.cell(88, 5, "Bu rapor yatirim tavsiyesi degildir.", align="R")

        p.output(str(pdf_path))
        log.info("PDF uretildi (fpdf2): %s", pdf_path)
        return pdf_path

    except Exception as exc:
        log.warning("PDF uretilemedi: %s", exc)
        return None
