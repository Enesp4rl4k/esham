"""Default fallback kart görselleri oluşturur.

web/public/cards/default-{kategori}.png dosyalarını üretir.
Gerçek bir kart üretilemediğinde (guardrail, hata vb.) web tarafı
bu fallback görsellerle devam eder.
"""
from __future__ import annotations

import sys
from pathlib import Path

# bot/ klasöründen çalıştırıldığında proje kökünü ayarla
PROJECT_ROOT = Path(__file__).resolve().parent.parent
CARDS_DIR = PROJECT_ROOT / "web" / "public" / "cards"
CARDS_DIR.mkdir(parents=True, exist_ok=True)

# Kategori → (arka plan rengi, vurgu rengi, etiket)
CATEGORIES = {
    "bist":      ((10, 30, 50),   (56, 189, 248),   "BIST & SEKTÖR"),
    "global":    ((15, 10, 40),   (139, 92, 246),   "KÜRESEL MAKRO"),
    "ipo":       ((5, 35, 20),    (52, 211, 153),   "HALKA ARZ & KAP"),
    "viop":      ((35, 15, 5),    (251, 146, 60),   "VİOP & TÜREV"),
    "gundem":    ((35, 25, 5),    (251, 191, 36),   "GÜNDEM"),
    "kripto":    ((35, 15, 5),    (253, 186, 116),  "KRİPTO"),
    "teknoloji": ((35, 10, 30),   (244, 114, 182),  "TEKNOLOJİ & AI"),
    "insider":   ((35, 5, 5),     (248, 113, 113),  "İÇSEL İŞLEM"),
}

W, H = 1200, 630


def make_default_card(category: str, bg_rgb: tuple, accent_rgb: tuple, label: str) -> Path:
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        print("Pillow bulunamadı — pip install Pillow")
        sys.exit(1)

    img = Image.new("RGB", (W, H), bg_rgb)
    draw = ImageDraw.Draw(img)

    # Arka plan: hafif gradient efekti (üst yarı biraz açık)
    for y in range(H // 2):
        alpha = int(20 * (1 - y / (H / 2)))
        overlay = tuple(min(255, c + alpha) for c in bg_rgb)
        draw.line([(0, y), (W, y)], fill=overlay)  # type: ignore[arg-type]

    # Sol kenarda dikey accent çizgi
    draw.rectangle([0, 0, 6, H], fill=accent_rgb)

    # Kategori etiketi — üst sol
    try:
        font_path = Path(__file__).parent / "esham" / "assets" / "fonts" / "Outfit-Bold.ttf"
        font_label = ImageFont.truetype(str(font_path), 28) if font_path.exists() else ImageFont.load_default()
        font_brand = ImageFont.truetype(str(font_path), 22) if font_path.exists() else ImageFont.load_default()
        font_main  = ImageFont.truetype(str(font_path), 72) if font_path.exists() else ImageFont.load_default()
    except Exception:
        font_label = font_brand = font_main = ImageFont.load_default()

    # Kategori badge
    badge_x, badge_y = 40, 40
    draw.text((badge_x, badge_y), label, fill=accent_rgb, font=font_label)

    # Ortada büyük Esham wordmark
    wordmark = "Esham"
    try:
        bbox = draw.textbbox((0, 0), wordmark, font=font_main)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
    except AttributeError:
        tw, th = draw.textsize(wordmark, font=font_main)  # type: ignore[attr-defined]
    cx = (W - tw) // 2
    cy = (H - th) // 2 - 30

    # Gölge
    draw.text((cx + 3, cy + 3), wordmark, fill=(0, 0, 0, 120), font=font_main)
    # Es → accent rengi, ham → beyaz
    draw.text((cx, cy), "Es", fill=accent_rgb, font=font_main)
    try:
        es_bbox = draw.textbbox((0, 0), "Es", font=font_main)
        es_w = es_bbox[2] - es_bbox[0]
    except AttributeError:
        es_w, _ = draw.textsize("Es", font=font_main)  # type: ignore[attr-defined]
    draw.text((cx + es_w, cy), "ham", fill=(240, 237, 232), font=font_main)

    # Alt satır tagline
    tagline = "YAPAY ZEKA DESTEKLİ PİYASA ANALİZİ"
    try:
        tb = draw.textbbox((0, 0), tagline, font=font_brand)
        tl_w = tb[2] - tb[0]
    except AttributeError:
        tl_w, _ = draw.textsize(tagline, font=font_brand)  # type: ignore[attr-defined]
    draw.text(((W - tl_w) // 2, cy + th + 20), tagline, fill=(100, 95, 90), font=font_brand)

    # Alt çizgi
    draw.rectangle([40, H - 60, W - 40, H - 57], fill=accent_rgb)

    # Alt sağ: domain
    domain = "esham.pages.dev"
    try:
        db = draw.textbbox((0, 0), domain, font=font_brand)
        d_w = db[2] - db[0]
    except AttributeError:
        d_w, _ = draw.textsize(domain, font=font_brand)  # type: ignore[attr-defined]
    draw.text((W - 40 - d_w, H - 50), domain, fill=(74, 71, 68), font=font_brand)

    out = CARDS_DIR / f"default-{category}.png"
    img.save(str(out), "PNG", optimize=True)
    print(f"  ✓ {out.name}")
    return out


def main() -> None:
    import sys
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    print(f"Default kart gorselleri olusturuluyor -> {CARDS_DIR}")
    ok = 0
    for cat, (bg, accent, label) in CATEGORIES.items():
        try:
            make_default_card(cat, bg, accent, label)
            ok += 1
        except Exception as exc:
            print(f"  HATA {cat}: {exc}")
    print(f"\nTamamlandi: {ok}/{len(CATEGORIES)} gorsel.")


if __name__ == "__main__":
    main()
