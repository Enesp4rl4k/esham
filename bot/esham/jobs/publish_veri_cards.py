"""Veri grafiği paylaşım kartları → ``web/public/veri-kart/<slug>-<boyut>.png``.

1. ``node web/scripts/veri-scenes.mjs [--all-variants]``: her veri kümesi için sahne (grafiğin tek tanımı, web/src/lib/veri.ts)
   sabit klasöre yazılır: ``web/.veri-scenes/yayin`` (ya da ``…/taslak``; git dışı).
2. ``esham.publishing.veri_cards``: sahneyi PNG'ye çizer; PNG sahnenin sha256 özetini taşır.
Veri dosyası değiştiyse bu iş aynı commit'te çalıştırılmalıdır; aksi halde web testi (kart ↔ sahne özeti) başarısız olur
ve dağıtım durur — eski sayılı bir kart yayımlanmaz.

Taslak/varyant: ``--all-variants`` tüm görsel varyantları ``web/.veri-scenes/taslak-png/<slug>-<boyut>-<varyant>.png``
adıyla yazar (git dışı; oradan elle kopyalanır). Komut satırından yol alınmaz.
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

from ..publishing import veri_cards

ROOT = Path(__file__).resolve().parents[3]
WEB = ROOT / "web"
OUT = WEB / "public" / "veri-kart"
SCENES = WEB / ".veri-scenes"
SCRIPT = WEB / "scripts" / "veri-scenes.mjs"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Veri grafiği kartlarını üretir")
    ap.add_argument("--all-variants", action="store_true", help="taslak: tüm varyantlar (web/.veri-scenes/taslak-png)")
    args = ap.parse_args(argv)
    node = shutil.which("node")
    if not node:
        print("node bulunamadı (web/scripts/veri-scenes.mjs için gerekli)", file=sys.stderr)
        return 2
    if args.all_variants:
        subprocess.run([node, str(SCRIPT), "--all-variants"], check=True, cwd=WEB)
        return veri_cards.main([str(SCENES / "taslak"), str(SCENES / "taslak-png"), "--name", "full"])
    subprocess.run([node, str(SCRIPT)], check=True, cwd=WEB)
    return veri_cards.main([str(SCENES / "yayin"), str(OUT), "--name", "published"])


if __name__ == "__main__":
    sys.exit(main())
