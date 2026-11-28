"""İş akışının git işlemleri: commit + push ve master'la eşitleme (GitHub koşucusunda çalışır).

Eski ``commit-push.sh`` ``pull --rebase -X theirs`` kullanıyordu: çakışmada koşunun kendi sürümü kazanıyordu.
Bayat bir checkout'tan başlayan koşu, master'daki ``sent`` kaydını ``pending``'e çevirebiliyordu (PR #31
ikinci tur). Şimdi:

- ``-X theirs`` YOK. Push reddedilirse master çekilir ve commit üstüne yeniden oynatılır (rebase).
- ``bot/state/telegram_outbox.json`` ANAHTAR BAZINDA birleşir (``.gitattributes`` → ``merge=esham-outbox``,
  sürücü: ``publishing/outbox_merge_driver.py``): son durumlar pending/in_flight'ı her zaman yener.
- ``bot/state/esham_state.json`` ``merge=binary``: iki taraf da değiştirdiyse çakışma.
- Herhangi bir çakışma çözülemezse rebase geri alınır ve ``GitSyncError``: iş akışı hiçbir şey göndermez.
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

from .config import PROJECT_ROOT, get_logger

log = get_logger(__name__)

IDENTITY = {
    "GIT_AUTHOR_NAME": "esham-bot", "GIT_AUTHOR_EMAIL": "bot@esham.local",
    "GIT_COMMITTER_NAME": "esham-bot", "GIT_COMMITTER_EMAIL": "bot@esham.local",
}


class GitSyncError(RuntimeError):
    """Push edilemedi ya da çakışma çözülemedi: bu koşu Telegram'a hiçbir şey göndermemeli."""


def _merge_config() -> list[str]:
    py = Path(sys.executable).as_posix()
    return [
        "-c", "merge.esham-outbox.name=esham giden kutusu (anahtar bazında)",
        "-c", f'merge.esham-outbox.driver="{py}" -m esham.publishing.outbox_merge_driver %O %A %B',
    ]


def _env() -> dict:
    env = {**os.environ, **IDENTITY, "GIT_EDITOR": "true"}
    bot = str(PROJECT_ROOT / "bot")
    env["PYTHONPATH"] = bot + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    return env


def _git(root: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    proc = subprocess.run(["git", "-C", str(root), *_merge_config(), *args],
                          capture_output=True, text=True, env=_env())
    if check and proc.returncode != 0:
        raise GitSyncError(f"git {' '.join(args)}: {proc.stderr.strip()[:500]}")
    return proc


def _rebase_onto_master(root: Path, branch: str) -> None:
    _git(root, "fetch", "-q", "origin", branch)
    proc = _git(root, "rebase", "--autostash", f"origin/{branch}", check=False)
    if proc.returncode != 0:
        _git(root, "rebase", "--abort", check=False)
        raise GitSyncError(
            "master ile çakışma çözülemedi (durum/rapor dosyası iki tarafta da değişmiş); "
            f"bu koşu hiçbir şey göndermeyecek: {(proc.stdout + proc.stderr).strip()[:500]}"
        )


def sync_with_master(root: Path = PROJECT_ROOT, branch: str = "master") -> str:
    """Yerel HEAD'i master'ın güncel ucuna getirir (gerekirse yerel commit'leri üstüne oynatır)."""
    _git(root, "fetch", "-q", "origin", branch)
    head = _git(root, "rev-parse", "HEAD").stdout.strip()
    remote = _git(root, "rev-parse", f"origin/{branch}").stdout.strip()
    if head == remote:
        return "current"
    _rebase_onto_master(root, branch)
    return "rebased"


def commit_push(message: str, paths: list[str], root: Path = PROJECT_ROOT, branch: str = "master",
                retries: int = 3, wait: float = 5.0) -> str:
    """Verilen yolları commit'ler ve push eder: ``pushed`` | ``clean``. Başarısızsa ``GitSyncError``."""
    for p in paths:
        if (root / p).exists():
            _git(root, "add", "--", p)
    if _git(root, "diff", "--staged", "--quiet", check=False).returncode == 0:
        return "clean"
    _git(root, "commit", "-q", "-m", message)
    last = ""
    for attempt in range(1, retries + 1):
        proc = _git(root, "push", "-q", "origin", f"HEAD:{branch}", check=False)
        if proc.returncode == 0:
            return "pushed"
        last = proc.stderr.strip()[:300]
        log.warning("Push reddedildi (deneme %d/%d): %s", attempt, retries, last)
        _rebase_onto_master(root, branch)  # çakışma çözülemezse GitSyncError
        time.sleep(wait * attempt)
    raise GitSyncError(f"push {retries} denemede başarısız: {last}")
