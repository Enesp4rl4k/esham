"""Giden kutusu durum makinesi, anahtar bazında birleştirme ve GERÇEK git ile bayat-checkout benzetimi.

İkinci tur engelleyici 1: kuyrukta bekleyen koşu B, koşu A'nın commit'lerinden önceki durumdan başlayıp aynı
`kap:<no>` anahtarını `pending` yazıyor; eski `rebase -X theirs` master'daki `sent` kaydını `pending`'e
çeviriyordu. Burada iki gerçek klon (A, B) ve yerel bir bare "origin" ile ``git_sync.commit_push`` koşulur
(ağ yok; git birleştirme sürücüsü gerçekten çağrılır).
"""
from __future__ import annotations

import json
import shutil
import subprocess
import time
from pathlib import Path

import pytest

from esham import git_sync
from esham.neutral import NOTE_KAP
from esham.publishing import outbox as ob
from esham.report_gate import git_changed_reports, git_head_content, run_gate

ALL = [ob.PENDING, ob.IN_FLIGHT, *sorted(ob.TERMINAL)]

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git yok")


def entry(key, status, **kw):
    return {"key": key, "status": status, "attempts": 0, "claim_run": "", "created_at": time.time(),
            "text": f"x\n\n{NOTE_KAP}", "disclaimer": NOTE_KAP, "verbatim": [], **kw}


# ---- durum makinesi ---------------------------------------------------------------------------------

@pytest.mark.parametrize("old", ALL)
@pytest.mark.parametrize("new", ALL)
def test_state_machine_single_table(old, new):
    e = entry("k", old)
    allowed = new in ob.TRANSITIONS[old]
    if old in ob.TERMINAL:
        assert not allowed  # son durumdan hiçbir geçiş yok
    if allowed:
        ob.move(e, new)
        assert e["status"] == new
    else:
        with pytest.raises(ob.IllegalTransition):
            ob.move(e, new)
        assert e["status"] == old


def test_outbox_operations_use_the_state_machine(tmp_path):
    box = ob.Outbox(tmp_path / "o.json")
    box.entries = [entry("kap:1", ob.SENT)]
    box.save()
    box = ob.Outbox(tmp_path / "o.json")
    assert box.claim("r1") == [] and box.entries[0]["status"] == ob.SENT


# ---- anahtar bazında birleştirme ------------------------------------------------------------------

@pytest.mark.parametrize("terminal", sorted(ob.TERMINAL))
@pytest.mark.parametrize("other", [ob.PENDING, ob.IN_FLIGHT])
def test_terminal_always_wins_both_orders(terminal, other):
    t, o = entry("kap:2", terminal), entry("kap:2", other, attempts=2)
    assert ob.merge_entry(t, o)["status"] == terminal
    assert ob.merge_entry(o, t)["status"] == terminal
    assert ob.merge_outboxes([], [o], [t])[0]["status"] == terminal
    assert ob.merge_outboxes([], [t], [o])[0]["status"] == terminal


def test_merge_never_moves_backwards_and_keeps_all_keys():
    base = [entry("kap:1", ob.PENDING), entry("kap:2", ob.PENDING)]
    theirs = [entry("kap:1", ob.SENT), entry("kap:2", ob.IN_FLIGHT, claim_run="A")]  # A gönderdi / üstlendi
    ours = [entry("kap:1", ob.PENDING, created_run="B"), entry("kap:2", ob.PENDING), entry("kap:3", ob.PENDING)]
    merged = {e["key"]: e for e in ob.merge_outboxes(base, ours, theirs)}
    assert merged["kap:1"]["status"] == ob.SENT
    assert merged["kap:2"]["status"] == ob.IN_FLIGHT and merged["kap:2"]["claim_run"] == "A"
    assert merged["kap:3"]["status"] == ob.PENDING


def test_in_flight_always_beats_pending_and_deploy_mark_is_kept():
    a = entry("k", ob.IN_FLIGHT, attempts=0)
    b = entry("k", ob.PENDING, attempts=2, deployed_at=5.0, deployed_sha="abc")  # deneme sayısı fazla olsa da
    for m in (ob.merge_entry(a, b), ob.merge_entry(b, a)):
        assert m["status"] == ob.IN_FLIGHT and m["deployed_sha"] == "abc"


def test_merge_deletion_semantics():
    p = entry("k", ob.PENDING)
    assert ob.merge_outboxes([p], [], [p]) == []                       # bir taraf sildi, öbürü dokunmadı
    s = entry("k", ob.SENT)
    assert ob.merge_outboxes([p], [], [s])[0]["status"] == ob.SENT     # silme son durumu YOK EDEMEZ


