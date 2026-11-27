"""Telegram giden kutusu: önce doğrula → commit/push → EN SON gönder (PR #31 engelleyici bulgusu).

İş akışı (``.github/workflows/esham-schedule.yml``) burada AĞSIZ bir benzetimle koşulur:
- ``origin``: commit'lenmiş dosyalar (durum, giden kutusu, raporlar, kartlar). Her koşu origin'in temiz bir
  kopyasıyla başlar (actions/checkout) ve koşu bitince çalışma kopyası atılır (geçici GitHub koşucusu).
- Bot adımı gerçek ``NewsStream.check_once`` + gerçek ``SocialPublisher``; yalnız KAP kaynağı ve rapor
  üretimi sahte. Telegram taşıması sahte (``FakeTransport``); ``requests.post`` bot adımında çağrılırsa test kırılır.
- Kapı kırılırsa ``publish_gate.handle_gate_failure`` + yalnız ``bot/state`` commit'i.
- Push başarısızsa origin'e hiçbir şey yazılmaz.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from esham import news_stream, publish_gate, state as state_mod
from esham.config import settings
from esham.neutral import NOTE_GENERIC, NOTE_KAP, find_banned
from esham.publishing import outbox as ob
from esham.publishing.content_store import slugify
from esham.publishing.social import SocialPublisher
from esham.sources import Disclosure

PNG = b"\x89PNG\r\n\x1a\n" + b"esham-test-card" * 4


class FakeTransport:
    """Sahte Telegram. ``plan``: sıradaki çağrıların sonucu (varsayılan "sent")."""

    def __init__(self) -> None:
        self.sent: list[dict] = []      # Telegram'a GERÇEKTEN ulaşan mesajlar
        self.calls = 0
        self.plan: list[str] = []
        self.crash_after_send = False

    def send(self, text, image_path=None):
        self.calls += 1
        outcome = self.plan.pop(0) if self.plan else "sent"
        if outcome == "sent":
            self.sent.append({
                "text": text,
                "image": image_path.read_bytes() if image_path else None,
                "image_name": image_path.name if image_path else None,
            })
            if self.crash_after_send:
                raise SystemExit("koşucu gönderimden hemen sonra öldü")
            return ob.SendResult("sent", message_id=str(len(self.sent)))
        return ob.SendResult(outcome, error=f"sahte {outcome}")


def filing(n: int, title: str | None = None) -> Disclosure:
    return Disclosure(
        title=title or f"ŞİRKET{n} A.Ş.: Yeni İş İlişkisi {n}", company=f"ŞİRKET{n} A.Ş.", date="2026-11-27",
        disclosure_type="Yeni İş İlişkisi", ticker=f"SRK{n}", disclosure_index=str(1800000 + n),
    )


class World:
    def __init__(self, tmp_path: Path, monkeypatch, cfg) -> None:
        self.tmp = tmp_path
        self.mp = monkeypatch
        self.cfg = cfg
        self.origin = tmp_path / "origin"
        (self.origin / "state").mkdir(parents=True)
        (self.origin / "reports").mkdir()
        (self.origin / "cards").mkdir()
        self.transport = FakeTransport()
        self.n = 0
        self.with_image = False
        self.work: Path | None = None
        self.bot_http_calls: list = []

    # ---- git benzetimi ----
    def _checkout(self) -> Path:
        self.n += 1
        work = self.tmp / f"run{self.n}"
        shutil.copytree(self.origin, work)
        self.work = work
        self.cfg("state_file", work / "state" / "esham_state.json")
        self.cfg("content_dir", work / "reports")
        self.cfg("cards_dir", work / "cards")
        self.mp.setenv("ESHAM_OUTBOX_FILE", str(work / "state" / "telegram_outbox.json"))
        self.mp.setenv("GITHUB_RUN_ID", str(1000 + self.n))
        self.mp.setattr(state_mod, "_shared", None)
        return work

    def _commit(self, *rel: str) -> None:
        """Yalnız izlenen dosyalar: outbox_media/ .gitignore'dadır, commit'lenmez."""
        assert self.work is not None
        for r in rel:
            src = self.work / r
            if src.is_dir():
                for p in src.rglob("*"):
                    if p.is_file() and "outbox_media" not in p.parts and p.suffix != ".tmp":
                        dest = self.origin / p.relative_to(self.work)
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy(p, dest)
            elif src.exists():
                (self.origin / r).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy(src, self.origin / r)

    # ---- bot adımı ----
    def _fake_news_report(self, disclosure=None, event=None, publish_social=True):
        d = disclosure
        slug_base = f"{slugify(d.title)}-{d.disclosure_index}"
        slug = f"{slug_base}-2026-11-27"
        path = settings.content_dir / f"2026-11-27-{slug_base}.json"
        if path.exists():
            self._status = "duplicate"
            return None
        path.write_text(json.dumps({"slug": slug, "title": d.title, "schemaVersion": 2,
                                    "kap": {"index": d.disclosure_index}}, ensure_ascii=False), encoding="utf-8")
        img = None
        if self.with_image:
            img = self.tmp / f"tmp_card_{self.n}_{d.disclosure_index}.png"  # pipeline'ın geçici kartı
            img.write_bytes(PNG)
            settings.cards_dir.mkdir(parents=True, exist_ok=True)
            (settings.cards_dir / f"{slug}.png").write_bytes(PNG)    # ContentStore'un kalıcı kopyası
        SocialPublisher().broadcast(
            f"{d.title}\n\nhttps://esham.pages.dev/rapor/{slug}\n#{d.ticker} #KAP",
            image_path=img, disclaimer=NOTE_KAP, verbatim=[d.title],
        )
        if img:
            img.unlink()  # pipeline._cleanup: geçici kart koşu içinde silinir
        self._status = "published"
        return slug

    def _bot_step(self, filings: list[Disclosure]) -> None:
        self._status = "none"
        self.mp.setattr(news_stream, "run_news_report", self._fake_news_report)
        self.mp.setattr(news_stream, "last_news_status", lambda: self._status)
        self.mp.setattr(news_stream, "update_ticker_data", lambda: None)
        self.mp.setattr(news_stream, "is_significant", lambda d, m=None: True)
        import requests

        self.mp.setattr(requests, "post", lambda *a, **k: self.bot_http_calls.append(a) or pytest.fail("bot adımı ağa çıktı"))
        stream = news_stream.NewsStream()
        stream.kap = type("K", (), {"latest_disclosures": lambda s: list(filings)})()
        stream.macro_scan = lambda: 0
        stream.check_once(max_publish=5)

    # ---- iş akışı ----
    def run(self, filings, *, gate_ok=True, push_ok=True, claim_push_ok=True, record_push_ok=True,
            crash_after_send=False) -> str:
        self._checkout()
        self._bot_step(filings)
        changed_reports = any(p.name not in {q.name for q in (self.origin / "reports").iterdir()}
                              for p in (self.work / "reports").iterdir())
        if changed_reports and not gate_ok:
            publish_gate.handle_gate_failure("web testleri kırıldı (test)")
            self._commit("state")  # YALNIZ durum + giden kutusu
            return "gate_failed"
        if not push_ok:
            return "push_failed"
        self._commit("reports", "cards", "state")
        # --- gönderim adımı (yalnız push başarılıysa) ---
        claimed = ob.Outbox().claim()  # önce-yaz: in_flight işareti (ve unknown/expired geçişleri)
        if not claim_push_ok:
            return "claim_push_failed"
        self._commit("state/telegram_outbox.json")
        if not claimed:
            return "nothing_to_send"
        self.transport.crash_after_send = crash_after_send
        try:
            ob.Outbox().deliver(self.transport)
        except SystemExit:
            return "crashed"
        if not record_push_ok:
            return "record_push_failed"
        self._commit("state/telegram_outbox.json")
        return "ok"

    # ---- origin okuma ----
    def origin_outbox(self) -> list[dict]:
        p = self.origin / "state" / "telegram_outbox.json"
        return json.loads(p.read_text(encoding="utf-8"))["entries"] if p.exists() else []

    def origin_state(self) -> dict:
        p = self.origin / "state" / "esham_state.json"
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}

    def origin_reports(self) -> list[str]:
        return sorted(p.name for p in (self.origin / "reports").iterdir())


@pytest.fixture
def cfg():
    """`settings` donmuş (frozen) dataclass: test süresince alan değiştirir, sonunda geri yükler."""
    old: dict = {}

    def set_(name, value):
        old.setdefault(name, getattr(settings, name))
        object.__setattr__(settings, name, value)

    yield set_
    for name, value in old.items():
        object.__setattr__(settings, name, value)


@pytest.fixture
def world(tmp_path, monkeypatch, cfg):
    cfg("paused", False)
    cfg("max_posts_per_day", 60)
    return World(tmp_path, monkeypatch, cfg)


# ---- 1. mutlu yol -------------------------------------------------------------------------------

def test_happy_path_sends_exactly_once_after_push(world):
    f = filing(1)
    assert world.run([f]) == "ok"
    (msg,) = world.transport.sent
    assert f.title in msg["text"] and msg["text"].endswith(NOTE_KAP) and "/rapor/" in msg["text"]
    assert world.bot_http_calls == []  # bot adımı Telegram'a (veya başka yere) istek atmadı
    (e,) = world.origin_outbox()
    assert e["status"] == "sent" and e["key"] == f"kap:{f.disclosure_index}" and e["kap_index"] == f.disclosure_index
    assert e["slug"].startswith(slugify(f.title)) and len(world.origin_reports()) == 1
    # aynı bildirim KAP akışında durmaya devam eder: sonraki koşular göndermez
    world.run([f])
    world.run([f])
    assert len(world.transport.sent) == 1


def test_run_step_only_writes_outbox(world):
    """Push'tan önce (kapı/commit aşamasında) giden kutusunda yalnız 'pending' vardır, hiçbir şey gitmemiştir."""
    world._checkout()
    world._bot_step([filing(1)])
    entries = ob.Outbox().entries
    assert [e["status"] for e in entries] == ["pending"]
    assert world.transport.calls == 0


