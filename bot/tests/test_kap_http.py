"""KAP HTTP katmanı + yayın işi: 429 fırtınası koşuyu batıramaz (ağ yok, HTTP taklit)."""
import json
from datetime import datetime, timezone

import pytest
import requests

from esham import kap_http
from esham.jobs import publish_kap
from esham.kap_http import KapGate, KapUnavailable, parse_retry_after
from esham.sources import kap_financials


class Clock:
    def __init__(self) -> None:
        self.t = 1000.0
        self.sleeps: list[float] = []

    def now(self) -> float:
        return self.t

    def sleep(self, s: float) -> None:
        self.sleeps.append(s)
        self.t += s


class FakeResp:
    def __init__(self, status: int = 200, headers: dict | None = None) -> None:
        self.status_code = status
        self.headers = headers or {}
        self.content = b"ok"

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code} Client Error")


@pytest.fixture
def clock(monkeypatch):
    c = Clock()
    monkeypatch.setattr(kap_http, "_clock", c.now)
    monkeypatch.setattr(kap_http, "_sleep", c.sleep)
    monkeypatch.setattr(kap_http, "_jitter", lambda a, b: 0.0)
    return c


def script(monkeypatch, responses):
    """``responses``: sıralı liste ya da url -> yanıt fonksiyonu. Çağrılan URL'leri döndürür."""
    calls: list[str] = []
    it = None if callable(responses) else iter(responses)

    def fake(url, **kw):
        calls.append(url)
        r = responses(url) if it is None else next(it)
        if isinstance(r, Exception):
            raise r
        return r

    monkeypatch.setattr(kap_http.requests, "get", fake)
    monkeypatch.setattr(kap_http.requests, "post", fake)
    return calls


def make_gate(**kw) -> KapGate:
    base = dict(min_interval=0, max_attempts=3, backoff_base=2.0, backoff_max=60, budget_seconds=300, breaker_threshold=5)
    base.update(kw)
    g = KapGate(**base)
    g.begin_stage()
    return g


def test_success_path_unchanged(monkeypatch, clock):
    calls = script(monkeypatch, [FakeResp(200)])
    g = make_gate()
    assert g.request("GET", "https://kap/x").status_code == 200
    assert len(calls) == 1 and clock.sleeps == []
    assert g.ok == 1 and g.throttled == 0


def test_retry_after_seconds_is_honoured(monkeypatch, clock):
    script(monkeypatch, [FakeResp(429, {"Retry-After": "17"}), FakeResp(200)])
    g = make_gate()
    assert g.request("GET", "https://kap/x").status_code == 200
    assert clock.sleeps == [17.0]


def test_retry_after_is_capped_and_parsed(monkeypatch, clock):
    script(monkeypatch, [FakeResp(429, {"Retry-After": "9999"}), FakeResp(200)])
    g = make_gate(backoff_max=30, budget_seconds=0)
    g.request("GET", "https://kap/x")
    assert clock.sleeps == [30.0]
    assert parse_retry_after("abc") is None and parse_retry_after(None) is None
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    assert parse_retry_after("Thu, 01 Jan 2026 00:00:10 GMT", now) == 10.0


def test_exponential_backoff_and_attempt_cap(monkeypatch, clock):
    calls = script(monkeypatch, [FakeResp(503)] * 3)
    g = make_gate()
    assert g.request("GET", "https://kap/x").status_code == 503
    assert len(calls) == 3
    assert clock.sleeps == [2.0, 4.0]


def test_pacing_between_requests(monkeypatch, clock):
    script(monkeypatch, [FakeResp(200)] * 3)
    g = make_gate(min_interval=1.5)
    for _ in range(3):
        g.request("GET", "https://kap/x")
    assert clock.sleeps == [1.5, 1.5]


def test_wait_exceeding_budget_aborts_instead_of_sleeping(monkeypatch, clock):
    script(monkeypatch, [FakeResp(429, {"Retry-After": "50"})])
    g = make_gate(budget_seconds=40, backoff_max=60)
    with pytest.raises(KapUnavailable):
        g.request("GET", "https://kap/x")
    assert clock.sleeps == []


def test_budget_exhaustion_stops_stage(monkeypatch, clock):
    calls = script(monkeypatch, lambda url: FakeResp(200))
    g = make_gate(budget_seconds=10)
    g.request("GET", "https://kap/a")
    clock.t += 11
    with pytest.raises(KapUnavailable):
        g.request("GET", "https://kap/b")
    assert calls == ["https://kap/a"] and g.stopped and g.skipped == 1
    assert "bütçe" in g.summary()


def test_circuit_breaker_trips_after_consecutive_429s(monkeypatch, clock):
    calls = script(monkeypatch, lambda url: FakeResp(429))
    g = make_gate(breaker_threshold=4, max_attempts=3)
    g.request("GET", "https://kap/1")  # 3 x 429
    g.request("GET", "https://kap/2")  # 4. 429 devreyi açar, tekrar denenmez
    assert g.stopped
    n = len(calls)
    for i in range(10):
        with pytest.raises(KapUnavailable):
            g.request("GET", f"https://kap/s{i}")
    assert len(calls) == n and g.skipped == 10