# ---- gerçek git: bayat checkout (A ve B) ---------------------------------------------------------

def _run(cwd: Path, *args: str) -> str:
    env = {**git_sync._env()}
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True, env=env).stdout


def _write_outbox(repo: Path, entries: list[dict]) -> None:
    p = repo / "bot" / "state" / "telegram_outbox.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    ob.dump_entries(p, entries)


def _read_origin_outbox(origin: Path) -> list[dict]:
    raw = subprocess.run(["git", "--git-dir", str(origin), "show", "master:bot/state/telegram_outbox.json"],
                         check=True, capture_output=True, text=True).stdout
    return json.loads(raw)["entries"]


@pytest.fixture
def repos(tmp_path):
    origin = tmp_path / "origin.git"
    _run(tmp_path, "init", "-q", "--bare", "-b", "master", str(origin))
    seed = tmp_path / "seed"
    _run(tmp_path, "clone", "-q", str(origin), str(seed))
    _run(seed, "config", "core.autocrlf", "false")
    (seed / ".gitattributes").write_text(
        "bot/state/telegram_outbox.json merge=esham-outbox\nbot/state/esham_state.json merge=binary\n", encoding="utf-8")
    _write_outbox(seed, [entry("kap:1", ob.SENT)])
    (seed / "bot" / "state" / "esham_state.json").write_text('{"seen": 1}\n', encoding="utf-8")
    _run(seed, "add", "-A")
    _run(seed, "commit", "-q", "-m", "seed")
    _run(seed, "push", "-q", "origin", "master")
    a, b = tmp_path / "A", tmp_path / "B"
    for r in (a, b):  # B, A çalışırken tetiklendi: aynı (bayat) commit'ten başlar
        _run(tmp_path, "clone", "-q", str(origin), str(r))
        _run(r, "config", "core.autocrlf", "false")
    return origin, a, b


def test_stale_checkout_cannot_turn_sent_back_to_pending(repos, monkeypatch):
    origin, a, b = repos
    # A: kap:2'yi yayınlar, gönderir ve "sent" push eder
    _write_outbox(a, [entry("kap:1", ob.SENT), entry("kap:2", ob.SENT, sent_at=10.0, created_run="A")])
    assert git_sync.commit_push("A: gönderildi", ["bot/state/telegram_outbox.json"], root=a, wait=0) == "pushed"
    # B: bayat checkout'tan başladı, kap:2'yi yeniden işleyip pending yazdı + yeni kap:3
    _write_outbox(b, [entry("kap:1", ob.SENT), entry("kap:2", ob.PENDING, created_run="B"),
                      entry("kap:3", ob.PENDING, created_run="B")])
    assert git_sync.commit_push("B: içerik", ["bot/state/telegram_outbox.json"], root=b, wait=0) == "pushed"
    merged = {e["key"]: e for e in _read_origin_outbox(origin)}
    assert merged["kap:2"]["status"] == ob.SENT and merged["kap:2"]["created_run"] == "A"
    assert merged["kap:3"]["status"] == ob.PENDING
    # B'nin gönderim adımı: master'daki güncel kutuyu okur, yalnız hâlâ pending olanı üstlenir → Telegram'a tek mesaj
    sent = []

    class T:
        def send(self, text, image_path=None):
            sent.append(text)
            return ob.SendResult("sent", message_id="1")

    monkeypatch.setenv("GITHUB_RUN_ID", "B")
    box = ob.Outbox(b / "bot" / "state" / "telegram_outbox.json")
    claimed = box.claim()
    assert [e["key"] for e in claimed] == ["kap:3"]
    box.deliver(T())
    assert len(sent) == 1


