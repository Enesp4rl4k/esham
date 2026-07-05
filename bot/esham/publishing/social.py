"""Sosyal medya yayıncısı (Twitter/X, Telegram).

- Gerçek gönderim: tweepy (X API v2) ve Telegram Bot API.
- Anahtar yoksa/kütüphane kuruluysa değilse "dry-run" (konsola basar).
- broadcast, göndermeden önce guardrail uygular: kurallara aykırı metin gönderilmez.
"""
from __future__ import annotations

import requests

from ..config import get_logger, settings
from ..guardrails import allow, validate_tweet

log = get_logger(__name__)


class SocialPublisher:
    def post_tweet(self, message: str) -> bool:
        if not settings.twitter_api_key:
            log.info("[DRY-RUN][Twitter] %s", message)
            return False
        try:
            import tweepy

            client = tweepy.Client(
                consumer_key=settings.twitter_api_key,
                consumer_secret=settings.twitter_api_secret,
                access_token=settings.twitter_access_token,
                access_token_secret=settings.twitter_access_secret,
            )
            client.create_tweet(text=message)
            log.info("Tweet gönderildi.")
            return True
        except ImportError:
            log.warning("tweepy kurulu değil; tweet gönderilemedi. `pip install tweepy`.")
            return False
        except Exception as exc:
            log.error("Tweet gönderimi başarısız: %s", exc)
            return False

    def post_telegram(self, message: str) -> bool:
        if not (settings.telegram_bot_token and settings.telegram_chat_id):
            log.info("[DRY-RUN][Telegram] %s", message)
            return False
        try:
            url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
            resp = requests.post(
                url,
                json={
                    "chat_id": settings.telegram_chat_id,
                    "text": message,
                    "parse_mode": "Markdown",
                },
                timeout=settings.http_timeout,
            )
            resp.raise_for_status()
            log.info("Telegram gönderimi başarılı.")
            return True
        except requests.RequestException as exc:
            log.error("Telegram gönderimi başarısız: %s", exc)
            return False

    def broadcast(self, message: str) -> None:
        # Guardrail: kurallara aykırı metni hiçbir kanala gönderme.
        if not allow("sosyal paylaşım", validate_tweet(message)):
            return
        self.post_tweet(message)
        self.post_telegram(message)
