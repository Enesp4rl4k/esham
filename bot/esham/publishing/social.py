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


from pathlib import Path

class SocialPublisher:
    def post_tweet(self, message: str, image_path: Path | None = None) -> bool:
        import re
        # X API v2 link fiyatlandırma sürşarjından kaçınmak için linkleri kaldırıyoruz.
        cleaned_message = re.sub(r"https?://[^\s]+", "", message).strip()
        # Çift satır boşluklarını temizle
        cleaned_message = re.sub(r"\n\s*\n", "\n", cleaned_message)

        if not settings.twitter_api_key:
            log.info("[DRY-RUN][Twitter] %s (Image: %s)", cleaned_message, image_path)
            return False
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

            client.create_tweet(text=cleaned_message, media_ids=media_ids)
            log.info("Tweet gönderildi. (Görselli: %s)", bool(media_ids))
            return True
        except ImportError:
            log.warning("tweepy kurulu değil; tweet gönderilemedi. `pip install tweepy`.")
            return False
        except Exception as exc:
            log.error("Tweet gönderimi başarısız: %s", exc)
            return False

    def post_telegram(self, message: str, image_path: Path | None = None) -> bool:
        if not (settings.telegram_bot_token and settings.telegram_chat_id):
            log.info("[DRY-RUN][Telegram] %s (Image: %s)", message, image_path)
            return False
        try:
            if image_path and image_path.exists():
                url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendPhoto"
                with open(image_path, "rb") as f:
                    resp = requests.post(
                        url,
                        data={
                            "chat_id": settings.telegram_chat_id,
                            "caption": message,
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
                        "text": message,
                        "parse_mode": "Markdown",
                    },
                    timeout=settings.http_timeout,
                )
            resp.raise_for_status()
            log.info("Telegram gönderimi başarılı. (Görselli: %s)", bool(image_path and image_path.exists()))
            return True
        except requests.RequestException as exc:
            log.error("Telegram gönderimi başarısız: %s", exc)
            return False

    def broadcast(self, message: str, image_path: Path | None = None) -> None:
        # Guardrail: kurallara aykırı metni hiçbir kanala gönderme.
        if not allow("sosyal paylaşım", validate_tweet(message)):
            return
        self.post_tweet(message, image_path)
        self.post_telegram(message, image_path)
