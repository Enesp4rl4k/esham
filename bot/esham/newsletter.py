"""E-posta bülteni — abone deposu + günlük özet (digest) gönderimi.

Üç parça:

1. `SubscriberStore` — kalıcı abone listesi (`bot/state/esham_subscribers.json`,
   atomik yazım). E-posta doğrular, tekrarı engeller, tavan uygular ve çıkış
   için **imzalı token** üretir (sha256(eposta + sır)) — liste sızsa bile
   imzasız çıkış yapılamaz.
2. `build_digest` — `web/content/reports/*.json` son raporlardan HTML + düz metin
   bülteni üretir (aynı köprü dosyalarını web gibi okur).
3. `send_digest` — SMTP ile toplu gönderir. SMTP **yapılandırılmamışsa**
   **dry-run**: gönderim loglanır, e-posta çıkmaz (zarif bozulma).

Web formu `POST /subscribe` (Render Flask, `render_app.py`) üzerinden bu depoya
yazar; çıkış `GET /unsubscribe?email=...&token=...` ile yapılır.
"""
from __future__ import annotations

import hashlib
import html
import json
import re
import smtplib
import ssl
from dataclasses import dataclass
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from .config import get_logger, settings
from .neutral import NOTE_GENERIC, is_legacy, legacy_summary, legacy_title, sanitize_summary

log = get_logger(__name__)

# Makul e-posta biçimi — pratik doğrulama (RFC tamamı değil, spam'i keser).
_EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")

# web/src/lib/content-utils.ts CATEGORIES ile aynı etiketler.
_CATEGORY_LABELS: dict[str, str] = {
    "bist": "BIST & Sektör",
    "global": "Küresel Makro",
    "ipo": "Halka Arz",
    "viop": "VİOP",
    "gundem": "Gündem",
    "kripto": "Kripto",
    "teknoloji": "Teknoloji",
}


def is_valid_email(email: str) -> bool:
    return bool(email and len(email) <= 254 and _EMAIL_RE.match(email.strip()))


@dataclass
class Subscriber:
    email: str
    added_at: str = ""  # ISO Z
    source: str = "web"  # web | manual | test


