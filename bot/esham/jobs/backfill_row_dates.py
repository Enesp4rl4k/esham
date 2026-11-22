"""Tek seferlik göç: universe.json / universe-funds.json satırlarına KENDİ veri zamanını (`updated_at`) yazar.

Neden: satır düzeyinde damga eklenmeden önce üretilmiş committed dosyalarda hiçbir satırın tarihi yok; web tarihsiz
satırı "bayat — son veri: bilinmiyor" sayar. Dosya düzeyi damgayı satırlara kopyalamak, taşınmış (eski) satırı taze
göstermek demektir (asıl hata sınıfı). Bu yüzden her satırın GERÇEK tarihi, o satırla aynı turda yazılmış kardeş
dosyadan (`stocks/<T>.json`, `funds/<KOD>.json`: her biri kendi `updated_at` değerini taşır) okunur. Kardeş dosya yoksa
ya da tarihsizse satıra tarih YAZILMAZ (web "bilinmiyor" der); uydurma tarih yok.

Çalıştırma: ``python -m esham.jobs.backfill_row_dates`` (idempotent: tarihli satıra dokunmaz). Dosya düzeyi
`updated_at` (tarama zamanı) değişmez.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

DATA = Path(__file__).resolve().parents[3] / "web" / "public" / "data"


def _sibling_stamp(path: Path) -> str | None:
    try:
        stamp = json.loads(path.read_text(encoding="utf-8")).get("updated_at")
        datetime.fromisoformat(str(stamp).replace("Z", "+00:00"))
        return str(stamp)
    except (OSError, ValueError, AttributeError):
        return None


def _backfill(universe_file: Path, rows_key: str, id_key: str, sibling_dir: Path) -> tuple[int, int]:
    doc: dict[str, Any] = json.loads(universe_file.read_text(encoding="utf-8"))
    filled = unknown = 0
    for row in doc.get(rows_key, []):
        if row.get("updated_at"):
            continue
        stamp = _sibling_stamp(sibling_dir / f"{row[id_key]}.json")
        if stamp:
            row["updated_at"] = stamp
            filled += 1
        else:
            unknown += 1
    if filled:
        universe_file.write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return filled, unknown


def run(data_dir: Path = DATA) -> dict[str, tuple[int, int]]:
    out = {"stocks": _backfill(data_dir / "universe.json", "stocks", "ticker", data_dir / "stocks")}
    funds = data_dir / "universe-funds.json"
    if funds.exists():
        out["funds"] = _backfill(funds, "funds", "code", data_dir / "funds")
    return out


if __name__ == "__main__":
    for name, (filled, unknown) in run().items():
        print(f"{name}: {filled} satıra gerçek tarih yazıldı, {unknown} satır tarihsiz kaldı")
