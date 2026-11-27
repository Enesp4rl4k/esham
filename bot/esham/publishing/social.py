"""Sosyal medya yayıncısı — sadece Telegram.

Twitter/X paylaşımları manuel olarak yapılır.
Bot yalnızca Telegram kanalına otomatik yayın yapar.

Her gönderi: (1) yasaklı piyasa yargısı/tavsiye kalıplarından deterministik olarak süzülür,
(2) guardrail'dan geçer, (3) sonuna "yatırım tavsiyesi değildir" uyarısı eklenir.
"""
from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import requests

from ..config import get_logger, settings
from ..guardrails import allow, validate_tweet
from ..neutral import DISCLAIMER_GENERIC, strip_banned
from ..state import get_state

log = get_logger(__name__)


def prepare_post(message: str, disclaimer: str | None = None, *, filtered: bool = False) -> str:
    """Gönderi metnini süzer (``filtered=True`` ise zaten süzülmüştür) ve uyarı satırını ekler.
    Süzgeç sonrası metin boşsa "" döner."""
    clean = (message or "").strip() if filtered else strip_banned(message or "")
    if not clean:
        return ""
    note = disclaimer or DISCLAIMER_GENERIC
    if note not in clean:
        clean = f"{clean}\n\n{note}"
    return clean


class SocialPublisher:

    def post_telegram(self, message: str, image_path: Path | None = None) -> bool:
        """Telegram kanalına mesaj/görsel gönderir."""
        if not (settings.telegram_bot_token and settings.telegram_chat_id):
            log.info("[DRY-RUN][Telegram] %s", message[:100])
            return False
        try:
            if image_path and image_path.exists():
                url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendPhoto"
                with open(image_path, "rb") as f:
                    resp = requests.post(
                        url,
                        data={
                            "chat_id": settings.telegram_chat_id,
                            "caption": message[:1024],
                            "parse_mode": "Markdown",
                        },
                        files={"photo": f},
                        timeout=settings.http_timeout,
                    )
            else:
                url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
                resp = requests.post(
                    url,
                    json={
                        "chat_id": settings.telegram_chat_id,
                        "text": message[:4096],
                        "parse_mode": "Markdown",
                    },
                    timeout=settings.http_timeout,
                )
            resp.raise_for_status()
            log.info("Telegram gönderildi.")
            return True
        except requests.RequestException as exc:
            log.error("Telegram gönderimi başarısız: %s", exc)
            return False

    def broadcast(
        self,
        message: str,
        image_path: Path | None = None,
        disclaimer: str | None = None,
        verbatim: Sequence[str] = (),
    ) -> None:
        """Telegram'a yayın yapar. Süzgeç + guardrail + günlük tavan kontrolü yapar.

        ``verbatim``: mesajda geçen BİREBİR kaynak metinleri (ör. KAP başlığı). Bunları içeren satırlar
        süzülmez ve guardrail denetiminde maskelenir — olgusal kaynak bozulmaz.
        Twitter paylaşımı bu fonksiyonla yapılmaz — manuel olarak yapılır.
        280 karakter sınırı uyarı satırı eklenmeden ÖNCEKİ metne uygulanır (Telegram açıklama sınırı 1024).
        """
        if settings.paused:
            log.info("[PAUSED] Paylaşım atlandı: %s", message[:60])
            return
        verbatim = [v for v in verbatim if v]
        lines = []
        for line in (message or "").splitlines():
            if any(v in line for v in verbatim):
                lines.append(line)
            else:
                cleaned = strip_banned(line)
                if cleaned or not line.strip():
                    lines.append(cleaned)
        core = "\n".join(lines).strip()
        if not core:
            log.warning("Paylaşım süzgeç sonrası boş kaldı; atlandı: %s", (message or "")[:60])
            return
        masked = core
        for v in verbatim:
            masked = masked.replace(v, "")
        # Tavsiye/yasaklı kalıp denetimi maskelenmiş (birebir kısmı çıkarılmış) metne; dil ve uzunluk
        # denetimi tüm metne uygulanır.
        violations = [v for v in validate_tweet(masked) if "Türkçe değil" not in v and "karakteri aşıyor" not in v]
        violations += [v for v in validate_tweet(core) if "Türkçe değil" in v or "karakteri aşıyor" in v]
        if not allow("sosyal paylaşım", violations):
            return

        state = get_state()
        if state.get_daily_post_count() >= settings.max_posts_per_day:
            log.warning(
                "Günlük paylaşım tavanına ulaşıldı (%d); atlandı.",
                settings.max_posts_per_day,
            )
            return

        sent = self.post_telegram(prepare_post(core, disclaimer, filtered=True), image_path)
        if sent:
            state.increment_daily_post_count()

    def broadcast_thread(self, tweets: list[str],
                         image_path: Path | None = None, disclaimer: str | None = None) -> None:
        """Uzun içerikleri (sabah bülteni, haftalık özet) Telegram'a gönderir.

        Tüm parçaları birleşik tek mesaj olarak iletir.
        Twitter thread'i manuel olarak paylaşılır.
        """
        if settings.paused or not tweets:
            return
        parts = [p for p in (strip_banned(t) for t in tweets) if p]
        if not parts:
            return
        if not allow("sosyal paylaşım (thread)", validate_tweet(parts[0])):
            return

        state = get_state()
        if state.get_daily_post_count() >= settings.max_posts_per_day:
            log.warning("Günlük tavan; thread atlandı.")
            return

        tg_text = prepare_post("\n\n".join(parts), disclaimer, filtered=True)
        sent = self.post_telegram(tg_text, image_path)
        if sent:
            state.increment_daily_post_count()
