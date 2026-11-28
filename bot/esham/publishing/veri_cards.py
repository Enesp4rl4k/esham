"""Veri grafiği kartları: web/src/lib/veri.ts `buildScene` sahnesi (JSON) → PNG.

Grafiğin TEK tanımı web tarafındadır; burada yalnızca sahnedeki öğeler (dikdörtgen, çizgi, çoklu çizgi, daire, çokgen,
metin) olduğu gibi çizilir. Hiçbir sayı burada hesaplanmaz ya da biçimlenmez, bu yüzden kart ile sayfadaki grafik ve tablo
farklı sayı gösteremez. PNG, sahne baytlarının sha256 özetini ``esham:scene-sha256`` metin parçası olarak taşır;
web testi (veri.test.mjs) yayımlanan kartın güncel veriden üretilen sahneyle aynı olduğunu bu özetle doğrular.

Yazı tipleri ve marka kartı üreticisiyle aynıdır (``cards.CardGenerator`` yazı tipi önbelleği: Outfit Bold + Inter).
Kenar yumuşatma için sahne 2× çizilip küçültülür.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, PngImagePlugin

from .cards import CardGenerator, _hex

SS = 2  # süper örnekleme
ANCHOR = {"start": "ls", "middle": "ms", "end": "rs"}

_fonts = CardGenerator()


def _font(kind: str, size: float):
    px = max(1, round(size * SS))
    if kind == "display":
        return _fonts.outfit(px)
    return _fonts.inter(px, bold=(kind == "bodyBold"))


def _dashed(draw: ImageDraw.ImageDraw, p0, p1, fill, width, dash):
    import math

    (x0, y0), (x1, y1) = p0, p1
    length = math.hypot(x1 - x0, y1 - y0)
    if length == 0:
        return
    on, off = dash[0] * SS, dash[1] * SS
    ux, uy = (x1 - x0) / length, (y1 - y0) / length
    t = 0.0
    while t < length:
        e = min(t + on, length)
        draw.line([(x0 + ux * t, y0 + uy * t), (x0 + ux * e, y0 + uy * e)], fill=fill, width=width)
        t = e + off


def render_scene(scene: dict[str, Any]) -> tuple[Image.Image, list[str]]:
    """Sahneyi çizer. Döner: (görüntü, çizilen metinler) — ikincisi testlerde parite denetimi için."""
    pal = {k: _hex(v) for k, v in scene["palette"].items()}
    W, H = int(scene["w"]), int(scene["h"])
    img = Image.new("RGB", (W * SS, H * SS), pal["bg"])
    draw = ImageDraw.Draw(img)
    texts: list[str] = []
    S = lambda v: v * SS  # noqa: E731
    for it in scene["items"]:
        k = it["k"]
        if k == "rect":
            box = [S(it["x"]), S(it["y"]), S(it["x"] + it["w"]) - 1, S(it["y"] + it["h"]) - 1]
            if it.get("rx"):
                draw.rounded_rectangle(box, radius=S(it["rx"]), fill=pal[it["fill"]])
            else:
                draw.rectangle(box, fill=pal[it["fill"]])
        elif k == "line":
            w = max(1, round(S(it["sw"])))
            p0, p1 = (S(it["x1"]), S(it["y1"])), (S(it["x2"]), S(it["y2"]))
            if it.get("dash"):
                _dashed(draw, p0, p1, pal[it["stroke"]], w, it["dash"])
            else:
                draw.line([p0, p1], fill=pal[it["stroke"]], width=w)
        elif k == "path":
            w = max(1, round(S(it["sw"])))
            pts = [(S(x), S(y)) for x, y in it["pts"]]
            draw.line(pts, fill=pal[it["stroke"]], width=w, joint="curve")
            r = w / 2  # yuvarlak uçlar (SVG stroke-linecap="round" ile aynı görünüm)
            for x, y in (pts[0], pts[-1]):
                draw.ellipse([x - r, y - r, x + r, y + r], fill=pal[it["stroke"]])
        elif k == "circle":
            x, y, r = S(it["x"]), S(it["y"]), S(it["r"])
            sw = S(it.get("sw") or 0)
            if it.get("stroke") and sw:
                draw.ellipse([x - r - sw / 2, y - r - sw / 2, x + r + sw / 2, y + r + sw / 2], fill=pal[it["stroke"]])
            draw.ellipse([x - r, y - r, x + r, y + r], fill=pal[it["fill"]])
        elif k == "poly":
            pts = [(S(x), S(y)) for x, y in it["pts"]]
            sw = S(it.get("sw") or 0)
            if it.get("stroke") and sw:
                draw.polygon(pts, fill=pal[it["fill"]], outline=pal[it["stroke"]], width=max(1, round(sw)))
            else:
                draw.polygon(pts, fill=pal[it["fill"]])
        elif k == "text":
            font = _font(it["font"], it["size"])
            spans = it["spans"]
            full = "".join(s["text"] for s in spans)
            texts.append(full)
            x, y = S(it["x"]), S(it["y"])
            if len(spans) == 1:
                draw.text((x, y), full, font=font, fill=pal[spans[0]["fill"]], anchor=ANCHOR[it["anchor"]])
                continue
            total = font.getlength(full)
            if it["anchor"] == "middle":
                x -= total / 2
            elif it["anchor"] == "end":
                x -= total
            for s in spans:
                draw.text((x, y), s["text"], font=font, fill=pal[s["fill"]], anchor="ls")
                x += font.getlength(s["text"])
        else:
            raise ValueError(f"bilinmeyen sahne öğesi: {k}")
    return img.resize((W, H), Image.LANCZOS), texts


def save_png(img: Image.Image, path: Path, scene_bytes: bytes, scene: dict[str, Any]) -> None:
    info = PngImagePlugin.PngInfo()
    info.add_text("esham:scene-sha256", hashlib.sha256(scene_bytes).hexdigest())
    info.add_text("esham:slug", scene["meta"]["slug"])
    info.add_text("esham:variant", scene["meta"]["variant"])
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, "PNG", pnginfo=info, optimize=True)


def render_file(scene_path: Path, out_path: Path) -> Path:
    raw = scene_path.read_bytes()
    scene = json.loads(raw.decode("utf-8"))
    img, _ = render_scene(scene)
    save_png(img, out_path, raw, scene)
    return out_path


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Veri grafiği sahnelerini PNG'ye çevirir")
    ap.add_argument("scenes", type=Path, help="*.scene.json klasörü (web/scripts/veri-scenes.mjs çıktısı)")
    ap.add_argument("out", type=Path)
    ap.add_argument("--name", choices=["published", "full"], default="published",
                    help="published: <slug>-<boyut>.png (sitede yayımlanan ad); full: <slug>-<boyut>-<varyant>.png")
    args = ap.parse_args(argv)
    for p in sorted(args.scenes.glob("*.scene.json")):
        slug, size, variant = p.name[: -len(".scene.json")].split("__")
        name = f"{slug}-{size}.png" if args.name == "published" else f"{slug}-{size}-{variant}.png"
        print(render_file(p, args.out / name))
    return 0


if __name__ == "__main__":
    sys.exit(main())
