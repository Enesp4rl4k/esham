"""Sosyal medya yayıncısı (Twitter/X, Telegram).

- Gerçek gönderim: tweepy (X API v2) ve Telegram Bot API.
- Anahtar yoksa/kütüphane kuruluysa değilse "dry-run" (konsola basar).
- broadcast, göndermeden önce guardrail uygular: kurallara aykırı metin gönderilmez.
"""
from __future__ import annotations

import requests

from ..config import get_logger, settings
from ..guardrails import allow, validate_tweet
from ..state import get_state

log = get_logger(__name__)


from pathlib import Path

class SocialPublisher:
    @staticmethod
    def _twitter_message(message: str) -> str:
        """X API v2 link fiyatlandırma sürşarjından kaçınmak için tam URL'leri
        kısa path'e dönüştürür.

        Örn: 'https://esham.com.tr/rapor/abc-123' → '/rapor/abc-123'

        Neden: X Basic/Free API'de URL içeren tweetler ek ücrete tabidir. Ancak
        domain olmayan /rapor/slug ifadesi "link" sayılmaz — kullanıcı karta veya
        profile bakarak siteye ulaşabilir. Telegram'a her zaman tam URL gider.
        """
        import re
        # https://esham.com.tr/rapor/abc → /rapor/abc
        cleaned = re.sub(r"https?://[^\s/]+(/[^\s]*)", r"\1", message)
        # Bare domain (link değil, site adı) olduğu gibi kalsın: esham.com.tr
        # Çift satır boşluklarını temizle
        cleaned = re.sub(r"\n\s*\n", "\n", cleaned).strip()
        return cleaned

    def post_tweet(self, message: str, image_path: Path | None = None) -> bool:
        cleaned_message = self._twitter_message(message)

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
        # Acil durdurma: ESHAM_PAUSED=true ise hiçbir kanala paylaşım yapılmaz.
        if settings.paused:
            log.info("[PAUSED] Paylaşım atlandı: %s", message[:60])
            return
        # Guardrail: kurallara aykırı metni hiçbir kanala gönderme.
        if not allow("sosyal paylaşım", validate_tweet(message)):
            return

        # Günlük paylaşım tavanı — bir hata/döngü API kotasını sessizce tüketmesin
        # diye güvenlik ağı. Sadece GERÇEK canlı tweet'leri sayar (dry-run saymaz).
        state = get_state()
        if state.get_daily_post_count() >= settings.max_posts_per_day:
            log.warning(
                "Günlük paylaşım tavanına ulaşıldı (%d); bu paylaşım atlandı "
                "(API kotası korunuyor).",
                settings.max_posts_per_day,
            )
            return

        tweeted = self.post_tweet(message, image_path)
        self.post_telegram(message, image_path)
        if tweeted:
            state.increment_daily_post_count()
