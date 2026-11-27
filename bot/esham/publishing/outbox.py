"""Telegram giden kutusu (outbox) — önce doğrula, sonra commit/push, EN SON gönder.

Neden: Bot eskiden Telegram'a koşu adımının içinde gönderiyordu. Yayın kapısı (web testleri) veya push
başarısız olunca rapor siteye girmiyor, durum dosyası da commit'lenmediği için aynı bildirim sonraki
koşuda yeniden işlenip Telegram'a YENİDEN gidiyordu (PR #31 incelemesi; PR #28'in "gönderildi, push
başarısız, yeniden gönderildi" kalıntısı).

Yeni akış (``.github/workflows/esham-schedule.yml``):

1. Bot koşusu HİÇBİR ŞEY göndermez. ``SocialPublisher.broadcast`` her mesajı bu dosyaya ``pending``
   kaydı olarak yazar (``bot/state/telegram_outbox.json``; durumla birlikte commit'lenir).
2. Yayın kapısı geçer → raporlar + durum + giden kutusu commit + push.
3. Push başarılıysa ayrı adım: ``send-outbox --phase claim`` bekleyen kayıtları ``in_flight`` yapar ve bu
   işaret commit + push edilir (önce-yaz / write-ahead). ANCAK bundan sonra ``--phase deliver`` gönderir
   ve her kaydı ``sent`` / ``pending`` (kesin ret, sınırlı yeniden deneme) / ``unknown`` (belirsiz)
   olarak işaretler; sonuç ikinci küçük commit ile push edilir.

Teslim garantisi: Telegram'a EN FAZLA BİR KEZ (at-most-once). Kayıt anahtarı (``key``) idempotans
anahtarıdır; aynı anahtar ikinci kez kuyruğa giremez. Gönderimden ÖNCE ``in_flight`` işareti origin'e
yazılmış olduğundan "gönderildi ama 'gönderildi' kaydı push edilemedi / iş çöktü" durumunda sonraki koşu
kaydı ``in_flight`` (başka koşuya ait) görür ve ``unknown`` yapar: YENİDEN GÖNDERMEZ. Tekrar eden gönderi
yerine kaçan gönderi tercih edilir. Kesin ret (Telegram HTTP 4xx yanıtı, bağlantı hiç kurulamadı) dışındaki
her hata belirsiz sayılır ve yeniden denenmez.

Yerel/elle kullanım: ``python -m esham.main --send-now <komut>`` komuttan sonra giden kutusunu hemen
gönderir; ``python -m esham.main send-outbox`` bekleyenleri gönderir (git işlemi yapmaz).
"""
from __future__ import annotations

import contextlib
import contextvars
import hashlib
import json
import os
import re
import shutil
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator, Protocol, Sequence

from ..config import PROJECT_ROOT, get_logger, settings
from ..neutral import NOTE_GENERIC, NOTE_KAP, find_banned

log = get_logger(__name__)

OUTBOX_VERSION = 1
#: Kesin retle (Telegram HTTP 4xx) başarısız gönderim en fazla bu kadar denenir; sonra ``failed``.
MAX_SEND_ATTEMPTS = 3
#: Bu süreden eski bekleyen kayıt gönderilmez (``expired``): bayat haber kanala düşmesin.
MAX_PENDING_AGE_SECONDS = 6 * 3600
#: Son durumdaki (gönderildi/başarısız/...) kayıtlar bu süre tutulur (idempotans penceresi), sonra budanır.
RETENTION_SECONDS = 14 * 24 * 3600

PENDING = "pending"
IN_FLIGHT = "in_flight"
SENT = "sent"
FAILED = "failed"        # kesin ret, deneme sınırı doldu
UNKNOWN = "unknown"      # gönderilmiş olabilir; ASLA yeniden gönderilmez
EXPIRED = "expired"      # bekleme süresi doldu
SKIPPED = "skipped"      # kimlik bilgisi yok (dry-run): gönderilmedi, sonra da gönderilmez
BLOCKED = "blocked"      # gönderim öncesi tarafsız dil/uyarı denetimine takıldı
TERMINAL = {SENT, FAILED, UNKNOWN, EXPIRED, SKIPPED, BLOCKED}

#: Telegram gönderisinin sonunda bulunması gereken uyarı satırları (tek kaynak: neutral-rules.json).
KNOWN_DISCLAIMERS = (NOTE_KAP, NOTE_GENERIC)