def test_success_resets_consecutive_429_counter(monkeypatch, clock):
    script(monkeypatch, [FakeResp(429), FakeResp(200), FakeResp(429), FakeResp(200)])
    g = make_gate(breaker_threshold=2)
    g.request("GET", "https://kap/a")
    g.request("GET", "https://kap/b")
    assert not g.stopped


def test_connection_error_retries_then_raises(monkeypatch, clock):
    script(monkeypatch, [requests.ConnectionError("x")] * 3)
    g = make_gate()
    with pytest.raises(requests.ConnectionError):
        g.request("GET", "https://kap/x")
    assert g.failed == 1


# --- yayın işi: son iyi veri korunur -------------------------------------

REPORTS = {t: [{"disclosureIndex": str(i), "_consolidated": True, "year": 2026, "period": 9}]
           for i, t in enumerate(("AAA", "BBB", "CCC"), 1)}


@pytest.fixture
def kap_env(tmp_path, monkeypatch, clock):
    g = KapGate(min_interval=0, max_attempts=2, backoff_base=1, budget_seconds=300, breaker_threshold=2)
    monkeypatch.setattr(publish_kap, "DATA_DIR", tmp_path)
    monkeypatch.setattr(publish_kap, "load_universe", lambda: [{"ticker": t, "financial": False} for t in REPORTS])
    monkeypatch.setattr(publish_kap, "gate", g)
    monkeypatch.setattr(publish_kap, "build_periods", lambda ok: ([{"date": "2026-09-30", "revenue": 4.0}], []))
    monkeypatch.setattr(kap_financials, "CACHE_DIR", tmp_path / "cache")
    monkeypatch.setattr(kap_financials, "kap_get", lambda url, **kw: g.request("GET", url, **kw))
    monkeypatch.setattr(kap_financials, "parse_report", lambda h: {})
    monkeypatch.setattr(kap_financials, "decode_page", lambda b: "")
    monkeypatch.setattr(kap_financials, "report_snapshot",
                        lambda p: {"end": "2026-09-30", "currency": "TRY", "consolidated": True})
    monkeypatch.setattr(
        kap_financials.KapFinancials, "list_reports",
        lambda self, want, months=18: [r | {"_ticker": t} for t, rs in REPORTS.items() for r in rs])
    return tmp_path, g


def _prior(tmp_path, t):
    p = tmp_path / "kap" / f"{t}.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"ticker": t, "marker": "last-good"}), encoding="utf-8")
    return p


def test_run_kap_success_writes_all(kap_env, monkeypatch):
    tmp, _ = kap_env
    script(monkeypatch, lambda url: FakeResp(200))
    assert publish_kap.run_kap(workers=1) == 3
    assert json.loads((tmp / "kap" / "AAA.json").read_text(encoding="utf-8"))["source"] == "KAP"


def test_run_kap_429_storm_keeps_last_good_and_returns_partial(kap_env, monkeypatch):
    tmp, g = kap_env
    prior = {t: _prior(tmp, t) for t in REPORTS}
    n = {"c": 0}

    def resp(url):
        n["c"] += 1
        return FakeResp(200) if n["c"] == 1 else FakeResp(429)

    calls = script(monkeypatch, resp)
    assert publish_kap.run_kap(workers=1) == 1
    assert json.loads(prior["AAA"].read_text(encoding="utf-8"))["source"] == "KAP"
    for t in ("BBB", "CCC"):
        assert json.loads(prior[t].read_text(encoding="utf-8")) == {"ticker": t, "marker": "last-good"}
    assert g.stopped
    assert len(calls) <= 4  # devre kesici sonrası kalan hisselere istek gitmedi


def test_run_kap_incomplete_listing_changes_nothing(kap_env, monkeypatch):
    tmp, g = kap_env
    prior = _prior(tmp, "AAA")

    def listing(self, want, months=18):
        g.failed += 1  # bir pencere alınamadı
        return [{"disclosureIndex": "1", "_ticker": "AAA", "_consolidated": True}]

    monkeypatch.setattr(kap_financials.KapFinancials, "list_reports", listing)
    script(monkeypatch, lambda url: FakeResp(200))
    assert publish_kap.run_kap(workers=1) == 0
    assert json.loads(prior.read_text(encoding="utf-8"))["marker"] == "last-good"


def test_unparseable_report_is_not_a_fetch_failure(kap_env, monkeypatch):
    _, g = kap_env
    monkeypatch.setattr(kap_financials, "report_snapshot", lambda p: None)
    script(monkeypatch, lambda url: FakeResp(200))
    assert publish_kap.run_kap(workers=1) == 0
    assert not g.stopped
