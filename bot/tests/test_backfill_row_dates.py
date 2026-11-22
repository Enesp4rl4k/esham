"""Satır tarihi göçü + committed veri dosyalarında her satırın tarihi (gelecekte olmayan, ayrıştırılabilir)."""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from esham.jobs import backfill_row_dates as bf

DATA = Path(__file__).resolve().parents[2] / "web" / "public" / "data"


def _w(p, o):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(o), encoding="utf-8")


def test_backfill_uses_each_rows_sibling_file_date_not_the_container_date(tmp_path):
    _w(tmp_path / "universe.json", {"updated_at": "2026-11-20T20:59:33+00:00", "stocks": [
        {"ticker": "NEW"}, {"ticker": "CARRIED"}, {"ticker": "NOFILE"}, {"ticker": "DONE", "updated_at": "2026-01-01T00:00:00+00:00"}]})
    _w(tmp_path / "stocks" / "NEW.json", {"updated_at": "2026-11-20T20:59:05+00:00"})
    _w(tmp_path / "stocks" / "CARRIED.json", {"updated_at": "2026-11-20T16:20:32+00:00"})
    _w(tmp_path / "universe-funds.json", {"updated_at": "2026-11-20T23:00:37+03:00", "funds": [{"code": "AFT"}]})
    _w(tmp_path / "funds" / "AFT.json", {"updated_at": "2026-11-20T22:10:00+03:00"})
    res = bf.run(tmp_path)
    assert res == {"stocks": (2, 1), "funds": (1, 0)}
    rows = {r["ticker"]: r for r in json.loads((tmp_path / "universe.json").read_text(encoding="utf-8"))["stocks"]}
    assert rows["NEW"]["updated_at"] == "2026-11-20T20:59:05+00:00"
    assert rows["CARRIED"]["updated_at"] == "2026-11-20T16:20:32+00:00"  # eski tur: dosya damgası DEĞİL
    assert "updated_at" not in rows["NOFILE"]  # uydurma tarih yok
    assert rows["DONE"]["updated_at"] == "2026-01-01T00:00:00+00:00"
    assert json.loads((tmp_path / "universe.json").read_text(encoding="utf-8"))["updated_at"] == "2026-11-20T20:59:33+00:00"
    assert bf.run(tmp_path) == {"stocks": (0, 1), "funds": (0, 0)}  # idempotent


def _parse(ts):
    d = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def test_every_committed_universe_and_fund_row_has_a_valid_non_future_updated_at():
    now = datetime.now(timezone.utc) + timedelta(minutes=5)
    for fname, key in (("universe.json", "stocks"), ("universe-funds.json", "funds")):
        rows = json.loads((DATA / fname).read_text(encoding="utf-8"))[key]
        assert rows
        bad = [r.get("ticker") or r.get("code") for r in rows if not r.get("updated_at") or _parse(r["updated_at"]) > now]
        assert not bad, (fname, bad[:5])