# ---- 2. kapı kırılır ----------------------------------------------------------------------------

def test_gate_failure_sends_nothing_and_stops_after_three_attempts(world):
    f = filing(1)
    key = f"{f.company}:{f.title}:{f.date}"
    for i in (1, 2):
        assert world.run([f], gate_ok=False) == "gate_failed"
        st = world.origin_state()
        assert st["gate_failures"][key]["count"] == i
        assert key not in st.get("seen_disclosures", {})   # yeniden denenecek
        assert world.origin_outbox() == []                  # iptal edilen gönderi commit'lenmedi
        assert world.origin_reports() == []                 # kıran rapor commit'lenmedi
    assert world.run([f], gate_ok=False) == "gate_failed"
    st = world.origin_state()
    (failed,) = st["failed_disclosures"]
    assert failed["status"] == "gate_failed" and failed["attempts"] == 3
    assert failed["index"] == f.disclosure_index and "web testleri" in failed["reason"]
    assert key in st["seen_disclosures"]                    # bir daha denenmez
    # kapı düzelse bile bırakılan bildirim yeniden işlenmez; sonsuz döngü yok
    for _ in range(3):
        world.run([f])
    assert world.transport.calls == 0 and world.transport.sent == []
    assert world.origin_reports() == []


def test_gate_failure_once_then_success_sends_once(world):
    f = filing(1)
    assert world.run([f], gate_ok=False) == "gate_failed"
    assert world.transport.sent == []
    assert world.run([f]) == "ok"
    assert len(world.transport.sent) == 1 and len(world.origin_reports()) == 1