class SubscriberStore:
    """Kalıcı abone deposu — atomik yazım, doğrulama, tavan ve imzalı çıkış."""

    def __init__(
        self,
        path: Path | None = None,
        *,
        secret: str | None = None,
        max_subscribers: int | None = None,
    ) -> None:
        self.path = path or settings.subscriber_file
        self.secret = secret or settings.unsubscribe_secret
        self.max_subscribers = max_subscribers or settings.subscribers_max

    # ---- token ----------------------------------------------------------

    def token(self, email: str) -> str:
        """E-posta için imzalı çıkış token'ı (kayıtla aynı yolla üretilir)."""
        payload = f"{email.strip().lower()}|{self.secret}".encode("utf-8")
        return hashlib.sha256(payload).hexdigest()[:20]

    def verify_token(self, email: str, token: str) -> bool:
        return bool(token) and token == self.token(email)

    # ---- okuma/yazma ----------------------------------------------------

    def _load(self) -> list[Subscriber]:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return []
        except (OSError, json.JSONDecodeError) as exc:
            log.warning("Abone dosyası okunamadı (%s); boş listeyle devam.", exc)
            return []
        out: list[Subscriber] = []
        if isinstance(raw, list):
            for item in raw:
                if isinstance(item, dict) and item.get("email"):
                    out.append(
                        Subscriber(
                            email=str(item["email"]),
                            added_at=str(item.get("added_at", "")),
                            source=str(item.get("source", "web")),
                        )
                    )
                elif isinstance(item, str):
                    out.append(Subscriber(email=item))
        return out

    def _save(self, subs: list[Subscriber]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = [
            {"email": s.email, "added_at": s.added_at, "source": s.source}
            for s in subs
        ]
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        tmp.replace(self.path)  # atomik — yarı yazım yok

    # ---- işlemler -------------------------------------------------------

    def emails(self) -> list[str]:
        return [s.email for s in self._load()]

    def count(self) -> int:
        return len(self._load())

    def contains(self, email: str) -> bool:
        target = email.strip().lower()
        return any(s.email.lower() == target for s in self._load())

    def add(self, email: str, source: str = "web") -> tuple[bool, str]:
        """Abone ekler. Döndürür: (başarılı mı, insan-okunur mesaj)."""
        email = (email or "").strip()
        if not is_valid_email(email):
            return False, "Geçersiz e-posta adresi."
        subs = self._load()
        if any(s.email.lower() == email.lower() for s in subs):
            return True, "Zaten abonesiniz."  # idempotent — formda çifte mesaj yok
        if len(subs) >= self.max_subscribers:
            log.warning("Abone tavanı doldu (%d); ekleme reddedildi.", self.max_subscribers)
            return False, "Abone listesi geçici olarak dolu."
        subs.append(
            Subscriber(
                email=email,
                added_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                source=source,
            )
        )
        self._save(subs)
        log.info("Yeni abone: %s (toplam %d)", email, len(subs))
        return True, "Aboneliğiniz alındı. İlk bülten bir sonraki gönderimde ulaşacak."

    def remove(self, email: str) -> bool:
        """E-postayı listeden çıkarır (imza kontrolü çağıran tarafta yapılır)."""
        target = (email or "").strip().lower()
        subs = self._load()
        kept = [s for s in subs if s.email.lower() != target]
        if len(kept) == len(subs):
            return False
        self._save(kept)
        log.info("Abonelik sonlandırıldı: %s", email)
        return True


# ---- bülten içeriği -------------------------------------------------------


def _read_json(path: Path) -> dict | None:
    r"""JSON okur. Bazı rapor dosyalarının adı Windows MAX_PATH'ı (260) aşıyor;
    normal okuma başarısız olursa `\\?\` uzun yol öneki ile tekrar denenir."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        try:
            long_path = Path("\\\\?\\" + str(path.resolve()))
            return json.loads(long_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None


def latest_reports(limit: int | None = None) -> list[dict]:
    """Web'in okuduğu aynı klasörden en yeni raporları okur (başlık/özet/link).

    Dosya adı `YYYY-MM-DD-<slug>.json` biçiminde olduğu için alfabetik sıralama
    zaten tarihe göre sıralamadır — `stat()` kullanılmaz (uzun adlar MAX_PATH
    hatası verir).
    """
    limit = limit or settings.newsletter_limit
    files = sorted(settings.content_dir.glob("*.json"), reverse=True)
    reports: list[dict] = []
    for path in files:
        doc = _read_json(path)
        if not isinstance(doc, dict) or not doc.get("slug"):
            continue
        # Web ile AYNI görünüm kararı (neutral.is_legacy / legacy_title / legacy_summary): sürümsüz kayıtta
        # eski özet ve yorum taşıyan başlık gösterilmez.
        if is_legacy(doc):
            doc["summary"] = legacy_summary(doc)
            doc["title"] = legacy_title(doc)
        else:
            doc["summary"] = sanitize_summary(str(doc.get("summary", "")), str(doc.get("title", "")))
        reports.append(doc)
        if len(reports) >= limit:
            break
    return reports


def _date_tr(iso: str) -> str:
    try:
        dt = datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
        return dt.strftime("%d.%m.%Y")
    except (ValueError, TypeError):
        return ""


def build_digest(reports: list[dict]) -> tuple[str, str, str]:
    """`(konu, html, düz metin)` üretir. Raporda tavsiye yok; tümü zaten guardrail'den geçti."""
    today = datetime.now(timezone.utc).strftime("%d.%m.%Y")
    subject = f"Esham Günlük Bülten — {today} ({len(reports)} rapor)"

    items_html: list[str] = []
    items_text: list[str] = []
    for r in reports:
        slug = html.escape(str(r.get("slug", "")))
        link = f"{settings.site_url}/rapor/{slug}"
        title = html.escape(str(r.get("title", "")))
        summary = html.escape(str(r.get("summary", "")))
        label = _CATEGORY_LABELS.get(str(r.get("category", "")), "Esham")
        date = _date_tr(str(r.get("publishedAt", "")))
        items_html.append(
            f"""
      <tr><td style="padding:16px 0;border-bottom:1px solid #27272a;">
        <div style="font-size:11px;letter-spacing:.08em;text-transform:uppercase;color:#f59e0b;">
          {html.escape(label)}{(' · ' + date) if date else ''}
        </div>
        <a href="{link}" style="display:block;margin-top:6px;font-size:17px;font-weight:600;
           color:#fafafa;text-decoration:none;">{title}</a>
        <p style="margin:6px 0 0;font-size:14px;color:#a1a1aa;line-height:1.5;">{summary}</p>
        <a href="{link}" style="display:inline-block;margin-top:8px;font-size:13px;color:#22d3ee;
           text-decoration:none;">Raporu oku →</a>
      </td></tr>"""
        )
        items_text.append(f"• {r.get('title', '')}\n  {link}\n  {r.get('summary', '')}")

    if not items_html:
        items_html.append(
            '<tr><td style="padding:16px 0;color:#a1a1aa;font-size:14px;">'
            "Bu gönderimde yeni rapor yok.</td></tr>"
        )
        items_text.append("Bu gönderimde yeni rapor yok.")

    html_body = f"""<!doctype html>
<html lang="tr"><body style="margin:0;background:#0a0a0a;font-family:Arial,Helvetica,sans-serif;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
         style="background:#0a0a0a;padding:24px 12px;"><tr><td align="center">
    <table role="presentation" width="600" cellpadding="0" cellspacing="0"
           style="max-width:600px;width:100%;background:#111113;border:1px solid #27272a;
                  border-radius:14px;padding:28px;">
      <tr><td>
        <div style="font-size:22px;font-weight:bold;color:#f59e0b;">Es</div>
        <div style="display:inline;font-size:22px;font-weight:bold;color:#fafafa;">ham</div>
        <div style="font-size:11px;letter-spacing:.14em;text-transform:uppercase;color:#71717a;
             margin-top:6px;">Kamuya açık bildirim ve veri özetleri</div>
      </td></tr>
      <tr><td style="padding-top:18px;border-top:1px solid #27272a;margin-top:18px;">
        {''.join(items_html)}
      </td></tr>
      <tr><td style="padding-top:20px;font-size:12px;color:#71717a;line-height:1.6;
              border-top:1px solid #27272a;margin-top:8px;">
        Bu e-posta Esham'ın günlük otomatik gönderimidir. {html.escape(NOTE_GENERIC)}<br>
        Abonelikten çıkmak için:
        <a href="{settings.site_url}" style="color:#a1a1aa;">bülten sayfası</a>
        veya iletişime geçin.
      </td></tr>
    </table>
  </td></tr></table>
</body></html>"""

    text_body = (
        f"Esham Günlük Bülten — {today}\n{'=' * 40}\n\n"
        + "\n\n".join(items_text)
        + f"\n\n---\n{NOTE_GENERIC}"
    )
    return subject, html_body, text_body


# ---- gönderim -------------------------------------------------------------


def send_digest(
    recipients: list[str],
    subject: str,
    html_body: str,
    text_body: str,
    *,
    force_dry: bool = False,
) -> int:
    """Toplu gönderim. SMTP yoksa (veya `force_dry`) dry-run: 0 gönderim, log yazar."""
    if not recipients:
        log.info("Bülten gönderimi atlandı: abone yok.")
        return 0
    if force_dry or not settings.smtp_enabled:
        log.info(
            "[DRY-RUN] Bülten gönderilecekti: %d alıcı, konu=%r "
            "(ESHAM_SMTP_HOST/USER/PASSWORD tanımlı değil).",
            len(recipients),
            subject,
        )
        return 0

    message = MIMEMultipart("alternative")
    message["Subject"] = subject
    message["From"] = settings.email_from
    message["To"] = ", ".join(recipients)
    message.attach(MIMEText(text_body, "plain", "utf-8"))
    message.attach(MIMEText(html_body, "html", "utf-8"))

    context = ssl.create_default_context()
    try:
        if settings.smtp_use_ssl:
            with smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=30,
                                  context=context) as server:
                server.login(settings.smtp_user, settings.smtp_password)
                server.sendmail(settings.email_from, recipients, message.as_string())
        else:
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=30) as server:
                server.ehlo()
                server.starttls(context=context)
                server.ehlo()
                server.login(settings.smtp_user, settings.smtp_password)
                server.sendmail(settings.email_from, recipients, message.as_string())
    except (smtplib.SMTPException, OSError) as exc:
        log.error("Bülten gönderimi başarısız (%s); %d e-posta gönderilemedi.", exc, len(recipients))
        return 0

    log.info("Bülten gönderildi: %d alıcı, konu=%r.", len(recipients), subject)
    return len(recipients)


def run_newsletter(
    *,
    limit: int | None = None,
    test_to: str | None = None,
    dry_run: bool = False,
) -> int:
    """Bülteni üret ve gönderir (gönderilen e-posta sayısını döner).

    `test_to` verilirse liste yerine yalnızca o adrese gönderilir (send-list
    doğrulaması için) — gerçek abonelere dokunulmaz.
    """
    reports = latest_reports(limit)
    if not reports:
        log.info("Bülten atlandı: `web/content/reports` içinde rapor yok.")
        return 0
    subject, html_body, text_body = build_digest(reports)

    if test_to:
        if not is_valid_email(test_to):
            log.warning("Test adresi geçersiz: %r", test_to)
            return 0
        recipients = [test_to.strip()]
    else:
        recipients = SubscriberStore().emails()

    return send_digest(recipients, subject, html_body, text_body, force_dry=dry_run)
