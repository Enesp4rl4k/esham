"""İçerik deposu — bot ile web arasındaki köprü.

Bot ürettiği raporu buradan `web/content/reports/<tarih>-<slug>.json` dosyasına yazar.
Şema, web tarafındaki `src/lib/content.ts` içindeki `Report` arayüzüyle birebir uyumlu
olmalıdır. Hacim büyüyünce bu sınıfın gövdesi bir veritabanı yazımına çevrilebilir;
web tarafındaki okuma sözleşmesi değişmeden kalır.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from ..config import get_logger, settings
from ..guardrails import allow, validate_report

log = get_logger(__name__)

# web/src/lib/content-utils.ts içindeki CATEGORIES ile senkron tutulmalı.
VALID_CATEGORIES = {"bist", "global", "ipo", "viop", "gundem", "kripto", "teknoloji"}

_TR_MAP = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosucgiosu")


def slugify(text: str) -> str:
    text = text.translate(_TR_MAP)
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return text or "rapor"


@dataclass
class ReportDraft:
    title: str
    category: str
    summary: str
    body: str
    sources: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    author: str = "Esham AI"
    ai_generated: bool = True
    published_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    slug: str | None = None
    # Aynı görsel hem tweet'e hem web hero/OG'ye gider — tek üretim, tek kaynak.
    image_path: Path | None = None

    def resolved_slug(self) -> str:
        base = self.slug or slugify(self.title)
        return f"{base}-{self.published_at.date().isoformat()}"

    def to_document(self, image_rel_url: str | None = None) -> dict:
        if self.category not in VALID_CATEGORIES:
            raise ValueError(
                f"Geçersiz kategori: {self.category!r}. Beklenen: {sorted(VALID_CATEGORIES)}"
            )
        doc = {
            "slug": self.resolved_slug(),
            "title": self.title,
            "category": self.category,
            "summary": self.summary,
            "publishedAt": self.published_at.astimezone(timezone.utc)
            .isoformat()
            .replace("+00:00", "Z"),
            "author": self.author,
            "aiGenerated": self.ai_generated,
            "sources": self.sources,
            "tags": self.tags,
            "body": self.body,
        }
        if image_rel_url:
            doc["image"] = image_rel_url
        return doc


class ContentStore:
    def __init__(self, content_dir: Path | None = None, cards_dir: Path | None = None) -> None:
        self.content_dir = content_dir or settings.content_dir
        self.content_dir.mkdir(parents=True, exist_ok=True)
        self.cards_dir = cards_dir or settings.cards_dir

    def publish(self, draft: ReportDraft) -> Path | None:
        """Raporu yayınlar. Acil durdurma veya guardrail'a takılırsa yazmaz, None döner."""
        if settings.paused:
            log.info("[PAUSED] Rapor yayını atlandı: %s", draft.title)
            return None
        violations = validate_report(draft.title, draft.summary, draft.body)
        if not allow(f"rapor '{draft.title}'", violations):
            return None

        slug = draft.resolved_slug()
        image_rel_url = self._store_image(draft.image_path, slug)

        doc = draft.to_document(image_rel_url)
        filename = f"{draft.published_at.date().isoformat()}-{slugify(draft.title)}.json"
        path = self.content_dir / filename
        path.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        log.info("Rapor yayınlandı: %s (%s)", doc["slug"], path)

        # Render/VPS modunda: üretilen raporu otomatik git push yap ki
        # Cloudflare Pages yeni içeriği görebilsin.
        self._git_push(path, slug)

        return path

    def _git_push(self, report_path: Path, slug: str) -> None:
        """Yeni raporu ve varsa kart görselini git'e commit edip push eder.

        Sadece GIT_AUTO_PUSH=true ortam değişkeni set edilmişse çalışır.
        GitHub Actions zaten kendi commit/push adımını yönetir; bu metot
        Render gibi uzun-ömürlü süreçler içindir.
        """
        if os.getenv("GIT_AUTO_PUSH", "").lower() not in ("1", "true", "yes"):
            return

        git_token = os.getenv("GIT_PUSH_TOKEN") or os.getenv("GITHUB_TOKEN")
        git_repo = os.getenv("GIT_REPO_URL")  # https://github.com/user/repo.git

        try:
            from ..config import PROJECT_ROOT
            repo_root = PROJECT_ROOT

            # Remote URL'yi token ile güncelle (ilk seferinde veya her seferinde)
            if git_token and git_repo:
                # token'ı URL'e göm: https://token@github.com/user/repo.git
                authed_url = git_repo.replace("https://", f"https://{git_token}@")
                subprocess.run(
                    ["git", "remote", "set-url", "origin", authed_url],
                    cwd=repo_root, capture_output=True, check=False
                )

            # git config (bot kimliği)
            subprocess.run(["git", "config", "user.email", "bot@esham.local"],
                           cwd=repo_root, capture_output=True, check=False)
            subprocess.run(["git", "config", "user.name", "esham-bot"],
                           cwd=repo_root, capture_output=True, check=False)

            # Stage: rapor JSON + cards klasörü + data klasörü
            subprocess.run(
                ["git", "add",
                 "web/content/reports",
                 "web/public/cards",
                 "web/public/data"],
                cwd=repo_root, capture_output=True, check=False
            )

            # Değişiklik var mı?
            diff = subprocess.run(
                ["git", "diff", "--staged", "--quiet"],
                cwd=repo_root, capture_output=True
            )
            if diff.returncode == 0:
                log.debug("Git push atlandı: staged değişiklik yok.")
                return

            subprocess.run(
                ["git", "commit", "-m", f"content: {slug}"],
                cwd=repo_root, capture_output=True, check=True
            )
            result = subprocess.run(
                ["git", "push", "origin", "HEAD"],
                cwd=repo_root, capture_output=True, text=True
            )
            if result.returncode == 0:
                log.info("Git push başarılı: %s", slug)
            else:
                log.warning("Git push başarısız: %s", result.stderr[:200])
        except Exception as exc:
            log.warning("Git push hatası (%s); rapor yerel olarak yazıldı.", exc)

    def _store_image(self, image_path: Path | None, slug: str) -> str | None:
        """Üretilen kartı web'in statik `public/cards/` klasörüne kopyalar."""
        if not image_path or not image_path.exists():
            return None
        try:
            self.cards_dir.mkdir(parents=True, exist_ok=True)
            dest = self.cards_dir / f"{slug}.png"
            shutil.copy(image_path, dest)
            return f"/cards/{slug}.png"
        except OSError as exc:
            log.warning("Kart görseli kopyalanamadı (%s); rapor görselsiz yayınlanacak.", exc)
            return None