# ---- 3. push başarısız --------------------------------------------------------------------------

def test_push_failure_sends_nothing_and_no_duplicate_later(world):
    f = filing(1)
    assert world.run([f], push_ok=False) == "push_failed"
    assert world.transport.calls == 0 and world.origin_outbox() == [] and world.origin_reports() == []
    assert world.run([f]) == "ok"            # sonraki koşu bildirimi kaybetmez
    world.run([f])
    assert len(world.transport.sent) == 1     # ve iki kez göndermez


def test_claim_push_failure_sends_nothing_next_run_sends_once(world):
    world.with_image = True
    f = filing(1)
    assert world.run([f], claim_push_ok=False) == "claim_push_failed"
    assert world.transport.calls == 0
    assert [e["status"] for e in world.origin_outbox()] == ["pending"]
    assert world.run([f]) == "ok"
    (msg,) = world.transport.sent
    # yeni koşucuda outbox_media yok (commit'lenmez): commit'lenmiş kart görseline düşülür
    assert msg["image"] == PNG and msg["image_name"].endswith(".png")


# ---- 4. gönderim ile "gönderildi" kaydı arasında çökme -----------------------------------------

def test_crash_between_send_and_mark_sent_does_not_double_send(world):
    f = filing(1)
    assert world.run([f], crash_after_send=True) == "crashed"
    assert len(world.transport.sent) == 1
    assert [e["status"] for e in world.origin_outbox()] == ["in_flight"]
    world.run([f])
    world.run([f])
    assert len(world.transport.sent) == 1
    assert [e["status"] for e in world.origin_outbox()] == ["unknown"]


