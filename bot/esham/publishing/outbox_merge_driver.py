"""git birleştirme sürücüsü: ``bot/state/telegram_outbox.json`` anahtar bazında birleşir.

``.gitattributes``: ``bot/state/telegram_outbox.json merge=esham-outbox``. Sürücü ``git_sync`` tarafından
``-c merge.esham-outbox.driver=...`` ile tanımlanır (``python -m esham.publishing.outbox_merge_driver %O %A %B``).
Sonuç ``%A`` dosyasına yazılır. Dosyalardan biri okunamazsa çıkış 1 = çözülemeyen çakışma: rebase durur,
iş akışı hiçbir şey göndermez. Kural (son durum her zaman kazanır) ``outbox.merge_outboxes``'tadır.
"""
from __future__ import annotations

import sys
from pathlib import Path

from .outbox import dump_entries, load_entries, merge_outboxes


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("kullanım: outbox_merge_driver BASE OURS THEIRS", file=sys.stderr)
        return 2
    base, ours, theirs = (Path(a) for a in argv)
    try:
        merged = merge_outboxes(load_entries(base), load_entries(ours), load_entries(theirs))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"giden kutusu birleştirilemedi: {exc}", file=sys.stderr)
        return 1
    dump_entries(ours, merged)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