_LINK_RE = re.compile(r"/rapor/([A-Za-z0-9][A-Za-z0-9\-]*)")
_SAFE_RE = re.compile(r"[^A-Za-z0-9_.-]+")

_PROCESS_RUN_ID = f"local-{uuid.uuid4().hex[:12]}"
_context: contextvars.ContextVar[dict] = contextvars.ContextVar("esham_outbox_context", default={})


def current_run_id() -> str:
    """Bu koşunun kimliği: GitHub Actions'ta ``<run_id>-<attempt>``, yerelde süreç başına rastgele."""
    run = os.getenv("GITHUB_RUN_ID")
    if run:
        return f"{run}-{os.getenv('GITHUB_RUN_ATTEMPT', '1')}"
    return _PROCESS_RUN_ID


def outbox_path() -> Path:
    override = os.getenv("ESHAM_OUTBOX_FILE")
    return Path(override) if override else settings.state_file.parent / "telegram_outbox.json"


@contextlib.contextmanager
def outbox_context(**meta: Any) -> Iterator[None]:
    """Bu blokta kuyruğa giren mesajlara kaynak bilgisini (``kap_index``, ``source_key``, ``kind``) ekler.

    Üretici kodu (pipeline) değişmeden mesajın hangi bildirime ait olduğu bilinir.
    """
    token = _context.set({**_context.get(), **{k: v for k, v in meta.items() if v not in (None, "")}})
    try:
        yield
    finally:
        _context.reset(token)


def validate_post(text: str, disclaimer: str, verbatim: Sequence[str] = ()) -> list[str]:
    """Gönderi metni denetimi (kuyruğa girerken VE gönderim öncesi tekrar).

    - Birebir kaynak alıntıları (KAP başlığı vb.) çıkarıldıktan sonra yasaklı kalıp olmamalı,
    - uyarı satırı (``disclaimer``) boş olmamalı ve metinde bulunmalı.
    """
    problems: list[str] = []
    if not (text or "").strip():
        problems.append("boş metin")
    if not disclaimer or disclaimer not in (text or ""):
        problems.append("uyarı satırı yok")
    masked = text or ""
    for v in verbatim:
        if v:
            masked = masked.replace(v, "")
    if disclaimer:
        masked = masked.replace(disclaimer, "")
    banned = find_banned(masked)
    if banned:
        problems.append("yasaklı kalıp: " + ", ".join(sorted(set(banned))))
    return problems


# ---- taşıma katmanı ------------------------------------------------------------------------------

@dataclass
class SendResult:
    #: sent | retryable (kesin ret: gitmedi) | ambiguous (gitmiş olabilir) | dry_run (kimlik yok)
    outcome: str
    message_id: str = ""
    error: str = ""


class Transport(Protocol):
    def send(self, text: str, image_path: Path | None = None) -> SendResult: ...


class TelegramTransport:
    """Gerçek Telegram Bot API taşıması. Testlerde sahte taşıma kullanılır (ağ yok)."""

    def __init__(self, token: str | None = None, chat_id: str | None = None, timeout: int | None = None) -> None:
        self.token = token if token is not None else settings.telegram_bot_token
        self.chat_id = chat_id if chat_id is not None else settings.telegram_chat_id
        self.timeout = timeout or settings.http_timeout

    @property
    def configured(self) -> bool:
        return bool(self.token and self.chat_id)

    def _post(self, text: str, image_path: Path | None, parse_mode: str | None):
        import requests

        base = f"https://api.telegram.org/bot{self.token}"
        if image_path and image_path.exists():
            data = {"chat_id": self.chat_id, "caption": text[:1024]}
            if parse_mode:
                data["parse_mode"] = parse_mode
            with open(image_path, "rb") as f:
                return requests.post(f"{base}/sendPhoto", data=data, files={"photo": f}, timeout=self.timeout)
        payload = {"chat_id": self.chat_id, "text": text[:4096]}
        if parse_mode:
            payload["parse_mode"] = parse_mode
        return requests.post(f"{base}/sendMessage", json=payload, timeout=self.timeout)

    def send(self, text: str, image_path: Path | None = None) -> SendResult:
        import requests

        if not self.configured:
            log.info("[DRY-RUN][Telegram] %s", text[:100])
            return SendResult("dry_run")
        try:
            resp = self._post(text, image_path, "Markdown")
            if resp.status_code == 400 and "parse" in resp.text.lower():
                # Markdown ayrıştırma hatası: ileti GİTMEDİ (kesin ret) → aynı denemede düz metin.
                resp = self._post(text, image_path, None)
        except requests.exceptions.ConnectTimeout as exc:
            return SendResult("retryable", error=f"bağlantı kurulamadı: {type(exc).__name__}")
        except requests.exceptions.RequestException as exc:
            # Okuma zaman aşımı / bağlantı kopması: ileti gitmiş olabilir → yeniden DENENMEZ.
            return SendResult("ambiguous", error=type(exc).__name__)
        except OSError as exc:
            return SendResult("retryable", error=f"görsel okunamadı: {exc}")
        if 200 <= resp.status_code < 300:
            try:
                mid = str(resp.json().get("result", {}).get("message_id", ""))
            except ValueError:
                mid = ""
            return SendResult("sent", message_id=mid)
        if 400 <= resp.status_code < 500:
            # Telegram açıkça reddetti (429 dahil): ileti gitmedi.
            return SendResult("retryable", error=f"HTTP {resp.status_code}")
        return SendResult("ambiguous", error=f"HTTP {resp.status_code}")