def test_record_push_failure_does_not_double_send(world):
    f = filing(1)
    assert world.run([f], record_push_ok=False) == "record_push_failed"
    world.run([f])
    assert len(world.transport.sent) == 1
    assert world.origin_outbox()[0]["status"] == "unknown"


# ---- 5. birden çok bildirim / görsel ---------------------------------------------------------------

def test_two_filings_in_one_run(world):
    a, b = filing(1), filing(2)
    assert world.run([a, b]) == "ok"
    texts = [m["text"] for m in world.transport.sent]
    assert len(texts) == 2 and any(a.title in t for t in texts) and any(b.title in t for t in texts)
    keys = sorted(e["key"] for e in world.origin_outbox())
    assert keys == [f"kap:{a.disclosure_index}", f"kap:{b.disclosure_index}"]
    world.run([a, b])
    assert len(world.transport.sent) == 2


def test_two_filings_gate_failure_rolls_back_both(world):
    a, b = filing(1), filing(2)
    world.run([a, b], gate_ok=False)
    st = world.origin_state()
    assert set(st["gate_failures"]) == {f"{x.company}:{x.title}:{x.date}" for x in (a, b)}
    assert world.transport.calls == 0


def test_image_post_survives_temp_cleanup(world):
    world.with_image = True
    assert world.run([filing(1)]) == "ok"
    (msg,) = world.transport.sent
    assert msg["image"] == PNG


# ---- 6. Telegram hatası -----------------------------------------------------------------------------

def test_telegram_rejection_retries_bounded_and_never_blocks_reports(world):
    f = filing(1)
    world.transport.plan = ["retryable"] * 5
    assert world.run([f]) == "ok"
    assert len(world.origin_reports()) == 1                     # rapor siteye girdi
    e = world.origin_outbox()[0]
    assert e["status"] == "pending" and e["attempts"] == 1
    world.run([f])
    world.run([f])
    e = world.origin_outbox()[0]
    assert e["status"] == "failed" and e["attempts"] == ob.MAX_SEND_ATTEMPTS
    world.run([f])
    assert world.transport.calls == ob.MAX_SEND_ATTEMPTS and world.transport.sent == []


def test_ambiguous_telegram_error_is_never_retried(world):
    world.transport.plan = ["ambiguous"]
    world.run([filing(1)])
    world.run([filing(1)])
    assert world.transport.calls == 1 and world.origin_outbox()[0]["status"] == "unknown"


def test_dry_run_marks_skipped_and_never_sends_later(world):
    world.transport.plan = ["dry_run"]
    world.run([filing(1)])
    world.run([filing(1)])
    assert world.transport.calls == 1 and world.origin_outbox()[0]["status"] == "skipped"


def test_stale_pending_entry_expires(tmp_path, monkeypatch):
    now = [1_000_000.0]
    box = ob.Outbox(tmp_path / "o.json", clock=lambda: now[0])
    box.enqueue(f"Metin\n\n{NOTE_GENERIC}", disclaimer=NOTE_GENERIC)
    now[0] += ob.MAX_PENDING_AGE_SECONDS + 1
    assert box.claim("r1") == [] and box.entries[0]["status"] == "expired"


