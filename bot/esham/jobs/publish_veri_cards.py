"""Veri grafiği paylaşım kartları → ``web/public/veri-kart/<slug>-<boyut>.png``.

1. ``node web/scripts/veri-scenes.mjs <geçici klasör>``: her veri kümesi için sahne (grafiğin tek tanımı, web/src/lib/veri.ts).
2. ``esham.publishing.veri_cards``: sahneyi PNG'ye çizer; PNG sahnenin sha256 özetini taşır.
Veri dosyası değiştiyse bu iş aynı commit'te çalıştırılmalıdır; aksi halde web testi (kart ↔ sahne özeti) başarısız olur
ve dağıtım durur — eski sayılı bir kart yayımlanmaz.

Taslak/varyant: ``--all-variants --out <depo içi klasör>`` tüm görsel varyantları <slug>-<boyut>-<varyant>.png adıyla yazar.
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from ..publishing import veri_cards

ROOT = Path(__file__).resolve().parents[3]
WEB = ROOT / "web"
OUT = WEB / "public" / "veri-kart"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Veri grafiği kartlarını üretir")
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--all-variants", action="store_true")
    ap.add_argument("--scenes-dir", type=Path, help="sahneleri geçici klasör yerine bu klasöre yaz (silinmez)")
    args = ap.parse_args(argv)
    # CLI yolları depo içinde kalmalı (taslaklar depo içinde üretilip elle kopyalanır)
    for name in ("out", "scenes_dir"):
        p = getattr(args, name)
        if p is not None:
            r = p.resolve()
            if not r.is_relative_to(ROOT):
                print(f"yol depo içinde olmalı: {r}", file=sys.stderr)
                return 2
            setattr(args, name, r)
    node = shutil.which("node")
    if not node:
        print("node bulunamadı (web/scripts/veri-scenes.mjs için gerekli)", file=sys.stderr)
        return 2
    def run(tmp: str) -> int:
        cmd = [node, str(WEB / "scripts" / "veri-scenes.mjs"), tmp] + (["--all-variants"] if args.all_variants else [])
        subprocess.run(cmd, check=True, cwd=WEB)
        return veri_cards.main([tmp, str(args.out), "--name", "full" if args.all_variants else "published"])

    if args.scenes_dir:
        args.scenes_dir.mkdir(parents=True, exist_ok=True)
        return run(str(args.scenes_dir))
    with tempfile.TemporaryDirectory(prefix="esham-veri-") as tmp:
        return run(tmp)


if __name__ == "__main__":
    sys.exit(main())
