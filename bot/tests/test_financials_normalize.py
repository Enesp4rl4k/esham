"""Yahoo DataFrame → Period normalizasyonu (ağsız)."""
import pandas as pd

from esham.sources.financials import dividend_ttm, normalize_frames
from esham.universe import is_financial, load_universe


def _df(rows: dict, cols: list[str]) -> pd.DataFrame:
    return pd.DataFrame(rows, index=pd.to_datetime(cols)).T


def test_normalize_merges_statements_sorted_oldest_first():
    cols = ["2025-12-31", "2025-09-30"]
    inc = _df({"Total Revenue": [200.0, 180.0], "Net Income": [20.0, 18.0], "EBIT": [30.0, 27.0]}, cols)
    bal = _df({"Total Assets": [1000.0, 950.0], "Stockholders Equity": [400.0, 380.0]}, cols)
    cf = _df({"Operating Cash Flow": [50.0, 45.0], "Depreciation And Amortization": [10.0, 9.0]}, cols)
    ps = normalize_frames(inc, bal, cf)
    assert [p["date"] for p in ps] == ["2025-09-30", "2025-12-31"]
    assert ps[1]["revenue"] == 200 and ps[1]["equity"] == 400 and ps[1]["cfo"] == 50
    assert ps[1]["ebitda"] == 40          # EBITDA satırı yok → EBIT + amortisman


def test_missing_rows_stay_none_and_nan_ignored():
    inc = _df({"Total Revenue": [float("nan")], "Operating Revenue": [150.0]}, ["2025-12-31"])
    ps = normalize_frames(inc, None, None)
    assert ps[0]["revenue"] == 150        # NaN satırı atlanıp yedek satıra düşer
    assert ps[0]["total_assets"] is None


def test_gross_profit_derived_from_cogs():
    inc = _df({"Total Revenue": [100.0], "Cost Of Revenue": [70.0]}, ["2025-12-31"])
    assert normalize_frames(inc, None, None)[0]["gross_profit"] == 30


def test_dividend_ttm_window():
    divs = [("2024-01-10", 1.0), ("2025-06-01", 2.0), ("2025-12-01", 3.0)]
    assert dividend_ttm(divs, "2026-01-01") == 5.0   # 2024 olan dışarıda
    assert dividend_ttm(divs, "2027-06-01") == 0.0


def test_universe_unique_and_banks_flagged():
    u = load_universe()
    tickers = [x["ticker"] for x in u]
    assert len(tickers) == len(set(tickers)) >= 100
    assert is_financial("GARAN") and not is_financial("THYAO")
