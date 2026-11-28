"""Yayın kapısı: yeni/değişen raporları web testlerinden RAPOR BAŞINA geçirir.

İkinci tur incelemesi: eski kapı tek bir kırık raporda (ya da kod/test kırıldığında) koşudaki TÜM KAP
bildirimlerinin sayacını artırıyordu; 3 koşuda suçsuz bildirimler de kalıcı düşüyordu.

Akış (en ucuz yol önce; olağan durumda tek ``npm test``):

1. Tüm yeni raporlarla birlikte ``npm test``. Geçerse bitti (``passed``).
2. Kırıldıysa yeni raporlar geçici olarak çekilir (yeni dosya kaldırılır, değişmiş dosya HEAD sürümüne
   döner) ve TEMEL koşulur. Temel de kırıksa sorun KODDA/TESTTE: ``code_broken``. Hiçbir sayaç artmaz,
   hiçbir bildirim düşmez, hiçbir şey commit'lenmez/gönderilmez; bildirimler sonraki koşuda yeniden denenir.
3. Temel yeşilse her rapor TEK BAŞINA temele eklenip sınanır.
   - Yeni raporların HEPSİ kırıksa (tek raporlu koşu dahil): ``all_broken`` = KOD sorunu (27.11: test "her
     rapor eskidir" varsayıyordu, temel yeşil, her yeni rapor kırık). Sayaç yok; kalıcı suç ancak araya başka
     raporların geçtiği bir koşu girdikten sonra hâlâ kırılan bildirime yazılır
     (``publish_gate.handle_all_broken`` durum makinesi).
   - En az bir rapor geçtiyse: kırılanlar ayrılır (``partial``, yalnız onların sayacı artar), kalanlar yerine
     konur ve birlikte bir kez daha doğrulanır (rapor etkileşimi kırarsa ``code_broken``: kimse cezalandırılmaz).

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
    status: str                      # skipped | passed | partial | all_broken | code_broken
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


class _Tree:
    """Çalışma ağacındaki rapor dosyalarını yeni/eski sürümler arasında değiştirir."""

    def __init__(self, root: Path, changed: list[str], head_content: Callable[[str], bytes | None]) -> None:
        self.root = root
        self.new = {rel: (root / rel).read_bytes() for rel in changed}
        self.old = {rel: head_content(rel) for rel in changed}

    def put(self, rel: str, use_new: bool) -> None:
        data = self.new[rel] if use_new else self.old[rel]
        p = self.root / rel
        if data is not None:
            p.write_bytes(data)
        elif p.exists():
            p.unlink()

    def set_all(self, rels, use_new: bool) -> None:
        for rel in rels:
            self.put(rel, use_new)


def _isolate(tree: _Tree, changed: list[str], runner: Callable[[], bool]) -> list[str]:
    """Temel yeşilken her raporu tek başına sınar; kırılanları döner (ağaç: hepsi eski sürümde kalır)."""
    bad: list[str] = []
    for rel in changed:
        tree.put(rel, True)
        if not runner():
            bad.append(rel)
            log.error("Rapor kapıdan geçmedi: %s", rel)
        tree.put(rel, False)
    return bad


def _drop_cards(root: Path, slugs: list[str], head_content: Callable[[str], bytes | None]) -> None:
    """Kırık raporun (henüz commit'lenmemiş) kartı da yayına girmesin."""
    for slug in slugs:
        card = root / CARDS_REL / f"{slug}.png"
        if slug and card.exists() and head_content(f"{CARDS_REL}/{slug}.png") is None:
            card.unlink()


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

    tree = _Tree(root, changed, head_content)
    try:
        tree.set_all(changed, False)
        if not runner():
            log.error("Yeni raporlar OLMADAN da web testleri kırık: sorun kodda/testte, rapor suçlanmaz.")
            return GateResult("code_broken", checked=len(changed))
        bad = _isolate(tree, changed, runner)
        if len(bad) == len(changed):
            # Yeni raporların HEPSİ kırık (tek rapor dahil): 27.11 sınıfı (test yeni biçimi tanımıyor) → KOD sorunu.
            log.error("Yeni raporların hepsi kırık; kod sorunu sayılıyor (sayaç yalnız şüpheli durum makinesiyle).")
            slugs = [s for s in (_slug_of(tree.new[rel], rel) for rel in bad) if s]
            return GateResult("all_broken", bad=bad, bad_slugs=slugs, checked=len(changed))
        good = [rel for rel in changed if rel not in bad]
        tree.set_all(good, True)
        if good and not runner():
            log.error("Raporlar tek tek geçti ama birlikte kırıldı; kimse cezalandırılmaz (code_broken).")
            return GateResult("code_broken", checked=len(changed))
    except BaseException:
        # Beklenmeyen hata: yeni raporlar yerine konur; iş akışı adımı kırmızı biter, hiçbir şey commit'lenmez.
        tree.set_all(changed, True)
        raise
    slugs = [s for s in (_slug_of(tree.new[rel], rel) for rel in bad) if s]
    _drop_cards(root, slugs, head_content)
    return GateResult("partial" if bad else "passed", bad=bad, bad_slugs=slugs, checked=len(changed))