# ---- 7. tarafsız dil + uyarı satırı -----------------------------------------------------------------

def test_outbox_refuses_banned_phrases_and_missing_disclaimer(tmp_path):
    box = ob.Outbox(tmp_path / "o.json")
    assert box.enqueue(f"GARAN için güçlü al, hedef fiyat 150 TL\n\n{NOTE_GENERIC}", disclaimer=NOTE_GENERIC) is None
    assert box.enqueue("Temiz metin ama uyarı satırı yok", disclaimer=NOTE_GENERIC) is None
    assert box.enqueue("Temiz metin", disclaimer="") is None
    assert box.entries == []
    # birebir KAP başlığı (yasaklı kalıp içerse de) maskelenir; uyarı satırıyla kabul edilir
    title = "ABC A.Ş.: Mega Sözleşme İmzalanması Hk."
    assert box.enqueue(f"{title}\n\n{NOTE_KAP}", disclaimer=NOTE_KAP, verbatim=[title]) is not None


def test_tampered_outbox_entry_is_blocked_at_send(tmp_path):
    box = ob.Outbox(tmp_path / "o.json")
    box.enqueue(f"Temiz metin\n\n{NOTE_GENERIC}", disclaimer=NOTE_GENERIC)
    box.entries[0]["text"] = f"Hedef fiyat 150 TL\n\n{NOTE_GENERIC}"   # dosya elle bozuldu
    box.save()
    t = FakeTransport()
    box = ob.Outbox(tmp_path / "o.json")
    box.claim("r1")
    assert box.deliver(t, "r1")["blocked"] == 1 and t.calls == 0


def test_real_pipeline_outbox_is_neutral_and_carries_disclaimer(tmp_path, monkeypatch, cfg):
    """Gerçek run_news_report (kötü LLM çıktısıyla) → giden kutusu kaydı tarafsız dil kurallarından geçer."""
    from esham import pipeline
    from esham.ai.client import LlmClient
    from esham.publishing.content_store import ContentStore

    class _NoMacro:
        def snapshot(self):
            raise RuntimeError("ağ yok")

    class _FakeKap:
        def get_detail_text(self, index):
            return "Şirketimiz 1.250.000.000 TL tutarında sözleşme imzalamıştır."

    bad = ("## ÖZET\nHisse üzerinde pozitif haber akışı etkisi yaratması beklenir.\n\n## BİLDİRİM\n"
           "- **Değerlendirme:** hedef fiyat 150 TL, güçlü AL.\n\n## TWEET\nMEGA İŞ ANLAŞMASI! 🚀 Güçlü AL, hedef fiyat 150 TL.\n")
    monkeypatch.delenv("GIT_AUTO_PUSH", raising=False)
    cfg("paused", False)
    cfg("state_file", tmp_path / "state" / "esham_state.json")
    monkeypatch.setattr(state_mod, "_shared", None)
    monkeypatch.setattr(pipeline, "GlobalMacroSource", _NoMacro)
    monkeypatch.setattr(pipeline, "KapSource", _FakeKap)
    monkeypatch.setattr(pipeline, "_render_card", lambda spec: None)
    monkeypatch.setattr(pipeline, "ContentStore", lambda: ContentStore(tmp_path / "reports", tmp_path / "cards"))
    monkeypatch.setattr(LlmClient, "generate", lambda self, prompt, **kw: bad)
    import requests

    monkeypatch.setattr(requests, "post", lambda *a, **k: pytest.fail("pipeline ağa çıktı"))
    titles = []
    for i, t in enumerate(["ABC A.Ş.: Mega Sözleşme İmzalanması Hk.", "XYZ A.Ş.: Yeni İş İlişkisi"]):
        d = Disclosure(title=t, company=t.split(":")[0], date="2026-11-27", disclosure_type="Yeni İş İlişkisi",
                       raw_text="Sözleşme imzalanmıştır.", ticker=f"TCK{i}", disclosure_index=str(1900000 + i))
        with ob.outbox_context(kap_index=d.disclosure_index, kind="kap"):
            assert pipeline.run_news_report(disclosure=d, publish_social=True)
        titles.append(t)
    entries = ob.Outbox().entries
    assert len(entries) == 2
    for e, title in zip(entries, titles):
        text = e["text"]
        assert text.rstrip().endswith(e["disclaimer"]) and e["disclaimer"] in ob.KNOWN_DISCLAIMERS
        assert find_banned(text.replace(title, "")) == [], text
        assert ob.validate_post(text, e["disclaimer"], e["verbatim"]) == []
        assert "150" not in text and "1.250.000.000" not in text