def test_claim_merged_into_terminal_is_not_sent(repos, monkeypatch):
    """B kap:2'yi üstlendi (in_flight) ama push sırasında master'da kap:2 'sent' çıktı: deliver göndermez."""
    origin, a, b = repos
    _write_outbox(b, [entry("kap:1", ob.SENT), entry("kap:2", ob.PENDING, created_run="X")])
    _write_outbox(a, [entry("kap:1", ob.SENT), entry("kap:2", ob.PENDING, created_run="X")])
    git_sync.commit_push("ortak", ["bot/state/telegram_outbox.json"], root=a, wait=0)
    git_sync.sync_with_master(root=b)
    monkeypatch.setenv("GITHUB_RUN_ID", "B")
    box = ob.Outbox(b / "bot" / "state" / "telegram_outbox.json")
    assert [e["key"] for e in box.claim(require_deploy=False)] == ["kap:2"]
    _write_outbox(a, [entry("kap:1", ob.SENT), entry("kap:2", ob.SENT, created_run="X")])
    git_sync.commit_push("A gönderdi", ["bot/state/telegram_outbox.json"], root=a, wait=0)
    git_sync.commit_push("B claim", ["bot/state/telegram_outbox.json"], root=b, wait=0)
    calls = []
    box.deliver(type("T", (), {"send": lambda s, *a, **k: calls.append(1) or ob.SendResult("sent")})())
    assert calls == []


def test_state_file_conflict_stops_and_pushes_nothing(repos):
    origin, a, b = repos
    (a / "bot" / "state" / "esham_state.json").write_text('{"seen": 2}\n', encoding="utf-8")
    git_sync.commit_push("A durum", ["bot/state/esham_state.json"], root=a, wait=0)
    (b / "bot" / "state" / "esham_state.json").write_text('{"seen": 3}\n', encoding="utf-8")
    _write_outbox(b, [entry("kap:1", ob.SENT), entry("kap:9", ob.PENDING)])
    with pytest.raises(git_sync.GitSyncError):
        git_sync.commit_push("B", ["bot/state/esham_state.json", "bot/state/telegram_outbox.json"], root=b, wait=0)
    assert [e["key"] for e in _read_origin_outbox(origin)] == ["kap:1"]   # B'nin hiçbir şeyi master'a girmedi
    assert _run(b, "status", "--porcelain", "--untracked-files=no").strip() == ""  # rebase geri alındı


# ---- rapor başına kapı (gerçek git çalışma ağacı) ----------------------------------------------------

def test_report_gate_on_real_worktree_isolates_broken_report(repos):
    _, a, _ = repos
    reports = a / "web" / "content" / "reports"
    reports.mkdir(parents=True)
    (reports / "eski.json").write_text('{"slug": "eski"}', encoding="utf-8")
    _run(a, "add", "-A")
    _run(a, "commit", "-q", "-m", "eski rapor")
    (reports / "eski.json").write_text('{"slug": "eski", "BOZUK": true}', encoding="utf-8")  # değişmiş + bozuk
    for i in range(4):
        (reports / f"yeni{i}.json").write_text(json.dumps({"slug": f"yeni{i}"}), encoding="utf-8")
    runs = []

    def runner():
        runs.append(1)
        return not any("BOZUK" in p.read_text(encoding="utf-8") for p in reports.glob("*.json"))

    assert len(git_changed_reports(a)) == 5
    res = run_gate(a, runner=runner, changed=git_changed_reports(a), head_content=git_head_content(a))
    assert res.status == "partial" and res.bad == ["web/content/reports/eski.json"] and res.bad_slugs == ["eski"]
    assert json.loads((reports / "eski.json").read_text(encoding="utf-8")) == {"slug": "eski"}  # HEAD sürümüne döndü
    assert all((reports / f"yeni{i}.json").exists() for i in range(4))
    assert len(runs) == 1 + 1 + 5 + 1  # birlikte, temel, tek tek, son doğrulama


def test_code_broken_marker_alerts_once_per_day():
    from esham.publish_gate import code_broken_marker

    st, first = code_broken_marker({"seen_disclosures": {"a": 1}}, "2026-11-27")
    assert first and st["code_gate_broken"]["since"] == "2026-11-27" and st["seen_disclosures"] == {"a": 1}
    st2, again = code_broken_marker(st, "2026-11-27")
    assert not again
    _, next_day = code_broken_marker(st2, "2026-11-28")
    assert next_day


def test_external_network_is_blocked_for_unmarked_tests(request):
    """conftest: işaretsiz testte dış bağlantı ve DNS denemesi engellenir (yerel adres serbest)."""
    import socket

    from conftest import ExternalNetworkBlocked

    with pytest.raises(ExternalNetworkBlocked):
        socket.getaddrinfo("query1.finance.yahoo.com", 443)
    s = socket.socket()
    try:
        with pytest.raises(ExternalNetworkBlocked):
            s.connect(("93.184.216.34", 80))
    finally:
        s.close()
    assert len(request.node.esham_network_attempts) == 2   # yutulsa bile kaydedildi → teardown testi kırar
    request.node.esham_network_attempts.clear()             # bu öz-test kasıtlı denedi
