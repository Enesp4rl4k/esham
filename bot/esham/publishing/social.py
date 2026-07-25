"""Sosyal medya yayıncısı — sadece Telegram.

Twitter/X paylaşımları manuel olarak yapılır.
Bot yalnızca Telegram kanalına otomatik yayın yapar.
"""
from __future__ import annotations

from pathlib import Path

import requests

from ..config import get_logger, settings
from ..guardrails import allow, validate_tweet
from ..state import get_state

log = get_logger(__name__)


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

    def broadcast(self, message: str, image_path: Path | None = None) -> None:
        """Telegram'a yayın yapar. Guardrail + günlük tavan kontrolü yapar.

        Twitter paylaşımı bu fonksiyonla yapılmaz — manuel olarak yapılır.
        """
        if settings.paused:
            log.info("[PAUSED] Paylaşım atlandı: %s", message[:60])
            return
        if not allow("sosyal paylaşım", validate_tweet(message)):
            return

        state = get_state()
        if state.get_daily_post_count() >= settings.max_posts_per_day:
            log.warning(
                "Günlük paylaşım tavanına ulaşıldı (%d); atlandı.",
                settings.max_posts_per_day,
            )
            return

        sent = self.post_telegram(message, image_path)
        if sent:
            state.increment_daily_post_count()

    def broadcast_thread(self, tweets: list[str],
                         image_path: Path | None = None) -> None:
        """Uzun içerikleri (sabah bülteni, haftalık özet) Telegram'a gönderir.

        Tüm parçaları birleşik tek mesaj olarak iletir.
        Twitter thread'i manuel olarak paylaşılır.
        """
        if settings.paused or not tweets:
            return
        if not allow("sosyal paylaşım (thread)", validate_tweet(tweets[0])):
            return

        state = get_state()
        if state.get_daily_post_count() >= settings.max_posts_per_day:
            log.warning("Günlük tavan; thread atlandı.")
            return

        tg_text = "\n\n".join(tweets)
        sent = self.post_telegram(tg_text, image_path)
        if sent:
            state.increment_daily_post_count()
