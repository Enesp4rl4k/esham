"""Yayın kapısı: yeni/değişen raporları web testlerinden RAPOR BAŞINA geçirir.

İkinci tur incelemesi: eski kapı tek bir kırık raporda (ya da kod/test kırıldığında) koşudaki TÜM KAP
bildirimlerinin sayacını artırıyordu; 3 koşuda suçsuz bildirimler de kalıcı düşüyordu.

Akış (en ucuz yol önce; olağan durumda tek ``npm test``):

1. Tüm yeni raporlarla birlikte ``npm test``. Geçerse bitti (``passed``).
2. Kırıldıysa yeni raporlar geçici olarak çekilir (yeni dosya kaldırılır, değişmiş dosya HEAD sürümüne
   döner) ve TEMEL koşulur. Temel de kırıksa sorun KODDA/TESTTE: ``code_broken``. Hiçbir sayaç artmaz,
   hiçbir bildirim düşmez, hiçbir şey commit'lenmez/gönderilmez; bildirimler sonraki koşuda yeniden denenir.
3. Temel yeşilse her rapor TEK BAŞINA temele eklenip sınanır. Kırılanlar ayrılır (``partial``), kalanlar
   yerine konur ve birlikte bir kez daha doğrulanır (rapor etkileşimi kırarsa ``code_broken`` gibi davranılır:
   kimse cezalandırılmaz).

Rapor başına AYNI ``npm test`` koşulur (ayrı bir hafif doğrulayıcı yok): kurallar ve kod birebir aynıdır,
eşdeğerlik kanıtı gerekmez. Maliyet yalnız kırık durumda: temel + rapor sayısı + 1 koşu (en çok ~5 rapor).
"""
from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from .config import PROJECT_ROOT, get_logger

log = get_logger(__name__)

REPORTS_REL = "web/content/reports"
CARDS_REL = "web/public/cards"


@dataclass
class GateResult:
    status: str                      # skipped | passed | partial | code_broken
    bad: list[str] = field(default_factory=list)       # kapıdan geçemeyen rapor yolları
    bad_slugs: list[str] = field(default_factory=list)
    checked: int = 0


def npm_test(root: Path = PROJECT_ROOT) -> bool:
    npm = shutil.which("npm") or "npm"
    proc = subprocess.run([npm, "test"], cwd=root / "web", capture_output=True, text=True)
    if proc.returncode != 0:
        tail = "\n".join((proc.stdout + proc.stderr).splitlines()[-25:])
        log.warning("web testleri kırıldı:\n%s", tail)
    return proc.returncode == 0


def git_changed_reports(root: Path = PROJECT_ROOT) -> list[str]:
    out = subprocess.run(["git", "-C", str(root), "status", "--porcelain", "--untracked-files=all", "--", REPORTS_REL],
                         capture_output=True, text=True, check=True).stdout
    paths = []
    for line in out.splitlines():
        path = line[3:].strip().strip('"')
        if path.endswith(".json"):
            paths.append(path)
    return paths


def git_head_content(root: Path = PROJECT_ROOT) -> Callable[[str], bytes | None]:
    def get(rel: str) -> bytes | None:
        proc = subprocess.run(["git", "-C", str(root), "show", f"HEAD:{rel}"], capture_output=True)
        return proc.stdout if proc.returncode == 0 else None
    return get


def _slug_of(data: bytes, rel: str) -> str:
    try:
        return str(json.loads(data.decode("utf-8")).get("slug") or "")
    except (ValueError, UnicodeDecodeError):
        return Path(rel).stem


def run_gate(
    root: Path = PROJECT_ROOT,
    *,
    runner: Callable[[], bool] | None = None,
    changed: list[str] | None = None,
    head_content: Callable[[str], bytes | None] | None = None,
) -> GateResult:
    runner = runner or (lambda: npm_test(root))
    changed = git_changed_reports(root) if changed is None else changed
    head_content = head_content or git_head_content(root)
    if not changed:
        return GateResult("skipped")
    if runner():
        return GateResult("passed", checked=len(changed))

    new = {rel: (root / rel).read_bytes() for rel in changed}
    old = {rel: head_content(rel) for rel in changed}

    def put(rel: str, data: bytes | None) -> None:
        p = root / rel
        if data is None:
            if p.exists():
                p.unlink()
        else:
            p.write_bytes(data)

    try:
        for rel in changed:
            put(rel, old[rel])
        if not runner():
            log.error("Yeni raporlar OLMADAN da web testleri kırık: sorun kodda/testte, rapor suçlanmaz.")
            return GateResult("code_broken", checked=len(changed))
        bad: list[str] = []
        for rel in changed:
            put(rel, new[rel])
            if not runner():
                bad.append(rel)
                log.error("Rapor kapıdan geçmedi: %s", rel)
            put(rel, old[rel])
        good = [rel for rel in changed if rel not in bad]
        for rel in good:
            put(rel, new[rel])
        if good and not runner():
            log.error("Raporlar tek tek geçti ama birlikte kırıldı; kimse cezalandırılmaz (code_broken).")
            return GateResult("code_broken", checked=len(changed))
        slugs = [_slug_of(new[rel], rel) for rel in bad]
        for slug in slugs:  # kırık raporun (henüz commit'lenmemiş) kartı da yayına girmesin
            card = root / CARDS_REL / f"{slug}.png"
            if slug and card.exists() and head_content(f"{CARDS_REL}/{slug}.png") is None:
                card.unlink()
        return GateResult("partial" if bad else "passed", bad=bad, bad_slugs=[s for s in slugs if s], checked=len(changed))
    except BaseException:
        # Beklenmeyen hata: yeni raporlar yerine konur; iş akışı adımı kırmızı biter, hiçbir şey commit'lenmez.
        for rel in changed:
            put(rel, new[rel])
        raise
