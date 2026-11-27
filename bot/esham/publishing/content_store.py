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
from ..neutral import REPORT_SCHEMA_VERSION

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
    # Yapılandırılmış ek alan (şu an sadece halka arz meta verisi). Web tarafındaki
    # `Report.ipo` ile senkron: takvim/istatistik sayfaları body markdown'ini regex ile
    # sömmek zorunda kalmasın. None ise JSON'a hiç yazılmaz (eski raporlar değişmez).
    ipo: dict | None = None
    # BİREBİR/olgusal blok (KAP başlığı, şirket, tarih, bildirim türü, tutarlar, KAP bağlantısı):
    # tarafsız dil süzgecinden GEÇMEZ ve gövdenin sonuna eklenir. `body` yalnız üretilmiş metindir.
    facts: str = ""
    # Özet birebir kaynaksa (ör. KAP başlığı) süzülmez.
    summary_verbatim: bool = False
    # Üretilmiş özet süzgece takılırsa kullanılacak birebir özet (KAP başlığı).
    fallback_summary: str = ""
    # Tüm üreticiler bu sürümü yazar. Web, eski kayıt kararını YALNIZ bu alana göre verir
    # (alan yoksa = bu tarafsız dil sürümünden önce üretilmiş kayıt).
    schema_version: int | None = REPORT_SCHEMA_VERSION
    kap: dict | None = None

    def resolved_slug(self) -> str:
        base = self.slug or slugify(self.title)
        return f"{base}-{self.published_at.date().isoformat()}"

    def filename(self) -> str:
        return f"{self.published_at.date().isoformat()}-{self.slug or slugify(self.title)}.json"

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
            "body": "\n\n".join(p for p in (self.body.strip(), self.facts.strip()) if p),
        }
        if image_rel_url:
            doc["image"] = image_rel_url
        if self.ipo:
            doc["ipo"] = self.ipo
        if self.schema_version is not None:
            doc["schemaVersion"] = self.schema_version
        if self.kap:
            doc["kap"] = self.kap
        return doc