# ---- giden kutusu --------------------------------------------------------------------------------

class Outbox:
    """``bot/state/telegram_outbox.json``: ``{"version": 1, "entries": [ ... ]}``.

    Kayıt alanları: ``key`` (idempotans anahtarı), ``status``, ``text`` (uyarı satırı dahil, gönderilecek
    metnin AYNISI), ``disclaimer``, ``verbatim`` (denetimde maskelenen birebir alıntılar), ``image``
    (yerel kopya, ``outbox_media/``; commit'lenmez), ``image_card`` (repo içindeki kalıcı kart yolu, varsa),
    ``slug``, ``kap_index``, ``source_key``, ``kind``, ``created_at``, ``created_run``, ``claim_run``,
    ``attempts``, ``last_error``, ``sent_at``, ``message_id``.
    """

    def __init__(self, path: Path | None = None, clock=time.time) -> None:
        self.path = path or outbox_path()
        self.clock = clock
        self.entries: list[dict] = self._load()

    # -- dosya --
    def _load(self) -> list[dict]:
        if not self.path.exists():
            return []
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            # Bozuk dosyada sessizce sıfırlanırsa idempotans kaybolur → çift gönderi riski. Durdur.
            raise RuntimeError(f"Giden kutusu okunamadı ({self.path}): {exc}") from exc
        return list(data.get("entries", []))

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(
            json.dumps({"version": OUTBOX_VERSION, "entries": self.entries}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        tmp.replace(self.path)

    @property
    def media_dir(self) -> Path:
        return self.path.parent / "outbox_media"

    def get(self, key: str) -> dict | None:
        return next((e for e in self.entries if e.get("key") == key), None)

    def by_status(self, *statuses: str) -> list[dict]:
        return [e for e in self.entries if e.get("status") in statuses]

    # -- kuyruğa alma --
    def make_key(self, text: str, meta: dict) -> str:
        if meta.get("key"):
            return str(meta["key"])
        index = str(meta.get("kap_index") or "")
        if index:
            kind = meta.get("kind") or "kap"
            return f"kap:{index}" if kind == "kap" else f"kap:{index}:{kind}"
        slug = meta.get("slug")
        if slug:
            return f"rapor:{slug}"
        day = time.strftime("%Y-%m-%d", time.gmtime(self.clock()))
        from ..neutral import normalize

        digest = hashlib.sha256(f"{day}|{normalize(text)}".encode("utf-8")).hexdigest()[:20]
        return f"text:{day}:{digest}"

    def enqueue(
        self,
        text: str,
        image_path: Path | None = None,
        *,
        disclaimer: str,
        verbatim: Sequence[str] = (),
        **meta: Any,
    ) -> dict | None:
        """Gönderiyi kuyruğa alır. Denetimden geçmezse veya aynı anahtar zaten varsa None."""
        problems = validate_post(text, disclaimer, verbatim)
        if problems:
            log.error("Telegram gönderisi giden kutusuna alınmadı (%s): %s", "; ".join(problems), text[:80])
            return None
        meta = {**_context.get(), **{k: v for k, v in meta.items() if v not in (None, "")}}
        m = _LINK_RE.search(text)
        if m and not meta.get("slug"):
            meta["slug"] = m.group(1)
        key = self.make_key(text, meta)
        existing = self.get(key)
        if existing is not None:
            log.info("Giden kutusu: '%s' zaten kayıtlı (durum=%s); ikinci kez kuyruğa alınmadı.",
                     key, existing.get("status"))
            return None
        entry: dict[str, Any] = {
            "key": key,
            "status": PENDING,
            "kind": meta.get("kind") or "post",
            "slug": meta.get("slug") or "",
            "kap_index": str(meta.get("kap_index") or ""),
            "source_key": meta.get("source_key") or "",
            "text": text,
            "disclaimer": disclaimer,
            "verbatim": [v for v in verbatim if v],
            "image": "",
            "image_card": "",
            "created_at": self.clock(),
            "created_run": current_run_id(),
            "claim_run": "",
            "attempts": 0,
            "last_error": "",
            "sent_at": None,
            "message_id": "",
        }
        entry["image"], entry["image_card"] = self._keep_image(image_path, key, entry["slug"])
        self.entries.append(entry)
        self.save()
        log.info("Telegram gönderisi giden kutusuna alındı: %s", key)
        return entry

    def _keep_image(self, image_path: Path | None, key: str, slug: str) -> tuple[str, str]:
        """Geçici kart dosyası koşu sonunda silinir; gönderim adımı için yerel kopya alınır."""
        card = ""
        if slug:
            candidate = settings.cards_dir / f"{slug}.png"
            if candidate.exists():
                try:
                    card = candidate.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix()
                except ValueError:
                    card = str(candidate)
        if not image_path or not Path(image_path).exists():
            return "", card
        try:
            self.media_dir.mkdir(parents=True, exist_ok=True)
            dest = self.media_dir / f"{_SAFE_RE.sub('_', key)}{Path(image_path).suffix or '.png'}"
            shutil.copy(image_path, dest)
            return dest.name, card
        except OSError as exc:
            log.warning("Gönderi görseli giden kutusuna kopyalanamadı (%s).", exc)
            return "", card

    def image_for(self, entry: dict) -> Path | None:
        if entry.get("image"):
            p = self.media_dir / entry["image"]
            if p.exists():
                return p
        if entry.get("image_card"):
            p = Path(entry["image_card"])
            p = p if p.is_absolute() else PROJECT_ROOT / p
            if p.exists():
                return p
        return None

    # -- gönderim --
    def claim(self, run_id: str | None = None) -> list[dict]:
        """Önce-yaz: bekleyenleri bu koşu adına ``in_flight`` yapar (dosyaya yazar, GÖNDERMEZ).

        Başka (bitmiş/çökmüş) bir koşunun ``in_flight`` kaydı ``unknown`` olur: gönderilmiş olabilir,
        yeniden gönderilmez.
        """
        run_id = run_id or current_run_id()
        now = self.clock()
        claimed: list[dict] = []
        for e in self.entries:
            if e["status"] == IN_FLIGHT and e.get("claim_run") != run_id:
                e["status"] = UNKNOWN
                e["last_error"] = f"önceki koşu ({e.get('claim_run')}) gönderim sonucunu kaydedemedi"
                log.warning("Giden kutusu: %s belirsiz (unknown); at-most-once gereği yeniden gönderilmez.", e["key"])
            elif e["status"] == PENDING:
                if now - float(e.get("created_at") or 0) > MAX_PENDING_AGE_SECONDS:
                    e["status"] = EXPIRED
                    log.warning("Giden kutusu: %s bayatladı (expired); gönderilmeyecek.", e["key"])
                    continue
                e["status"] = IN_FLIGHT
                e["claim_run"] = run_id
                e["claimed_at"] = now
                claimed.append(e)
        self.prune()
        self.save()
        return claimed

    def deliver(self, transport: Transport, run_id: str | None = None) -> dict[str, int]:
        """Bu koşunun ``in_flight`` kayıtlarını gönderir; her sonuçtan hemen sonra dosyaya yazar."""
        run_id = run_id or current_run_id()
        counts = {"sent": 0, "retry": 0, "failed": 0, "unknown": 0, "skipped": 0, "blocked": 0}
        for e in self.entries:
            if e["status"] != IN_FLIGHT or e.get("claim_run") != run_id:
                continue
            if settings.paused or self.sent_today() >= settings.max_posts_per_day:
                # Acil durdurma / günlük tavan: gönderme, beklet (süresi dolarsa expired). Hiç denenmedi.
                e["status"] = PENDING
                e["claim_run"] = ""
                self.save()
                continue
            problems = validate_post(e.get("text", ""), e.get("disclaimer", ""), e.get("verbatim", []))
            if problems:
                e["status"] = BLOCKED
                e["last_error"] = "; ".join(problems)
                counts["blocked"] += 1
                log.error("Giden kutusu: %s gönderilmedi (%s).", e["key"], e["last_error"])
                self.save()
                continue
            res = transport.send(e["text"], self.image_for(e))
            if res.outcome == "sent":
                e["status"] = SENT
                e["sent_at"] = self.clock()
                e["message_id"] = res.message_id
                counts["sent"] += 1
            elif res.outcome == "retryable":
                e["attempts"] = int(e.get("attempts", 0)) + 1
                e["last_error"] = res.error
                e["claim_run"] = ""
                if e["attempts"] >= MAX_SEND_ATTEMPTS:
                    e["status"] = FAILED
                    counts["failed"] += 1
                    log.error("Giden kutusu: %s %d denemede gönderilemedi (%s); bırakıldı.",
                              e["key"], e["attempts"], res.error)
                else:
                    e["status"] = PENDING
                    counts["retry"] += 1
                    log.warning("Giden kutusu: %s gönderilemedi (%s), deneme %d/%d; sonraki koşuda yeniden.",
                                e["key"], res.error, e["attempts"], MAX_SEND_ATTEMPTS)
            elif res.outcome == "dry_run":
                e["status"] = SKIPPED
                e["last_error"] = "Telegram kimlik bilgisi yok (dry-run)"
                counts["skipped"] += 1
            else:
                e["status"] = UNKNOWN
                e["last_error"] = res.error
                counts["unknown"] += 1
                log.error("Giden kutusu: %s gönderim sonucu belirsiz (%s); yeniden GÖNDERİLMEZ.", e["key"], res.error)
            self.save()
        return counts

    def drop_run(self, run_id: str | None = None) -> list[dict]:
        """Yayın kapısı kırıldı: bu koşunun (henüz hiç commit'lenmemiş) bekleyen kayıtlarını siler.

        Silinir (``dropped`` işaretlenmez): bildirim kapı düzelince yeniden yayınlanırsa aynı anahtarla
        tekrar kuyruğa girebilmelidir. Bu kayıtlar hiç gönderilmedi, origin'de de yok.
        """
        run_id = run_id or current_run_id()
        dropped = [e for e in self.entries if e.get("created_run") == run_id and e["status"] == PENDING]
        if dropped:
            keys = {e["key"] for e in dropped}
            self.entries = [e for e in self.entries if e["key"] not in keys]
            for e in dropped:
                self._remove_media(e)
            self.save()
        return dropped

    def prune(self) -> None:
        cutoff = self.clock() - RETENTION_SECONDS
        keep: list[dict] = []
        for e in self.entries:
            if e["status"] in TERMINAL:
                self._remove_media(e)
                if float(e.get("created_at") or 0) < cutoff:
                    continue
            keep.append(e)
        self.entries = keep

    def _remove_media(self, e: dict) -> None:
        name = e.get("image")
        if not name:
            return
        p = self.media_dir / name
        try:
            if p.is_file():
                p.unlink()
        except OSError:
            pass

    def sent_today(self) -> int:
        day = time.strftime("%Y-%m-%d", time.gmtime(self.clock()))
        return sum(
            1 for e in self.entries
            if e.get("sent_at") and time.strftime("%Y-%m-%d", time.gmtime(float(e["sent_at"]))) == day
        )


def send_outbox(phase: str = "all", transport: Transport | None = None, path: Path | None = None) -> dict:
    """``claim`` | ``deliver`` | ``all``. İş akışı claim ile deliver arasında commit + push yapar."""
    box = Outbox(path)
    result: dict[str, Any] = {}
    if phase in ("claim", "all"):
        result["claimed"] = len(box.claim())
    if phase in ("deliver", "all"):
        result.update(box.deliver(transport or TelegramTransport()))
    return result
