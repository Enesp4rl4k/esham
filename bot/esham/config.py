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


def _default_cards_dir() -> Path:
    """Üretilen marka kartlarının (tweet + web hero/OG için) yazıldığı statik klasör."""
    override = os.getenv("ESHAM_CARDS_DIR")
    if override:
        return Path(override)
    return PROJECT_ROOT / "web" / "public" / "cards"


def _safe_int(env_key: str, default: int) -> int:
    val = (os.getenv(env_key) or "").strip()
    try:
        return int(val) if val else default
    except (ValueError, TypeError):
        return default

def _default_state_file() -> Path:
    """Süreç yeniden başlasa da kaybolmaması gereken küçük durum dosyası (seen-set,
    margin-call önceki değer, günlük paylaşım sayacı, iş sağlığı)."""
    override = os.getenv("ESHAM_STATE_FILE")
    if override:
        return Path(override)
    return PROJECT_ROOT / "bot" / "state" / "esham_state.json"


def _default_subscriber_file() -> Path:
    """Bülten aboneleri — JSON listesi (eposta + katılım tarihi)."""
    override = os.getenv("ESHAM_SUBSCRIBER_FILE")
    if override:
        return Path(override)
    return PROJECT_ROOT / "bot" / "state" / "esham_subscribers.json"


