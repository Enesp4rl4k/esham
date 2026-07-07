"""Sosyal medya yayıncısı (Twitter/X, Telegram).

- Gerçek gönderim: tweepy (X API v2) ve Telegram Bot API.
- Anahtar yoksa/kütüphane kurulu değilse "dry-run" (konsola basar).
- broadcast      → tek tweet + Telegram
- broadcast_thread → sabah bülteni/haftalık özet gibi uzun içerikleri thread olarak at
"""
from __future__ import annotations

import re
import time
from pathlib import Path

import requests

from ..config import get_logger, settings
from ..guardrails import allow, validate_tweet
from ..state import get_state

log = get_logger(__name__)

# Thread tweet'leri arası bekleme (rate-limit önlemek için)
_THREAD_DELAY = 2.0


class SocialPublisher:

    @staticmethod
    def _twitter_message(message: str) -> str:
        """Tam URL'leri kısa path'e dönüştürür (X link sürşarjından kaçınmak için).

        Örn: 'https://esham.com.tr/rapor/abc-123' → '/rapor/abc-123'
        Telegram'a her zaman tam URL gider.
        """
        cleaned = re.sub(r"https?://[^\s/]+(/[^\s]*)", r"\1", message)
        cleaned = re.sub(r"\n\s*\n", "\n", cleaned).strip()
        return cleaned

    def post_tweet(self, message: str, image_path: Path | None = None,
                   reply_to_id: str | None = None) -> str | None:
        """Tweet gönderir. Başarılıysa tweet ID'sini döner (thread için), başarısızsa None."""
        cleaned_message = self._twitter_message(message)

        if not settings.twitter_api_key:
            log.info("[DRY-RUN][Twitter] %s", cleaned_message[:100])
            return "dry-run-id"
        try:
            import tweepy

            client = tweepy.Client(
                consumer_key=settings.twitter_api_key,
                consumer_secret=settings.twitter_api_secret,
                access_token=settings.twitter_access_token,
                access_token_secret=settings.twitter_access_secret,
            )

            media_ids = None
            if image_path and image_path.exists():
                auth = tweepy.OAuth1UserHandler(
                    settings.twitter_api_key, settings.twitter_api_secret,
                    settings.twitter_access_token, settings.twitter_access_secret
                )
                api = tweepy.API(auth)
                media = api.media_upload(filename=str(image_path))
                media_ids = [media.media_id]

            kwargs: dict = {"text": cleaned_message, "media_ids": media_ids}
            if reply_to_id and reply_to_id != "dry-run-id":
                kwargs["in_reply_to_tweet_id"] = reply_to_id

            resp = client.create_tweet(**kwargs)
            tweet_id = str(resp.data["id"]) if resp.data else None
            log.info("Tweet gönderildi (ID: %s, Görselli: %s)", tweet_id, bool(media_ids))
            return tweet_id
        except ImportError:
            log.warning("tweepy kurulu değil; tweet gönderilemedi.")
            return None
        except Exception as exc:
            log.error("Tweet gönderimi başarısız: %s", exc)
            return None

    def post_tweet_thread(self, tweets: list[str],
                          image_path: Path | None = None) -> list[str]:
        """Tweet listesini thread olarak gönderir.

        - İlk tweet isteğe bağlı görselle gönderilir.
        - Sonraki tweet'ler ilkine reply olarak zincir oluşturur.
        - Döner: gönderilen tweet ID listesi.

        Kullanım: sabah bülteni, haftalık özet gibi uzun raporlar için.
        """
        if not tweets:
            return []

        ids: list[str] = []
        reply_to: str | None = None

        for i, text in enumerate(tweets):
            img = image_path if i == 0 else None
            tweet_id = self.post_tweet(text, image_path=img, reply_to_id=reply_to)
            if tweet_id:
                ids.append(tweet_id)
                reply_to = tweet_id
            else:
                log.warning("Thread %d. tweet gönderilemedi; durdu.", i + 1)
                break
            if i < len(tweets) - 1:
                time.sleep(_THREAD_DELAY)

        log.info("Thread tamamlandı: %d/%d tweet.", len(ids), len(tweets))
        return ids

    def post_telegram(self, message: str, image_path: Path | None = None) -> bool:
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
        """Tek tweet + Telegram yayını. Guardrail + günlük tavan kontrolü yapar."""
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

        tweeted = self.post_tweet(message, image_path)
        self.post_telegram(message, image_path)
        if tweeted and tweeted != "dry-run-id":
            state.increment_daily_post_count()

    def broadcast_thread(self, tweets: list[str],
                         image_path: Path | None = None) -> None:
        """Tweet listesini thread olarak yayınlar (sabah bülteni, haftalık özet için).

        Guardrail + günlük tavan kontrolü yapar.
        Telegram'a tüm tweet'leri birleşik tek mesaj olarak gönderir.
        """
        if settings.paused or not tweets:
            return
        if not allow("sosyal paylaşım (thread)", validate_tweet(tweets[0])):
            return

        state = get_state()
        if state.get_daily_post_count() >= settings.max_posts_per_day:
            log.warning("Günlük tavan; thread atlandı.")
            return

        ids = self.post_tweet_thread(tweets, image_path=image_path)
        if ids and ids[0] != "dry-run-id":
            state.increment_daily_post_count()

        # Telegram'a birleşik mesaj
        tg_text = "\n\n".join(tweets)
        self.post_telegram(tg_text, image_path)
