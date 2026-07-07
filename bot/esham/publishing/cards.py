"""Esham marka kartı üreticisi.

Tweet görselleri VE web hero/OG görseli için TEK, marka tutarlı, gerçek veriye
dayalı görsel üretir. Pollinations gibi rastgele/yavaş/markasız üçüncü parti AI
görsel servislerinin yerini alır: tamamen yerel, deterministik, hızlı (<1sn),
ağ bağımlılığı yok (sparkline verisi zaten elde mevcut olmalı).

Tasarım dili sitenin kendisiyle birebir aynı: siyah zemin, kategori vurgu rengi
(cyan/blue/emerald/violet/amber), Outfit (başlık) + Inter (gövde) fontları.
"""
from __future__ import annotations

import tempfile
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from ..config import get_logger, settings
from ..turkish import tr_upper as _tr_upper

log = get_logger(__name__)

CARD_W, CARD_H = 1200, 630
PAD = 64

ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets" / "fonts"

# Tailwind varsayılan paleti — sitenin CSS'iyle birebir.
COLORS: dict[str, str] = {
    "black": "#000000",
    "zinc-950": "#09090b",
    "zinc-900": "#18181b",
    "zinc-800": "#27272a",
    "zinc-600": "#52525b",
    "zinc-500": "#71717a",
    "zinc-400": "#a1a1aa",
    "zinc-300": "#d4d4d8",
    "zinc-100": "#f4f4f5",
    "white": "#ffffff",
    "positive": "#34d399",  # emerald-400
    "negative": "#f87171",  # red-400
}

ACCENTS: dict[str, dict[str, str]] = {
    "cyan": {"400": "#22d3ee", "500": "#06b6d4", "900": "#164e63"},
    "blue": {"400": "#60a5fa", "500": "#3b82f6", "900": "#1e3a8a"},
    "emerald": {"400": "#34d399", "500": "#10b981", "900": "#064e3b"},
    "violet": {"400": "#a78bfa", "500": "#8b5cf6", "900": "#4c1d95"},
    "amber": {"400": "#fbbf24", "500": "#f59e0b", "900": "#78350f"},
}

CATEGORY_ACCENT: dict[str, str] = {
    "bist": "cyan",
    "global": "blue",
    "ipo": "emerald",
    "viop": "violet",
    "gundem": "amber",
    "insider": "amber",
}

CATEGORY_LABEL: dict[str, str] = {
    "bist": "BIST & SEKTÖR",
    "global": "KÜRESEL MAKRO",
    "ipo": "HALKA ARZ & KAP",
    "viop": "VİOP & TÜREV",
    "gundem": "GÜNDEM",
    "insider": "İÇERİDEN İŞLEM",
}


