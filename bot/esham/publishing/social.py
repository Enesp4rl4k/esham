"""Sosyal medya yayıncısı — sadece Telegram.

Twitter/X paylaşımları manuel olarak yapılır.
Bot yalnızca Telegram kanalına otomatik yayın yapar.

Her gönderi: (1) yasaklı piyasa yargısı/tavsiye kalıplarından deterministik olarak süzülür,
(2) guardrail'dan geçer, (3) sonuna "yatırım tavsiyesi değildir" uyarısı eklenir.

ÖNEMLİ: ``broadcast``/``broadcast_thread`` artık DOĞRUDAN GÖNDERMEZ. Gönderi giden kutusuna
(``publishing/outbox.py``, ``bot/state/telegram_outbox.json``) yazılır; iş akışı raporlar yayın kapısından
geçip master'a push edildikten SONRA ``python -m esham.main send-outbox`` ile gönderir. Yerelde hemen
göndermek için: ``python -m esham.main --send-now <komut>``.
"""
from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from ..config import get_logger, settings
from ..guardrails import allow, validate_tweet
from ..neutral import DISCLAIMER_GENERIC, strip_banned
from ..state import get_state
from .outbox import Outbox, TelegramTransport

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
        """Telegram'a DOĞRUDAN gönderir. Yalnız operasyonel uyarılar (scheduler) ve giden kutusu
        gönderici adımı kullanır; içerik gönderileri ``broadcast`` ile giden kutusuna gider."""
        result = TelegramTransport().send(message, image_path)
        if result.outcome == "sent":
            log.info("Telegram gönderildi.")
            return True
        if result.outcome != "dry_run":
            log.error("Telegram gönderimi başarısız: %s", result.error)
        return False

    def enqueue(
        self,
        message: str,
        image_path: Path | None = None,
        *,
        disclaimer: str | None = None,
        verbatim: Sequence[str] = (),
    ) -> bool:
        """Hazır (süzülmüş, uyarı satırlı) gönderiyi giden kutusuna yazar; yazıldıysa True."""
        entry = Outbox().enqueue(
            message, image_path, disclaimer=disclaimer or DISCLAIMER_GENERIC, verbatim=verbatim,
        )
        return entry is not None

    def broadcast(
        self,
        message: str,
        image_path: Path | None = None,
        disclaimer: str | None = None,
        verbatim: Sequence[str] = (),
    ) -> None:
        """Telegram gönderisini hazırlar ve giden kutusuna yazar. Süzgeç + guardrail + günlük tavan kontrolü.

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

        queued = self.enqueue(
            prepare_post(core, disclaimer, filtered=True), image_path,
            disclaimer=disclaimer or DISCLAIMER_GENERIC, verbatim=verbatim,
        )
        if queued:
            state.increment_daily_post_count()

    def broadcast_thread(self, tweets: list[str],
                         image_path: Path | None = None, disclaimer: str | None = None) -> None:
        """Uzun içerikleri (sabah bülteni, haftalık özet) tek Telegram gönderisi olarak giden kutusuna yazar.

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
        if self.enqueue(tg_text, image_path, disclaimer=disclaimer or DISCLAIMER_GENERIC):
            state.increment_daily_post_count()