@dataclass(frozen=True)
class Settings:
    gemini_api_key: str | None = field(default_factory=lambda: os.getenv("GEMINI_API_KEY"))
    # Derin analiz/sabah raporu modeli.
    gemini_model: str = field(
        default_factory=lambda: os.getenv("ESHAM_GEMINI_MODEL", "gemini-2.0-flash")
    )
    # Anlık tweet özetleri için ucuz/hızlı model.
    tweet_model: str = field(
        default_factory=lambda: os.getenv("ESHAM_TWEET_MODEL", "gemini-2.0-flash")
    )

    # DeepSeek — primary AI provider (ucuz + yuksek kalite, OpenAI uyumlu API)
    # platform.deepseek.com → API Keys
    # Modeller: deepseek-chat (V3, hizli/ucuz), deepseek-reasoner (R1, derin analiz)
    deepseek_api_key: str | None = field(default_factory=lambda: os.getenv("DEEPSEEK_API_KEY"))
    deepseek_model: str = field(
        default_factory=lambda: os.getenv("ESHAM_DEEPSEEK_MODEL", "deepseek-chat")
    )
    # deepseek-chat : hizli, ucuz, genel analiz + tweet icin ideal
    # deepseek-reasoner: R1 modeli, derin akil yurutme, uzun rapor analizi icin

    # Groq — ikinci fallback (ucretsiz tier: dakikada 30 istek)
    # console.groq.com → API Keys → ucretsiz kayit
    groq_api_key: str | None = field(default_factory=lambda: os.getenv("GROQ_API_KEY"))
    # Groq modeli — llama-3.3-70b-versatile kaliteli ve hizli, ücretsiz tier dahil
    groq_model: str = field(
        default_factory=lambda: os.getenv("ESHAM_GROQ_MODEL", "llama-3.3-70b-versatile")
    )
    # Groq tweet modeli — hizli ve ucuz
    groq_tweet_model: str = field(
        default_factory=lambda: os.getenv("ESHAM_GROQ_TWEET_MODEL", "llama-3.1-8b-instant")
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
        default_factory=lambda: os.getenv("ESHAM_SITE_URL", "https://esham.pages.dev")
    )
    # Kart footer'ında ve wordmark'ta gösterilen domain (site_url'den türetilir,
    # override için ESHAM_DISPLAY_DOMAIN kullanılır. Örn: "benimsite.com")
    display_domain: str = field(
        default_factory=lambda: os.getenv(
            "ESHAM_DISPLAY_DOMAIN",
            os.getenv("ESHAM_SITE_URL", "https://esham.com.tr")
            .removeprefix("https://")
            .removeprefix("http://")
            .rstrip("/"),
        )
    )
    # Kart wordmark'ında gösterilen marka adı (iki parça: accent renkli + beyaz)
    # Örn: brand_name_accent="Pi", brand_name_rest="yasaBot"
    brand_name_accent: str = field(
        default_factory=lambda: os.getenv("ESHAM_BRAND_ACCENT", "Es")
    )
    brand_name_rest: str = field(
        default_factory=lambda: os.getenv("ESHAM_BRAND_REST", "ham")
    )
    # Kart alt satırı tagline
    # Unsplash — genel haber kartları için otomatik fotoğraf arka plan
    # unsplash.com/developers → New Application → Access Key (ücretsiz, kredi kartı yok)
    unsplash_access_key: str | None = field(
        default_factory=lambda: os.getenv("UNSPLASH_ACCESS_KEY")
    )

    brand_tagline: str = field(
        default_factory=lambda: os.getenv(
            "ESHAM_BRAND_TAGLINE", "YAPAY ZEKA DESTEKLİ PİYASA ANALİZİ"
        )
    )
    # Takasbank VİOP agregat teminat verisi (opsiyonel; boşsa gerçekçi örnek kullanılır).
    takasbank_viop_url: str | None = field(
        default_factory=lambda: os.getenv("ESHAM_TAKASBANK_VIOP_URL")
    )
    content_dir: Path = field(default_factory=_default_content_dir)
    cards_dir: Path = field(default_factory=_default_cards_dir)
    ipo_output_dir: Path = field(
        default_factory=lambda: PROJECT_ROOT / "bot" / "output" / "ipo_reports"
    )
    http_timeout: int = field(default_factory=lambda: _safe_int("ESHAM_HTTP_TIMEOUT", 15))
    log_level: str = field(default_factory=lambda: os.getenv("ESHAM_LOG_LEVEL", "INFO"))
    # Yayın öncesi guardrail modu: enforce (blokla) | warn (uyar, yayınla) | off
    guardrails_mode: str = field(
        default_factory=lambda: os.getenv("ESHAM_GUARDRAILS", "enforce").lower()
    )

    # Anlık akış: tarama ile yayın hızını ayırır (drip servis).
    news_scan_interval: int = field(
        default_factory=lambda: _safe_int("ESHAM_NEWS_SCAN_INTERVAL", 300)
    )
    news_publish_interval: int = field(
        # 600 saniye = 10 dakikada bir yayın — dakikada max 6 AI isteği, kota koruma.
        # Yoğun KAP günlerinde (130+ bildirim) Groq/Gemini 429 riskini minimize eder.
        default_factory=lambda: _safe_int("ESHAM_NEWS_PUBLISH_INTERVAL", 600)
    )
    news_queue_max: int = field(
        default_factory=lambda: _safe_int("ESHAM_NEWS_QUEUE_MAX", 200)
    )
    # Genel KAP akışı için önem eşiği (insider/IPO bu filtreyi atlar, her zaman
    # önemli sayılır). Yükseltmek daha az/daha seçici paylaşım demektir.
    # 4: yüksek önem sinyalli bildirimler (temettü, birleşme, iflas, dava+iştirak vb.)
    #    Tek başına orta sinyaller (ihale=2, tahvil ihracı=2) geçemez; önem birikimleri geçer.
    # 3: daha geniş kapsam — yüksek 429 riski
    # 5: çok seçici — bazı gerçek önemli bildirimler kaçabilir
    kap_min_importance: int = field(
        default_factory=lambda: _safe_int("ESHAM_KAP_MIN_IMPORTANCE", 4)
    )

    state_file: Path = field(default_factory=_default_state_file)

    # ---- E-posta bülteni / abonelik ---------------------------------------
    # SMTP kimlik bilgileri verilmezse gönderim DRY-RUN olur (kayıt tutulur,
    # e-posta gitmez) — repo'nun zarif bozulma ilkesine uyar.
    smtp_host: str | None = field(default_factory=lambda: os.getenv("ESHAM_SMTP_HOST"))
    smtp_port: int = field(default_factory=lambda: _safe_int("ESHAM_SMTP_PORT", 587))
    smtp_user: str | None = field(default_factory=lambda: os.getenv("ESHAM_SMTP_USER"))
    smtp_password: str | None = field(default_factory=lambda: os.getenv("ESHAM_SMTP_PASSWORD"))
    # 465 → implicit TLS (SSL), diğerleri → STARTTLS
    smtp_use_ssl: bool = field(
        default_factory=lambda: os.getenv("ESHAM_SMTP_SSL", "false").lower() in ("1", "true", "yes")
    )
    email_from: str = field(
        default_factory=lambda: os.getenv("ESHAM_EMAIL_FROM", "Esham <bulten@esham.pages.dev>")
    )
    # Abone deposu (kalıcı) — Render disk kalıcı değilse en kötü durumda liste sıfırlanır.
    subscriber_file: Path = field(default_factory=_default_subscriber_file)
    # Abonelikten çıkış bağlantılarındaki imza tuzu (e-posta sızsa bile imzasız
    # çıkış yapılamaz). Verilmezse zayıf ama işleyen bir varsayılan kullanılır.
    unsubscribe_secret: str = field(
        default_factory=lambda: os.getenv("ESHAM_UNSUBSCRIBE_SECRET", "esham-default-secret")
    )
    # Tek bülten kaç rapor kapsın
    newsletter_limit: int = field(default_factory=lambda: _safe_int("ESHAM_NEWSLETTER_LIMIT", 6))
    # Abone sayısı tavanı (spam/kötü niyetli doldurma koruması)
    subscribers_max: int = field(default_factory=lambda: _safe_int("ESHAM_SUBSCRIBERS_MAX", 5000))

    # Acil durdurma: true ise hiçbir sosyal paylaşım/rapor yayını yapılmaz (dry-run
    # gibi davranır). Redeploy/restart ile değişir — anlık bir "panic switch" değil,
    # ama tek bir ortam değişkeniyle tüm otomasyonu durdurmaya yeter.
    paused: bool = field(
        default_factory=lambda: os.getenv("ESHAM_PAUSED", "false").lower() in ("1", "true", "yes")
    )
    # Günlük sosyal paylaşım tavanı — bir hata/döngü API kotasını tüketmesin diye
    # güvenlik ağı. Normal kullanımda asla dolmaz (varsayılan cömert).
    max_posts_per_day: int = field(
        default_factory=lambda: _safe_int("ESHAM_MAX_POSTS_PER_DAY", 60)
    )

    @property
    def ai_enabled(self) -> bool:
        return bool(self.deepseek_api_key or self.groq_api_key or self.gemini_api_key)

    @property
    def deepseek_enabled(self) -> bool:
        return bool(self.deepseek_api_key)

    @property
    def groq_enabled(self) -> bool:
        return bool(self.groq_api_key)

    @property
    def smtp_enabled(self) -> bool:
        """SMTP yapılandırmışsa gerçek gönderim; yoksa dry-run."""
        return bool(self.smtp_host and self.smtp_user and self.smtp_password)


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