def _hex(c: str) -> tuple[int, int, int]:
    c = c.lstrip("#")
    return tuple(int(c[i : i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]




# Format → (genişlik, yükseklik)
FORMAT_SIZES: dict[str, tuple[int, int]] = {
    "twitter": (1200, 630),
    "square": (1080, 1080),
    "story": (1080, 1920),
}


@dataclass
class CardSpec:
    category: str  # bist | global | ipo | viop | gundem | insider | kripto | teknoloji
    kicker: str  # üst küçük etiket, örn. "XU100 ENDEKSİ"
    headline: str  # ana başlık/metin
    stat_value: str = ""  # büyük rakam, örn. "14.417,91"
    stat_change: str = ""  # örn. "-0,26%" (renkli)
    metrics: list[tuple[str, str]] = field(default_factory=list)  # küçük chip'ler
    sparkline: list[float] | None = None  # opsiyonel fiyat serisi (mini grafik)
    radar_scores: dict[str, int] = field(default_factory=dict)
    bars: list[tuple[str, float]] | None = None  # opsiyonel (etiket, %değişim) barları
    ticker: str = ""  # borsa kodu rozeti (haber/IPO şablonlarında gösterilir)
    template: str = "auto"  # auto | market | news | ipo | bist | global | viop | gundem
    format: str = "twitter"  # twitter (1200×630) | square (1080×1080) | story (1080×1920)
    # Global şablon için ticker board verileri: [(label, arrow, value), ...]
    ticker_board: list[tuple[str, str, str]] = field(default_factory=list)
    # VİOP şablonu için teminat stres seviyesi: NORMAL | YÜKSEK | KRİTİK
    stress_level: str = "NORMAL"
    # IPO iskontosu — yüksekse (>%20) büyük rozet gösterilir
    discount_pct: float = 0.0
    # IPO fon kullanım açıklaması
    fund_usage: str = ""
    # Unsplash fotoğrafı — genel haber kartları için arka plan (opsiyonel)
    # Verilirse kart arka planı bu fotoğrafla (karartılmış) döşenir.
    # KAP/analiz kartları için kullanılmaz (veri kartları fotoğrafsız kalır).
    photo_path: Path | None = None


class CardGenerator:
    def __init__(self) -> None:
        self._font_cache: dict[tuple[str, int, int], ImageFont.FreeTypeFont] = {}

    # ---- canvas boyutu yardımcısı ------------------------------------------

    @staticmethod
    def _canvas_size(fmt: str) -> tuple[int, int]:
        """Format adından (twitter/square/story) piksel boyutunu döner."""
        return FORMAT_SIZES.get(fmt, FORMAT_SIZES["twitter"])

    # ---- font yardımcıları -------------------------------------------------

    def _font(self, family: str, size: int, weight: int = 400) -> ImageFont.FreeTypeFont:
        key = (family, size, weight)
        if key in self._font_cache:
            return self._font_cache[key]
        path = ASSETS_DIR / ("Outfit-Bold.ttf" if family == "outfit" else "Inter-Regular.ttf")
        font = ImageFont.truetype(str(path), size)
        try:
            axes = font.get_variation_axes()
            if len(axes) == 1:
                font.set_variation_by_axes([weight])
            elif len(axes) == 2:  # Inter: [optical_size, weight]
                font.set_variation_by_axes([min(max(size, 14), 32), weight])
        except Exception:
            pass
        self._font_cache[key] = font
        return font

    def outfit(self, size: int) -> ImageFont.FreeTypeFont:
        return self._font("outfit", size, 700)

    def inter(self, size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
        return self._font("inter", size, 700 if bold else 400)

    @staticmethod
    def _line_h(font: ImageFont.FreeTypeFont, leading: float = 1.18) -> int:
        ascent, descent = font.getmetrics()
        return int((ascent + descent) * leading)

    # ---- metin yardımcıları -------------------------------------------------

    @staticmethod
    def _wrap(draw: ImageDraw.ImageDraw, text: str, font, max_width: int, max_lines: int) -> list[str]:
        words = text.split()
        lines: list[str] = []
        current = ""
        for word in words:
            trial = f"{current} {word}".strip()
            if draw.textbbox((0, 0), trial, font=font)[2] <= max_width:
                current = trial
            else:
                if current:
                    lines.append(current)
                    if len(lines) == max_lines:
                        current = ""
                        break
                current = word
        if current and len(lines) < max_lines:
            lines.append(current)
        
        # Sığmayan metni son satırda "…" ile kapat.
        remaining = " ".join(words)
        consumed = " ".join(lines)
        if len(consumed) < len(remaining.rstrip()) and lines:
            last = lines[-1]
            while draw.textbbox((0, 0), last + "…", font=font)[2] > max_width and len(last) > 1:
                last = last[:-1].rstrip()
            lines[-1] = last + "…"
        return lines

    # ---- arkaplan/glow ------------------------------------------------------

    def _background(
        self, accent_hex: str, w: int = CARD_W, h: int = CARD_H,
        photo_path: Path | None = None,
    ) -> Image.Image:
        """Kart arka planını üretir.

        photo_path verilirse Unsplash fotoğrafını kart boyutuna sığdırır,
        üzerine koyu gradient overlay + accent glow ekler. Bu sayede fotoğraf
        hem görünür hem de metin okunabilirliği korunur.
        Foto yoksa standart siyah + glow arka planı kullanılır.
        """
        if photo_path and photo_path.exists():
            try:
                photo = Image.open(photo_path).convert("RGB")
                # Kart boyutuna cover (kırp + genişlet)
                photo_ratio = photo.width / photo.height
                card_ratio = w / h
                if photo_ratio > card_ratio:
                    new_h = h
                    new_w = int(h * photo_ratio)
                else:
                    new_w = w
                    new_h = int(w / photo_ratio)
                photo = photo.resize((new_w, new_h), Image.LANCZOS)
                left = (new_w - w) // 2
                top = (new_h - h) // 2
                photo = photo.crop((left, top, left + w, top + h))

                # Koyu overlay — fotoğrafı okurken metin kaybolmasın
                # Sol %60 çok karanlık (metin alanı), sağ %40 biraz daha açık
                overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
                odraw = ImageDraw.Draw(overlay)
                # Gradient efekti için bölgeler
                odraw.rectangle([0, 0, int(w * 0.65), h], fill=(0, 0, 0, 185))
                odraw.rectangle([int(w * 0.65), 0, w, h], fill=(0, 0, 0, 155))
                img = photo.convert("RGBA")
                img = Image.alpha_composite(img, overlay).convert("RGB")

                # Accent glow — sağ üst köşe
                glow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
                gdraw = ImageDraw.Draw(glow)
                r, g, b = _hex(accent_hex)
                gdraw.ellipse(
                    [w - int(w * 0.52), -int(h * 0.67), w + int(w * 0.32), int(h * 0.76)],
                    fill=(r, g, b, 40),
                )
                glow = glow.filter(ImageFilter.GaussianBlur(120))
                img_rgba = img.convert("RGBA")
                img_rgba = Image.alpha_composite(img_rgba, glow)
                return img_rgba.convert("RGB")
            except Exception as exc:
                log.warning("Unsplash foto arka plana yerleştirilemedi (%s); standart arka plan.", exc)

        # Standart arka plan — siyah + accent glow
        img = Image.new("RGB", (w, h), _hex(COLORS["black"]))
        glow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        gdraw = ImageDraw.Draw(glow)
        r, g, b = _hex(accent_hex)
        gdraw.ellipse(
            [w - int(w * 0.52), -int(h * 0.67), w + int(w * 0.32), int(h * 0.76)],
            fill=(r, g, b, 70),
        )
        glow = glow.filter(ImageFilter.GaussianBlur(120))
        img.paste(glow, (0, 0), glow)
        return img

    # ---- mini sparkline -----------------------------------------------------

    def _draw_sparkline(
        self, img: Image.Image, box: tuple[int, int, int, int], values: list[float], accent_hex: str
    ) -> None:
        if len(values) < 2:
            return
        x0, y0, x1, y1 = box
        w, h = x1 - x0, y1 - y0
        lo, hi = min(values), max(values)
        span = (hi - lo) or 1.0

        def point(i: int, v: float) -> tuple[float, float]:
            x = x0 + (i / (len(values) - 1)) * w
            y = y1 - ((v - lo) / span) * h
            return x, y

        pts = [point(i, v) for i, v in enumerate(values)]

        overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
        odraw = ImageDraw.Draw(overlay)
        r, g, b = _hex(accent_hex)
        fill_poly = [*pts, (x1, y1), (x0, y1)]
        odraw.polygon(fill_poly, fill=(r, g, b, 40))
        odraw.line(pts, fill=(r, g, b, 255), width=4, joint="curve")
        img.alpha_composite(overlay.convert("RGBA")) if img.mode == "RGBA" else img.paste(
            overlay, (0, 0), overlay
        )

    # ---- sol kolon (kicker/stat/headline/metrics) ----------------------------

    def _draw_left_column(
        self,
        draw: ImageDraw.ImageDraw,
        spec: CardSpec,
        start_y: int,
        left_w: int,
        content_bottom: int,
        *,
        measure_only: bool = False,
    ) -> int:
        cursor_y = start_y

        def text(xy, s, font, fill):
            if not measure_only:
                draw.text(xy, s, font=font, fill=fill)

        def rrect(box, **kw):
            if not measure_only:
                draw.rounded_rectangle(box, **kw)

        if spec.kicker:
            kicker_font = self.inter(22, bold=True)
            text((PAD, cursor_y), _tr_upper(spec.kicker), kicker_font, _hex(COLORS["zinc-400"]))
            cursor_y += self._line_h(kicker_font) + 10

        if spec.stat_value:
            stat_font = self.outfit(84)
            text((PAD, cursor_y), spec.stat_value, stat_font, _hex(COLORS["white"]))
            cursor_y += self._line_h(stat_font) + 4
            if spec.stat_change:
                is_positive = spec.stat_change.strip().startswith("+")
                change_color = COLORS["positive"] if is_positive else COLORS["negative"]
                change_font = self.inter(32, bold=True)
                text((PAD, cursor_y), spec.stat_change, change_font, _hex(change_color))
                cursor_y += self._line_h(change_font) + 18
            else:
                cursor_y += 16

        if spec.headline:
            headline_font = self.outfit(34 if spec.stat_value else 50)
            line_h = self._line_h(headline_font)
            desired_lines = 3 if spec.stat_value else 4
            # Kalan dikey alana göre kaç satır GERÇEKTEN sığar hesapla; _wrap'a bunu
            # ver ki taşan satır sessizce kaybolmasın, düzgün "…" ile ayarlansın.
            available = content_bottom - 8 - cursor_y
            fit_lines = max(1, min(desired_lines, available // line_h))
            lines = self._wrap(draw, spec.headline, headline_font, left_w, fit_lines)
            for line in lines:
                text((PAD, cursor_y), line, headline_font, _hex(COLORS["zinc-100"]))
                cursor_y += line_h

        if spec.metrics:
            cursor_y += 22
            chip_x = PAD
            chip_font = self.inter(21, bold=True)
            chip_h = 46
            for label, value in spec.metrics:
                # AI bazen kısa bir oran ("12,3") yerine tam bir cümle döndürebilir
                # (ör. bir varsayımı açıklayan metin) — chip bunun için tasarlanmadı,
                # kırpmazsak kart kenarından taşar. Değeri karakter bazında sınırla.
                value_str = str(value)
                if len(value_str) > 48:
                    value_str = value_str[:47].rsplit(" ", 1)[0].rstrip(",.;:") + "…"
                item = f"{label}: {value_str}"
                tw = draw.textbbox((0, 0), item, font=chip_font)[2]
                # Tek başına satırı bile aşan bir chip varsa (ilk chip dahil) yine de
                # satır genişliğini kesin olarak aşmasın diye ikinci bir güvenlik payı.
                max_w = left_w - 8
                if tw > max_w:
                    while tw > max_w and len(value_str) > 4:
                        value_str = value_str[:-2].rstrip(",.;: ") + "…"
                        item = f"{label}: {value_str}"
                        tw = draw.textbbox((0, 0), item, font=chip_font)[2]
                if chip_x != PAD and chip_x + tw + 36 > left_w + PAD:
                    chip_x = PAD
                    cursor_y += chip_h + 12
                if cursor_y + chip_h > content_bottom:
                    break
                rrect(
                    [chip_x, cursor_y, chip_x + tw + 32, cursor_y + chip_h],
                    radius=10,
                    fill=_hex(COLORS["zinc-900"]),
                    outline=_hex(COLORS["zinc-800"]),
                    width=1,
                )
                text_h = draw.textbbox((0, 0), item, font=chip_font)[3]
                text(
                    (chip_x + 16, cursor_y + (chip_h - text_h) // 2 - 2),
                    item,
                    chip_font,
                    _hex(COLORS["zinc-100"]),
                )
                chip_x += tw + 32 + 16
            cursor_y += chip_h

        return cursor_y

    # ---- paylaşılan üst/alt bölümler ------------------------------------------

    def _draw_wordmark(self, draw: ImageDraw.ImageDraw, accent_hex: str) -> None:
        accent_part = settings.brand_name_accent
        rest_part = settings.brand_name_rest
        tagline = settings.brand_tagline

        word_font = self.outfit(42)
        draw.text((PAD, PAD - 6), accent_part, font=word_font, fill=_hex(accent_hex))
        accent_w = draw.textbbox((0, 0), accent_part, font=word_font)[2]
        draw.text((PAD + accent_w, PAD - 6), rest_part, font=word_font, fill=_hex(COLORS["white"]))
        draw.text(
            (PAD + 2, PAD + 46),
            tagline,
            font=self.inter(15, bold=True),
            fill=_hex(COLORS["zinc-500"]),
        )

    def _draw_badge(
        self, draw: ImageDraw.ImageDraw, text: str, accent_hex: str, *, filled: bool = False, card_w: int = CARD_W
    ) -> None:
        """Sağ üstte kategori rozeti. `filled=True` haber şablonunda daha vurgulu/dolu."""
        badge_font = self.inter(20, bold=True)
        bw = draw.textbbox((0, 0), text, font=badge_font)[2]
        bx1 = card_w - PAD
        bx0 = bx1 - bw - 40
        by0, by1 = PAD - 4, PAD + 40
        if filled:
            draw.rounded_rectangle([bx0, by0, bx1, by1], radius=18, fill=_hex(accent_hex))
            draw.text((bx0 + 20, by0 + 8), text, font=badge_font, fill=_hex(COLORS["black"]))
        else:
            draw.rounded_rectangle([bx0, by0, bx1, by1], radius=18, outline=_hex(accent_hex), width=2)
            draw.text((bx0 + 20, by0 + 8), text, font=badge_font, fill=_hex(accent_hex))

    def _draw_footer(self, draw: ImageDraw.ImageDraw, content_bottom: int, card_w: int = CARD_W) -> None:
        draw.line([(PAD, content_bottom), (card_w - PAD, content_bottom)], fill=_hex(COLORS["zinc-800"]), width=1)
        draw.text(
            (PAD, content_bottom + 24), settings.display_domain, font=self.inter(22, bold=True), fill=_hex(COLORS["zinc-300"])
        )
        disclaimer = "Yatırım tavsiyesi değildir"
        dw = draw.textbbox((0, 0), disclaimer, font=self.inter(18))[2]
        draw.text(
            (card_w - PAD - dw, content_bottom + 26),
            disclaimer,
            font=self.inter(18),
            fill=_hex(COLORS["zinc-600"]),
        )

    def _save(self, img: Image.Image, out_path: Path | None) -> Path:
        out_path = out_path or Path(tempfile.gettempdir()) / f"esham_card_{uuid.uuid4().hex[:10]}.png"
        img.convert("RGB").save(out_path, "PNG", optimize=True)
        return out_path

    # ---- ana render (dispatch) ------------------------------------------------

    def render(self, spec: CardSpec, out_path: Path | None = None) -> Path:
        """Kategori/format kombinasyonuna göre şablona yönlendirir.

        Kategori bazlı özel şablonlar:
          bist    → _render_bist   (endeks stat + sparkline, sol/sağ layout)
          global  → _render_global (başlık sol + ticker board sağ)
          ipo     → _render_ipo    (fact-sheet ızgarası + iskonto rozeti)
          viop    → _render_viop   (stres bandı + teminat metrikleri)
          gundem  → _render_gundem (flash rozet + dev başlık + sol çubuk)

        Geriye kalan / legacy uyumluluk:
          template="market" → _render_market
          template="news"   → _render_news
        """
        template = spec.template
        # Kategori bazlı otomatik yönlendirme
        if template == "auto":
            dispatch = {
                "bist": "bist",
                "global": "global",
                "ipo": "ipo",
                "viop": "viop",
                "gundem": "gundem",
            }
            template = dispatch.get(spec.category, "news")

        if template == "bist":
            return self._render_bist(spec, out_path)
        if template == "global":
            return self._render_global(spec, out_path)
        if template == "ipo":
            return self._render_ipo(spec, out_path)
        if template == "viop":
            return self._render_viop(spec, out_path)
        if template == "gundem":
            return self._render_gundem(spec, out_path)
        if template == "news":
            return self._render_news(spec, out_path)
        # fallback
        return self._render_market(spec, out_path)

    # ---- piyasa şablonu (BIST/VİOP/sektör) — legacy uyumluluk ----------------

    def _render_market(self, spec: CardSpec, out_path: Path | None = None) -> Path:
        accent = CATEGORY_ACCENT.get(spec.category, "cyan")
        accent_hex = ACCENTS[accent]["400"]
        w, h = self._canvas_size(spec.format)

        img = self._background(accent_hex, w, h).convert("RGBA")
        draw = ImageDraw.Draw(img)

        self._draw_wordmark(draw, accent_hex)
        badge_text = CATEGORY_LABEL.get(spec.category, spec.category.upper())
        self._draw_badge(draw, badge_text, accent_hex)

        content_top = 184
        content_bottom = h - 84
        has_spark = bool(spec.sparkline and len(spec.sparkline) >= 2)
        has_bars = bool(spec.bars)

        left_w = int(w * 0.5) if (has_spark or has_bars) else (w - 2 * PAD)

        # Sparkline/bar yoksa içerik bloğunu dikey ortala — üstte yığılıp altta
        # boş kalmasın.
        start_y = content_top
        if not (has_spark or has_bars):
            measured_end = self._draw_left_column(
                draw, spec, content_top, left_w, content_bottom, measure_only=True
            )
            block_h = measured_end - content_top
            slack = max(0, (content_bottom - content_top - block_h) // 2 - 10)
            start_y = content_top + slack

        self._draw_left_column(draw, spec, start_y, left_w, content_bottom)

        if has_spark:
            spark_w = int(w * 0.35)
            box = (w - PAD - spark_w, content_top + 30, w - PAD, content_top + int(h * 0.41))
            self._draw_sparkline(img, box, spec.sparkline, accent_hex)  # type: ignore[arg-type]
        elif has_bars:
            bar_w = int(w * 0.37)
            self._draw_bars(draw, spec.bars, (w - PAD - bar_w, content_top, w - PAD, content_bottom))

        self._draw_footer(draw, content_bottom, w)
        return self._save(img, out_path)

    # ---- haber şablonu — çarpıcı, tam-ekran başlık ----------------------------

    def _render_news(self, spec: CardSpec, out_path: Path | None = None) -> Path:
        """Insider/gündem/genel KAP haberleri için: dev başlık, dolu (filled)
        kategori rozeti, sol kenarda kalın vurgu çubuğu — IPO'nun 'fact-sheet'
        hissinden kasıtlı olarak farklı, editoryal/"flash" bir görünüm."""
        accent = CATEGORY_ACCENT.get(spec.category, "amber")
        accent_hex = ACCENTS[accent]["400"]

        w, h = self._canvas_size(spec.format)
        img = self._background(accent_hex, w, h, photo_path=spec.photo_path).convert("RGBA")
        draw = ImageDraw.Draw(img)

        # Sol kenar vurgu çubuğu — haber şablonuna özgü kimlik.
        draw.rectangle([0, 0, 10, h], fill=_hex(accent_hex))

        self._draw_wordmark(draw, accent_hex)
        badge_text = CATEGORY_LABEL.get(spec.category, spec.category.upper())
        self._draw_badge(draw, badge_text, accent_hex, filled=True, card_w=w)

        has_spark = bool(spec.sparkline and len(spec.sparkline) >= 2)
        content_top = 200
        content_bottom = h - 84
        left_w = int(w * 0.5) if has_spark else (w - 2 * PAD - 20)  # sol çubuk payı

        cursor_y = content_top
        if spec.ticker:
            ticker_font = self.inter(24, bold=True)
            ttext = f"${_tr_upper(spec.ticker)}"
            tw = draw.textbbox((0, 0), ttext, font=ticker_font)[2]
            draw.rounded_rectangle(
                [PAD + 12, cursor_y, PAD + 12 + tw + 28, cursor_y + 46],
                radius=10, outline=_hex(accent_hex), width=2,
            )
            draw.text((PAD + 12 + 14, cursor_y + 10), ttext, font=ticker_font, fill=_hex(accent_hex))
            cursor_y += 46 + 22

        # Square/story formatlarda font büyüsün
        hl_size = 54 if spec.format == "twitter" else 62
        headline_font = self.outfit(hl_size)
        line_h = self._line_h(headline_font)
        available = content_bottom - 8 - cursor_y
        fit_lines = max(1, min(4, available // line_h))
        lines = self._wrap(draw, spec.headline, headline_font, left_w - 12, fit_lines)

        # Dikey ortala.
        block_h = len(lines) * line_h
        slack = max(0, (content_bottom - cursor_y - block_h) // 2 - 6)
        y = cursor_y + slack
        for line in lines:
            draw.text((PAD + 12, y), line, font=headline_font, fill=_hex(COLORS["zinc-100"]))
            y += line_h

        if has_spark:
            if spec.format == "square":
                spark_top = content_bottom - 280
                self._draw_sparkline(img, (PAD + 12, spark_top, w - PAD, content_bottom - 8), spec.sparkline, accent_hex)
            else:
                spark_w = int(w * 0.35)
                box = (w - PAD - spark_w, content_top + 30, w - PAD, content_top + int(h * 0.41))
                self._draw_sparkline(img, box, spec.sparkline, accent_hex)

        self._draw_footer(draw, content_bottom, w)
        return self._save(img, out_path)

    # ---- halka arz şablonu — fact-sheet/istatistik ızgarası -------------------

    def _render_ipo(self, spec: CardSpec, out_path: Path | None = None) -> Path:
        """Halka arz analizleri için: şirket adı + ticker rozeti, ardından
        gerçek bir istatistik ızgarası (büyük rakam + küçük etiket, akan chip
        DEĞİL) — finans uygulaması tarzı, haber şablonundan kasıtlı olarak
        çok farklı bir 'veri föyü' hissi."""
        accent = CATEGORY_ACCENT.get("ipo", "emerald")
        accent_hex = ACCENTS[accent]["400"]

        w, h = self._canvas_size(spec.format)
        img = self._background(accent_hex, w, h).convert("RGBA")
        draw = ImageDraw.Draw(img)

        self._draw_wordmark(draw, accent_hex)
        self._draw_badge(draw, CATEGORY_LABEL["ipo"], accent_hex, card_w=w)

        content_top = 190
        content_bottom = h - 84
        cursor_y = content_top

        kicker_font = self.inter(22, bold=True)
        draw.text((PAD, cursor_y), _tr_upper(spec.kicker or "Halka Arz Analizi"), font=kicker_font, fill=_hex(COLORS["zinc-400"]))
        cursor_y += self._line_h(kicker_font) + 8

        # Şirket adı + ticker rozeti aynı satırda.
        name_font = self.outfit(40)
        max_name_w = w - 2 * PAD - 180
        name_lines = self._wrap(draw, spec.headline, name_font, max_name_w, 1)
        company_name = name_lines[0] if name_lines else spec.headline
        draw.text((PAD, cursor_y), company_name, font=name_font, fill=_hex(COLORS["white"]))
        name_w = draw.textbbox((0, 0), company_name, font=name_font)[2]
        name_h = self._line_h(name_font)

        if spec.ticker:
            ticker_font = self.inter(22, bold=True)
            ttext = _tr_upper(spec.ticker)
            tw = draw.textbbox((0, 0), ttext, font=ticker_font)[2]
            tx0 = PAD + name_w + 20
            ty0 = cursor_y + (name_h - 40) // 2
            if tx0 + tw + 32 <= w - PAD:
                draw.rounded_rectangle([tx0, ty0, tx0 + tw + 32, ty0 + 40], radius=10, fill=_hex(accent_hex))
                draw.text((tx0 + 16, ty0 + 8), ttext, font=ticker_font, fill=_hex(COLORS["black"]))
        cursor_y += name_h + 28

        # --- İstatistik ızgarası + büyük iskonto rozeti ---
        # IPO iskonto yüksekse sağ kenarda büyük rozet
        if spec.discount_pct > 20:
            disc_font = self.outfit(36)
            disc_text = f"⬆%{spec.discount_pct:.0f} İSKONTO"
            dw = draw.textbbox((0, 0), disc_text, font=disc_font)[2]
            dx0 = w - PAD - dw - 24
            dy0 = content_top - 10
            draw.rounded_rectangle([dx0 - 8, dy0, dx0 + dw + 16, dy0 + 56], radius=12, fill=_hex(ACCENTS["emerald"]["900"]), outline=_hex(ACCENTS["emerald"]["400"]), width=2)
            draw.text((dx0, dy0 + 10), disc_text, font=disc_font, fill=_hex(ACCENTS["emerald"]["400"]))

        stats = list(spec.metrics)[:4]
        if stats:
            grid_top = cursor_y
            grid_bottom = content_bottom - 8
            cols = 4 if len(stats) >= 3 else len(stats)
            cols = max(1, min(cols, 4))
            cell_w = (w - 2 * PAD) // cols
            label_font = self.inter(17, bold=True)
            value_font = self.outfit(30)
            for i, (label, value) in enumerate(stats):
                col = i % cols
                row = i // cols
                cx = PAD + col * cell_w
                cy = grid_top + row * 110
                if cy + 90 > grid_bottom:
                    break
                draw.text((cx, cy), _tr_upper(label), font=label_font, fill=_hex(COLORS["zinc-500"]))
                value_str = str(value)
                max_vw = cell_w - 24
                vw = draw.textbbox((0, 0), value_str, font=value_font)[2]
                while vw > max_vw and len(value_str) > 4:
                    value_str = value_str[:-2].rstrip(",.;: ") + "…"
                    vw = draw.textbbox((0, 0), value_str, font=value_font)[2]
                draw.text((cx, cy + 26), value_str, font=value_font, fill=_hex(COLORS["zinc-100"]))
                if col < cols - 1 and i + 1 < len(stats):
                    draw.line([(cx + cell_w - 16, cy), (cx + cell_w - 16, cy + 76)], fill=_hex(COLORS["zinc-800"]), width=1)
            rows_used = (len(stats) + cols - 1) // cols
            cursor_y = grid_top + rows_used * 110 + 10
        else:
            cursor_y += 10

        # Fon kullanımı tek satır
        if spec.fund_usage and cursor_y + 40 < content_bottom - 8:
            fu_font = self.inter(18)
            fu_text = spec.fund_usage
            fw = draw.textbbox((0, 0), fu_text, font=fu_font)[2]
            max_fw = w - 2 * PAD - 16
            while fw > max_fw and len(fu_text) > 8:
                fu_text = fu_text[:-2].rstrip(" ,;") + "…"
                fw = draw.textbbox((0, 0), fu_text, font=fu_font)[2]
            draw.text((PAD, cursor_y + 8), fu_text, font=fu_font, fill=_hex(COLORS["zinc-500"]))

        self._draw_footer(draw, content_bottom, w)
        return self._save(img, out_path)

    def _draw_bars(
        self, draw: ImageDraw.ImageDraw, bars: list[tuple[str, float]], box: tuple[int, int, int, int]
    ) -> None:
        x0, y0, x1, y1 = box
        n = min(len(bars), 6)
        row_h = (y1 - y0) / n
        max_abs = max((abs(v) for _, v in bars[:n]), default=1.0) or 1.0
        label_font = self.inter(20, bold=True)
        value_font = self.inter(20, bold=True)
        bar_max_w = 170

        for i, (label, value) in enumerate(bars[:n]):
            y = y0 + i * row_h + row_h / 2
            draw.text((x0, y - 12), label, font=label_font, fill=_hex(COLORS["zinc-300"]))
            bar_w = int((abs(value) / max_abs) * bar_max_w)
            color = COLORS["positive"] if value >= 0 else COLORS["negative"]
            bar_x0 = x1 - bar_max_w - 95
            draw.rounded_rectangle(
                [bar_x0, y - 10, bar_x0 + max(bar_w, 4), y + 10], radius=5, fill=_hex(color)
            )
            value_str = f"{'+' if value >= 0 else ''}{value:.2f}%"
            draw.text((x1 - 80, y - 12), value_str, font=value_font, fill=_hex(color))

    def _draw_radar_chart(self, img: Image.Image, box: tuple[int, int, int, int], scores: dict[str, int], accent_hex: str) -> None:
        import math
        x0, y0, x1, y1 = box
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        r = min(x1 - x0, y1 - y0) / 2 * 0.7  # Etiketler için pay bırak

        n = len(scores)
        if n < 3: return

        draw = ImageDraw.Draw(img)
        labels = list(scores.keys())
        values = list(scores.values())

        # 1. Arka plan ağlarını çiz (5 seviye)
        levels = 5
        for level in range(1, levels + 1):
            pts = []
            for i in range(n):
                angle = -math.pi / 2 + (2 * math.pi * i / n)
                rad = r * (level / levels)
                pts.append((cx + rad * math.cos(angle), cy + rad * math.sin(angle)))
            draw.polygon(pts, outline=(255, 255, 255, 30), width=1)

        # 2. Eksen çizgilerini ve etiketleri çiz
        label_font = self.inter(22, bold=True)
        for i in range(n):
            angle = -math.pi / 2 + (2 * math.pi * i / n)
            px = cx + r * math.cos(angle)
            py = cy + r * math.sin(angle)
            draw.line([(cx, cy), (px, py)], fill=(255, 255, 255, 30), width=1)

            # Etiketler
            label = labels[i]
            lx = cx + (r + 40) * math.cos(angle)
            ly = cy + (r + 40) * math.sin(angle)
            tw, th = draw.textbbox((0, 0), label, font=label_font)[2:4]
            draw.text((lx - tw / 2, ly - th / 2), label, font=label_font, fill=_hex(COLORS["zinc-400"]))

        # 3. Veri poligonunu çiz (Saydam overlay ile)
        data_pts = []
        for i in range(n):
            angle = -math.pi / 2 + (2 * math.pi * i / n)
            val = min(10, max(0, values[i]))
            rad = r * (val / 10.0)
            data_pts.append((cx + rad * math.cos(angle), cy + rad * math.sin(angle)))

        overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
        odraw = ImageDraw.Draw(overlay)
        r_c, g_c, b_c = _hex(accent_hex)
        odraw.polygon(data_pts, fill=(r_c, g_c, b_c, 80), outline=(r_c, g_c, b_c, 255), width=3)
        img.alpha_composite(overlay)

    # ═══════════════════════════════════════════════════════════════════════════
    # 5 KATEGORİ ŞABLONU
    # ═══════════════════════════════════════════════════════════════════════════

    # ---- 1. BIST şablonu -------------------------------------------------------

    def _render_bist(self, spec: CardSpec, out_path: Path | None = None) -> Path:
        """BIST & Sektör: endeks stat (sol) + sparkline veya bar grafik (sağ).
        Square formatta metin büyür, sparkline daha yüksek alanda gösterilir."""
        accent_hex = ACCENTS["cyan"]["400"]
        w, h = self._canvas_size(spec.format)
        is_square = spec.format == "square"

        img = self._background(accent_hex, w, h).convert("RGBA")
        draw = ImageDraw.Draw(img)

        self._draw_wordmark(draw, accent_hex)
        self._draw_badge(draw, CATEGORY_LABEL["bist"], accent_hex, card_w=w)

        content_top = 184
        content_bottom = h - 84
        has_spark = bool(spec.sparkline and len(spec.sparkline) >= 2)
        has_bars = bool(spec.bars)
        has_radar = bool(spec.radar_scores)

        # Square: sol kolon daha geniş, grafik alt kısımda
        if is_square:
            left_w = w - 2 * PAD
            # Stat değerleri — büyük font
            cursor_y = content_top
            if spec.kicker:
                kf = self.inter(24, bold=True)
                draw.text((PAD, cursor_y), _tr_upper(spec.kicker), font=kf, fill=_hex(COLORS["zinc-400"]))
                cursor_y += self._line_h(kf) + 8
            if spec.stat_value:
                sf = self.outfit(96)
                draw.text((PAD, cursor_y), spec.stat_value, font=sf, fill=_hex(COLORS["white"]))
                cursor_y += self._line_h(sf) + 4
                if spec.stat_change:
                    is_pos = spec.stat_change.strip().startswith("+")
                    cf = self.inter(36, bold=True)
                    draw.text((PAD, cursor_y), spec.stat_change, font=cf,
                              fill=_hex(COLORS["positive"] if is_pos else COLORS["negative"]))
                    cursor_y += self._line_h(cf) + 20
            if spec.headline:
                hf = self.outfit(44)
                lh = self._line_h(hf)
                spark_reserve = 320 if (has_spark or has_radar) else 0
                avail = content_bottom - spark_reserve - 8 - cursor_y
                fit = max(1, min(3, avail // lh))
                lines = self._wrap(draw, spec.headline, hf, left_w, fit)
                for line in lines:
                    draw.text((PAD, cursor_y), line, font=hf, fill=_hex(COLORS["zinc-100"]))
                    cursor_y += lh
            if has_spark:
                spark_top = content_bottom - 300
                self._draw_sparkline(img, (PAD, spark_top, w - PAD, content_bottom - 8), spec.sparkline, accent_hex)  # type: ignore[arg-type]
            elif has_radar:
                radar_top = content_bottom - 320
                self._draw_radar_chart(img, (PAD, radar_top, w - PAD, content_bottom - 8), spec.radar_scores, accent_hex)
            elif has_bars:
                bar_top = max(cursor_y + 20, content_bottom - 280)
                self._draw_bars(draw, spec.bars, (PAD, bar_top, w - PAD, content_bottom - 8))
        else:
            # Twitter: klasik sol/sağ layout
            left_w = int(w * 0.5) if (has_spark or has_bars or has_radar) else (w - 2 * PAD)
            start_y = content_top
            if not (has_spark or has_bars or has_radar):
                measured = self._draw_left_column(draw, spec, content_top, left_w, content_bottom, measure_only=True)
                slack = max(0, (content_bottom - content_top - (measured - content_top)) // 2 - 10)
                start_y = content_top + slack
            self._draw_left_column(draw, spec, start_y, left_w, content_bottom)
            if has_spark:
                spark_w = int(w * 0.35)
                box = (w - PAD - spark_w, content_top + 30, w - PAD, content_top + int(h * 0.41))
                self._draw_sparkline(img, box, spec.sparkline, accent_hex)  # type: ignore[arg-type]
            elif has_radar:
                radar_w = int(w * 0.35)
                self._draw_radar_chart(img, (w - PAD - radar_w, content_top, w - PAD, content_bottom), spec.radar_scores, accent_hex)
            elif has_bars:
                bar_w = int(w * 0.37)
                self._draw_bars(draw, spec.bars, (w - PAD - bar_w, content_top, w - PAD, content_bottom))

        self._draw_footer(draw, content_bottom, w)
        return self._save(img, out_path)

    # ---- 2. Global şablonu -----------------------------------------------------

    def _render_global(self, spec: CardSpec, out_path: Path | None = None) -> Path:
        """Küresel Makro: sol başlık/kicker + sağda ticker board (label ↑↓ değer).
        Ticker board arka planı zinc-900/50 ile ayrılır."""
        accent_hex = ACCENTS["blue"]["400"]
        w, h = self._canvas_size(spec.format)
        is_square = spec.format == "square"

        img = self._background(accent_hex, w, h).convert("RGBA")
        draw = ImageDraw.Draw(img)

        self._draw_wordmark(draw, accent_hex)
        self._draw_badge(draw, CATEGORY_LABEL["global"], accent_hex, card_w=w)

        content_top = 184
        content_bottom = h - 84

        board = spec.ticker_board  # [(label, arrow, value), ...]
        has_board = bool(board)
        has_spark = bool(spec.sparkline and len(spec.sparkline) >= 2)

        if is_square:
            # Square: başlık üstte, ticker board altta
            left_w = w - 2 * PAD
            cursor_y = content_top
            if spec.kicker:
                kf = self.inter(22, bold=True)
                draw.text((PAD, cursor_y), _tr_upper(spec.kicker), font=kf, fill=_hex(COLORS["zinc-400"]))
                cursor_y += self._line_h(kf) + 10
            hf = self.outfit(52)
            lh = self._line_h(hf)
            
            reserve = 0
            if has_board:
                reserve = len(board) * 68 + 40
            elif has_spark:
                reserve = 300
                
            avail = content_bottom - reserve - 8 - cursor_y
            fit = max(1, min(3, avail // lh))
            lines = self._wrap(draw, spec.headline, hf, left_w, fit)
            for line in lines:
                draw.text((PAD, cursor_y), line, font=hf, fill=_hex(COLORS["zinc-100"]))
                cursor_y += lh
                
            if has_board:
                board_top = max(cursor_y + 20, content_bottom - len(board) * 68 - 20)
                self._draw_ticker_board(draw, board, (PAD, board_top, w - PAD, content_bottom - 8), w)
            elif has_spark:
                spark_top = content_bottom - 280
                self._draw_sparkline(img, (PAD, spark_top, w - PAD, content_bottom - 8), spec.sparkline, accent_hex)
        else:
            # Twitter: sol başlık, sağ ticker board veya sparkline
            split_x = w // 2 if (has_board or has_spark) else w - 2 * PAD
            left_w = split_x - PAD - 16

            cursor_y = content_top
            if spec.kicker:
                kf = self.inter(22, bold=True)
                draw.text((PAD, cursor_y), _tr_upper(spec.kicker), font=kf, fill=_hex(COLORS["zinc-400"]))
                cursor_y += self._line_h(kf) + 10

            hf = self.outfit(44)
            lh = self._line_h(hf)
            avail = content_bottom - 8 - cursor_y
            fit = max(1, min(3, avail // lh))
            lines = self._wrap(draw, spec.headline, hf, left_w, fit)
            block_h = len(lines) * lh
            slack = max(0, (content_bottom - cursor_y - block_h) // 2 - 6)
            y = cursor_y + slack
            for line in lines:
                draw.text((PAD, y), line, font=hf, fill=_hex(COLORS["zinc-100"]))
                y += lh

            if has_board:
                # Sağ sütun arka planı
                board_x0 = split_x + 8
                draw.rounded_rectangle(
                    [board_x0, content_top - 8, w - PAD + 8, content_bottom + 4],
                    radius=12,
                    fill=(*_hex(COLORS["zinc-900"]), 180),  # type: ignore[arg-type]
                )
                self._draw_ticker_board(draw, board, (board_x0 + 16, content_top, w - PAD, content_bottom), w)
            elif has_spark:
                spark_w = int(w * 0.35)
                box = (w - PAD - spark_w, content_top + 30, w - PAD, content_top + int(h * 0.41))
                self._draw_sparkline(img, box, spec.sparkline, accent_hex)

        self._draw_footer(draw, content_bottom, w)
        return self._save(img, out_path)

    def _draw_ticker_board(
        self,
        draw: ImageDraw.ImageDraw,
        board: list[tuple[str, str, str]],
        box: tuple[int, int, int, int],
        card_w: int,
    ) -> None:
        """Ticker board: her satır 'LABEL  ↑  4.52%' biçiminde, ok rengi emerald/kırmızı."""
        x0, y0, x1, y1 = box
        row_h = 58
        label_font = self.inter(20, bold=True)
        value_font = self.inter(22, bold=True)
        for i, (label, arrow, value) in enumerate(board):
            y = y0 + i * row_h
            if y + row_h > y1:
                break
            is_up = arrow in ("↑", "▲", "+")
            arrow_color = COLORS["positive"] if is_up else COLORS["negative"]
            draw.text((x0, y + 10), label, font=label_font, fill=_hex(COLORS["zinc-400"]))
            arrow_sym = "↑" if is_up else "↓"
            aw = draw.textbbox((0, 0), arrow_sym, font=value_font)[2]
            vw = draw.textbbox((0, 0), value, font=value_font)[2]
            # Sağa hizalı
            draw.text((x1 - vw, y + 8), value, font=value_font, fill=_hex(arrow_color))
            draw.text((x1 - vw - aw - 6, y + 8), arrow_sym, font=value_font, fill=_hex(arrow_color))
            # Satır ayırıcı
            if i < len(board) - 1:
                draw.line([(x0, y + row_h - 2), (x1, y + row_h - 2)], fill=_hex(COLORS["zinc-800"]), width=1)

    # ---- 3. IPO şablonu (yeni, geliştirilmiş) - _render_ipo zaten var ----------
    # _render_ipo artık discount_pct ve fund_usage destekliyor, ayrı metod gerekmez.

    # ---- 4. VIOP şablonu -------------------------------------------------------

    def _render_viop(self, spec: CardSpec, out_path: Path | None = None) -> Path:
        """VİOP & Türev: teminat stres bandı + margin metrikleri + endeks/vadeli fiyat."""
        accent_hex = ACCENTS["violet"]["400"]
        w, h = self._canvas_size(spec.format)

        # Stres seviyesine göre renk
        stress_colors = {
            "NORMAL": ACCENTS["emerald"]["400"],
            "YÜKSEK": ACCENTS["amber"]["400"],
            "KRİTİK": ACCENTS["cyan"]["400"],  # kırmızı — negative rengi kullanılır
        }
        stress_accent = stress_colors.get(spec.stress_level, ACCENTS["emerald"]["400"])
        if spec.stress_level == "KRİTİK":
            stress_accent = COLORS["negative"]

        img = self._background(accent_hex, w, h).convert("RGBA")
        draw = ImageDraw.Draw(img)

        self._draw_wordmark(draw, accent_hex)
        self._draw_badge(draw, CATEGORY_LABEL["viop"], accent_hex, card_w=w)

        content_top = 184
        content_bottom = h - 84
        cursor_y = content_top

        # Kicker
        if spec.kicker:
            kf = self.inter(22, bold=True)
            draw.text((PAD, cursor_y), _tr_upper(spec.kicker), font=kf, fill=_hex(COLORS["zinc-400"]))
            cursor_y += self._line_h(kf) + 12

        # Stres etiketi + bandı
        stress_label = f"TEMİNAT STRESİ"
        slabel_font = self.inter(18, bold=True)
        draw.text((PAD, cursor_y), stress_label, font=slabel_font, fill=_hex(COLORS["zinc-500"]))
        cursor_y += self._line_h(slabel_font) + 6

        # Stres seviye rozeti
        level_font = self.outfit(28)
        lw = draw.textbbox((0, 0), spec.stress_level, font=level_font)[2]
        draw.rounded_rectangle([PAD, cursor_y, PAD + lw + 28, cursor_y + 46], radius=10, fill=_hex(stress_accent))
        draw.text((PAD + 14, cursor_y + 8), spec.stress_level, font=level_font, fill=_hex(COLORS["black"]))
        cursor_y += 46 + 16

        # Stres bandı — doluluk oranı (margin_call_pct / 2.0 normalize)
        band_x0, band_x1 = PAD, w - PAD
        band_y0, band_y1 = cursor_y, cursor_y + 28
        band_w = band_x1 - band_x0
        # spec.stat_value'yu doluluk yüzdesi olarak kullan (0-100)
        try:
            fill_pct = min(100.0, float(spec.stat_value.replace("%", "").replace(",", ".")) * 50)
        except (ValueError, AttributeError):
            fill_pct = 30.0
        fill_w = int(band_w * fill_pct / 100)
        draw.rounded_rectangle([band_x0, band_y0, band_x1, band_y1], radius=8, fill=_hex(COLORS["zinc-900"]), outline=_hex(COLORS["zinc-800"]), width=1)
        if fill_w > 0:
            draw.rounded_rectangle([band_x0, band_y0, band_x0 + max(fill_w, 12), band_y1], radius=8, fill=_hex(stress_accent))
        # Yüzde etiketi
        pct_str = f"{spec.stat_value}" if spec.stat_value else ""
        if pct_str:
            pf = self.inter(16, bold=True)
            pw = draw.textbbox((0, 0), pct_str, font=pf)[2]
            draw.text((band_x1 - pw - 4, band_y0 - 20), pct_str, font=pf, fill=_hex(stress_accent))
        cursor_y = band_y1 + 24

        # Metrikler (margin-call, gereken teminat)
        if spec.metrics:
            mf_label = self.inter(18, bold=True)
            mf_value = self.outfit(32)
            col_w = (w - 2 * PAD) // min(len(spec.metrics), 3)
            for i, (label, value) in enumerate(spec.metrics[:3]):
                cx = PAD + i * col_w
                draw.text((cx, cursor_y), _tr_upper(label), font=mf_label, fill=_hex(COLORS["zinc-500"]))
                draw.text((cx, cursor_y + 24), str(value), font=mf_value, fill=_hex(COLORS["zinc-100"]))
            cursor_y += self._line_h(mf_value) + 40

        # Başlık (stres notu)
        if spec.headline and cursor_y < content_bottom - 60:
            hf = self.outfit(30 if spec.format == "twitter" else 36)
            lh = self._line_h(hf)
            avail = content_bottom - 8 - cursor_y
            fit = max(1, min(3, avail // lh))
            lines = self._wrap(draw, spec.headline, hf, w - 2 * PAD, fit)
            for line in lines:
                draw.text((PAD, cursor_y), line, font=hf, fill=_hex(COLORS["zinc-300"]))
                cursor_y += lh

        # stat_change → XU030/vadeli
        if spec.stat_change and cursor_y < content_bottom - 40:
            scf = self.inter(20, bold=True)
            draw.text((PAD, cursor_y + 4), spec.stat_change, font=scf, fill=_hex(COLORS["zinc-400"]))

        self._draw_footer(draw, content_bottom, w)
        return self._save(img, out_path)

    # ---- 5. Gündem şablonu -----------------------------------------------------

    def _render_gundem(self, spec: CardSpec, out_path: Path | None = None) -> Path:
        """Gündem/Flash: sol kenar çubuk + dolu amber rozet + FLASH etiketi + dev başlık."""
        accent_hex = ACCENTS["amber"]["400"]
        w, h = self._canvas_size(spec.format)

        img = self._background(accent_hex, w, h, photo_path=spec.photo_path).convert("RGBA")
        draw = ImageDraw.Draw(img)

        # Sol kenar vurgu çubuğu (gündem kimliği)
        draw.rectangle([0, 0, 10, h], fill=_hex(accent_hex))

        self._draw_wordmark(draw, accent_hex)
        self._draw_badge(draw, CATEGORY_LABEL["gundem"], accent_hex, filled=True, card_w=w)

        content_top = 200
        content_bottom = h - 84
        left_w = w - 2 * PAD - 20  # sol çubuk payı

        cursor_y = content_top

        # FLASH rozeti
        flash_font = self.inter(20, bold=True)
        flash_text = "FLASH"
        fw = draw.textbbox((0, 0), flash_text, font=flash_font)[2]
        draw.rounded_rectangle(
            [PAD + 12, cursor_y, PAD + 12 + fw + 28, cursor_y + 40],
            radius=8,
            fill=_hex(accent_hex),
        )
        draw.text((PAD + 12 + 14, cursor_y + 10), flash_text, font=flash_font, fill=_hex(COLORS["black"]))
        cursor_y += 40 + 20

        # Ticker rozeti (varsa)
        if spec.ticker:
            tf = self.inter(22, bold=True)
            ttext = f"${_tr_upper(spec.ticker)}"
            tw = draw.textbbox((0, 0), ttext, font=tf)[2]
            draw.rounded_rectangle(
                [PAD + 12, cursor_y, PAD + 12 + tw + 28, cursor_y + 44],
                radius=10,
                outline=_hex(accent_hex),
                width=2,
            )
            draw.text((PAD + 12 + 14, cursor_y + 10), ttext, font=tf, fill=_hex(accent_hex))
            cursor_y += 44 + 18

        # Dev başlık — square/story formatlarda daha büyük
        hl_size = 54 if spec.format == "twitter" else 64
        headline_font = self.outfit(hl_size)
        lh = self._line_h(headline_font)
        avail = content_bottom - 8 - cursor_y
        fit = max(1, min(4, avail // lh))
        lines = self._wrap(draw, spec.headline, headline_font, left_w - 12, fit)

        # Dikey ortala
        block_h = len(lines) * lh
        slack = max(0, (content_bottom - cursor_y - block_h) // 2 - 6)
        y = cursor_y + slack
        for line in lines:
            draw.text((PAD + 12, y), line, font=headline_font, fill=_hex(COLORS["zinc-100"]))
            y += lh

        self._draw_footer(draw, content_bottom, w)
        return self._save(img, out_path)
