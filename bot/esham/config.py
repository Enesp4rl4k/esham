"""Merkezi konfigürasyon ve loglama.

Tüm ayarlar ortam değişkenlerinden okunur (.env üzerinden). Böylece sırlar koda
gömülmez ve dağıtım ortamına göre değişebilir.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# bot/esham/config.py -> proje kökü iki üst dizin
PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _default_content_dir() -> Path:
    """Web'in okuduğu rapor klasörü. Bot ile web arasındaki tek sözleşme burası."""
    override = os.getenv("ESHAM_CONTENT_DIR")
    if override:
        return Path(override)
    return PROJECT_ROOT / "web" / "content" / "reports"


@dataclass(frozen=True)
class Settings:
    gemini_api_key: str | None = field(default_factory=lambda: os.getenv("GEMINI_API_KEY"))
    # Derin analiz/sabah raporu modeli. Varsayılan flash: ücretsiz tier'da çalışır ve
    # yeterince güçlü. Paralı tier'da ESHAM_GEMINI_MODEL=gemini-2.5-pro ile yükseltilebilir.
    gemini_model: str = field(
        default_factory=lambda: os.getenv("ESHAM_GEMINI_MODEL", "gemini-2.5-flash")
    )
    # Anlık tweet özetleri için ucuz/hızlı model. Yüksek hacimli çağrılarda maliyeti
    # düşürmek için en küçük katman kullanılır.
    tweet_model: str = field(
        default_factory=lambda: os.getenv("ESHAM_TWEET_MODEL", "gemini-2.5-flash-lite")
    )

    twitter_api_key: str | None = field(default_factory=lambda: os.getenv("TWITTER_API_KEY"))
    twitter_api_secret: str | None = field(
        default_factory=lambda: os.getenv("TWITTER_API_SECRET")
    )
    twitter_access_token: str | None = field(
        default_factory=lambda: os.getenv("TWITTER_ACCESS_TOKEN")
    )
    twitter_access_secret: str | None = field(
        default_factory=lambda: os.getenv("TWITTER_ACCESS_SECRET")
    )
    telegram_bot_token: str | None = field(
        default_factory=lambda: os.getenv("TELEGRAM_BOT_TOKEN")
    )
    telegram_chat_id: str | None = field(
        default_factory=lambda: os.getenv("TELEGRAM_CHAT_ID")
    )

    site_url: str = field(
        default_factory=lambda: os.getenv("ESHAM_SITE_URL", "https://esham.com.tr")
    )
    # Takasbank VİOP agregat teminat verisi (opsiyonel; boşsa gerçekçi örnek kullanılır).
    takasbank_viop_url: str | None = field(
        default_factory=lambda: os.getenv("ESHAM_TAKASBANK_VIOP_URL")
    )
    content_dir: Path = field(default_factory=_default_content_dir)
    ipo_output_dir: Path = field(
        default_factory=lambda: PROJECT_ROOT / "bot" / "output" / "ipo_reports"
    )
    http_timeout: int = field(default_factory=lambda: int(os.getenv("ESHAM_HTTP_TIMEOUT", "15")))
    log_level: str = field(default_factory=lambda: os.getenv("ESHAM_LOG_LEVEL", "INFO"))
    # Yayın öncesi guardrail modu: enforce (blokla) | warn (uyar, yayınla) | off
    guardrails_mode: str = field(
        default_factory=lambda: os.getenv("ESHAM_GUARDRAILS", "enforce").lower()
    )

    # Anlık akış: tarama ile yayın hızını ayırır (drip servis).
    news_scan_interval: int = field(
        default_factory=lambda: int(os.getenv("ESHAM_NEWS_SCAN_INTERVAL", "300"))
    )
    news_publish_interval: int = field(
        default_factory=lambda: int(os.getenv("ESHAM_NEWS_PUBLISH_INTERVAL", "90"))
    )
    news_queue_max: int = field(
        default_factory=lambda: int(os.getenv("ESHAM_NEWS_QUEUE_MAX", "200"))
    )

    @property
    def ai_enabled(self) -> bool:
        return bool(self.gemini_api_key)


settings = Settings()

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
}


def default_headers() -> dict[str, str]:
    return dict(_HEADERS)


_configured = False


def configure_logging() -> None:
    """Uygulama loglamasını bir kez yapılandırır."""
    global _configured
    if _configured:
        return
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%H:%M:%S",
    )
    _configured = True


def get_logger(name: str) -> logging.Logger:
    configure_logging()
    return logging.getLogger(name)