# ---- 8. yerel / elle kullanım ve taşıma sınıflandırması --------------------------------------------

def test_local_send_outbox_all_phase(tmp_path, monkeypatch):
    monkeypatch.setenv("ESHAM_OUTBOX_FILE", str(tmp_path / "o.json"))
    ob.Outbox().enqueue(f"Yerel deneme\n\n{NOTE_GENERIC}", disclaimer=NOTE_GENERIC)
    t = FakeTransport()
    assert ob.send_outbox("all", transport=t) == {"claimed": 1, "sent": 1, "retry": 0, "failed": 0,
                                                   "unknown": 0, "skipped": 0, "blocked": 0}
    assert ob.send_outbox("all", transport=t)["claimed"] == 0 and len(t.sent) == 1


def test_cli_has_send_now_and_outbox_commands():
    from esham.main import build_parser

    p = build_parser()
    a = p.parse_args(["--send-now", "morning-report"])
    assert a.send_now and a.command == "morning-report"
    assert p.parse_args(["send-outbox", "--phase", "claim"]).phase == "claim"
    assert p.parse_args(["outbox-gate-failed", "--reason", "x"]).reason == "x"


class _Resp:
    def __init__(self, code, body=None, text=""):
        self.status_code = code
        self._body = body or {}
        self.text = text

    def json(self):
        return self._body


@pytest.mark.parametrize("resp,outcome", [
    (_Resp(200, {"ok": True, "result": {"message_id": 7}}), "sent"),
    (_Resp(429, text="Too Many Requests"), "retryable"),
    (_Resp(403, text="bot was kicked"), "retryable"),
    (_Resp(502, text="Bad Gateway"), "ambiguous"),
])
def test_transport_classifies_http_results(monkeypatch, resp, outcome):
    import requests

    monkeypatch.setattr(requests, "post", lambda *a, **k: resp)
    r = ob.TelegramTransport(token="t", chat_id="c").send("x")
    assert r.outcome == outcome
    if outcome == "sent":
        assert r.message_id == "7"


@pytest.mark.parametrize("exc,outcome", [("ConnectTimeout", "retryable"), ("ReadTimeout", "ambiguous"),
                                         ("ConnectionError", "ambiguous")])
def test_transport_classifies_network_errors(monkeypatch, exc, outcome):
    import requests

    def boom(*a, **k):
        raise getattr(requests.exceptions, exc)("x")

    monkeypatch.setattr(requests, "post", boom)
    assert ob.TelegramTransport(token="t", chat_id="c").send("x").outcome == outcome


def test_transport_markdown_parse_error_falls_back_to_plain_text(monkeypatch):
    import requests

    calls = []

    def post(url, **k):
        calls.append(k.get("json", {}).get("parse_mode"))
        return _Resp(400, text="Bad Request: can't parse entities") if len(calls) == 1 else _Resp(200, {"result": {}})

    monkeypatch.setattr(requests, "post", post)
    assert ob.TelegramTransport(token="t", chat_id="c").send("a_b*c").outcome == "sent"
    assert calls == ["Markdown", None]


def test_transport_without_credentials_is_dry_run(monkeypatch):
    import requests

    monkeypatch.setattr(requests, "post", lambda *a, **k: pytest.fail("kimlik yokken istek atıldı"))
    assert ob.TelegramTransport(token="", chat_id="").send("x").outcome == "dry_run"


def test_corrupt_outbox_stops_instead_of_resetting(tmp_path):
    p = tmp_path / "o.json"
    p.write_text("{bozuk", encoding="utf-8")
    with pytest.raises(RuntimeError):
        ob.Outbox(p)