class ContentStore:
    def __init__(self, content_dir: Path | None = None, cards_dir: Path | None = None) -> None:
        self.content_dir = content_dir or settings.content_dir
        self.content_dir.mkdir(parents=True, exist_ok=True)
        self.cards_dir = cards_dir or settings.cards_dir
        #: Son publish/prepare kararı: published | duplicate | paused | blocked | ok
        self.last_status = "none"
    def _is_daily_duplicate(self, draft: ReportDraft) -> bool:
        """Kullanıcı kuralı: Gün içi aynı varlık hakkında (yön değişse dahi) tek bir
        kaliteli paylaşım yeterlidir; gün içi 2 defa aynı paylaşımı yapmaya gerek yok.
        """
        today_prefix = draft.published_at.date().isoformat()
        if (self.content_dir / draft.filename()).exists():
            return True
        if draft.kap:
            # KAP bildirimleri bildirim NUMARASIYLA tekilleşir — tarihten bağımsız: rapor yazıldıktan sonra
            # bir hata olup ertesi gün yeniden denenirse çift rapor/çift gönderi oluşmaz. Varlık bazlı
            # günlük tavan uygulanmaz (aynı gün aynı başlıklı iki ayrı bildirim kaybolmasın).
            index = str(draft.kap.get("index") or "")
            if index:
                for path in self.content_dir.glob(f"*-{index}.json"):
                    try:
                        doc = json.loads(path.read_text(encoding="utf-8"))
                    except (OSError, ValueError):
                        continue
                    if str((doc.get("kap") or {}).get("index") or "") == index:
                        log.info("[MÜKERRER] KAP bildirimi #%s zaten yayınlanmış (%s)", index, path.name)
                        return True
            return False

        title_lower = draft.title.translate(_TR_MAP).lower()
        SINGLE_PER_DAY_ASSETS = [
            ("nasdaq", "nasdaq"),
            ("s&p 500", "s-p-500"),
            ("sp 500", "s-p-500"),
            ("dow jones", "dow-jones"),
            ("bitcoin", "bitcoin"),
            ("ethereum", "ethereum"),
            ("solana", "solana"),
            ("ripple", "ripple"),
            ("viop piyasa", "viop-piyasa"),
            ("bist seans acilisi", "bist-seans-acilisi"),
            ("borsa gunu", "borsa-gunu"),
        ]

        for asset_key, file_token in SINGLE_PER_DAY_ASSETS:
            if asset_key in title_lower:
                existing = list(self.content_dir.glob(f"{today_prefix}-*{file_token}*.json"))
                if existing:
                    log.info(
                        "[MÜKERRER ENGELİ] Gün içinde '%s' için zaten rapor yayınlanmış (%s); ikinci paylaşım atlandı: %s",
                        asset_key, existing[0].name, draft.title,
                    )
                    return True

        return False

    def prepare(self, draft: ReportDraft) -> str:
        """Yayın kararını verir (dosya yazmadan): ok | paused | duplicate | blocked.

        - Üretilmiş gövde/özet tarafsız dil süzgecinden geçer; birebir kısım (``facts``, KAP başlığı,
          birebir özet) süzülmez.
        - Süzgeçten sonra hâlâ ihlal varsa ve rapor bir birebir blok taşıyorsa (KAP), üretilmiş kısım
          atılır ve YALIN rapor yayınlanır — bildirim sessizce kaybolmaz.
        """
        if settings.paused:
            log.info("[PAUSED] Rapor yayını atlandı: %s", draft.title)
            self.last_status = "paused"
            return "paused"

        from ..translation import ensure_turkish, is_mostly_english
        if not draft.facts and is_mostly_english(draft.title):
            tr_title = ensure_turkish(draft.title)
            if tr_title:
                draft.title = tr_title

        from ..neutral import find_banned, sanitize_summary, strip_banned
        draft.body = strip_banned(draft.body)
        if not draft.summary_verbatim:
            draft.summary = sanitize_summary(draft.summary, draft.fallback_summary or draft.title)
            if draft.fallback_summary and draft.summary == draft.fallback_summary:
                draft.summary_verbatim = True
        draft.tags = [t for t in draft.tags if t and not find_banned(t)]

        violations = validate_report(
            draft.title, "" if draft.summary_verbatim else draft.summary, draft.body
        )
        if violations and draft.facts:
            log.warning(
                "Üretilmiş metin guardrail'a takıldı (%s); yalın rapor yayınlanacak: %s",
                "; ".join(violations), draft.title,
            )
            draft.body = ""
            draft.summary = draft.fallback_summary or draft.title
            draft.summary_verbatim = True
            violations = validate_report(draft.title, "", "")
        if not allow(f"rapor '{draft.title}'", violations):
            self.last_status = "blocked"
            return "blocked"
        if self._is_daily_duplicate(draft):
            log.info("[MÜKERRER ATLANDI] Gün içi 2. kez aynı paylaşım yapılmaz: %s", draft.title)
            self.last_status = "duplicate"
            return "duplicate"
        self.last_status = "ok"
        return "ok"

    def publish(self, draft: ReportDraft, *, prepared: bool = False) -> Path | None:
        """Raporu yayınlar. Acil durdurma, mükerrer veya guardrail engelinde yazmaz, None döner
        (neden: ``last_status``)."""
        if not prepared:
            decision = self.prepare(draft)
            if decision != "ok":
                return None

        slug = draft.resolved_slug()
        image_rel_url = self._store_image(draft.image_path, slug)

        doc = draft.to_document(image_rel_url)
        path = self.content_dir / draft.filename()
        path.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        log.info("Rapor yayınlandı: %s (%s)", doc["slug"], path)
        self.last_status = "published"

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
