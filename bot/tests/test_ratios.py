"""Oran motoru testleri — elle doğrulanmış sentetik şirket."""
import pytest

from esham import ratios as R


def q(date, **kw):
    return {"date": date, **kw}


QUARTERS = [
    q("2024-12-31", revenue=100, gross_profit=30, ebit=15, ebitda=20, net_income=10, cfo=18, capex=-8,
      interest_expense=-3, total_assets=500, current_assets=200, current_liabilities=120, cash=40,
      inventory=50, receivables=60, payables=45, total_debt=150, equity=250, cogs=70),
    q("2025-03-31", revenue=110, gross_profit=33, ebit=17, ebitda=22, net_income=11, cfo=20, capex=-9),
    q("2025-06-30", revenue=120, gross_profit=36, ebit=18, ebitda=24, net_income=12, cfo=21, capex=-9),
    q("2025-09-30", revenue=130, gross_profit=39, ebit=20, ebitda=26, net_income=13, cfo=23, capex=-10,
      interest_expense=-4, total_assets=600, current_assets=240, current_liabilities=150, cash=60,
      inventory=60, receivables=70, payables=50, total_debt=170, equity=300),
]


def test_ttm_sums_last_four_quarters():
    assert R.ttm(QUARTERS, "revenue") == 460
    assert R.ttm(QUARTERS[:3], "revenue") is None  # 4 çeyrek yok


def test_ttm_missing_value_returns_none():
    qs = [dict(x) for x in QUARTERS]
    qs[1]["revenue"] = None
    assert R.ttm(qs, "revenue") is None


def test_snapshot_uses_latest_balance_sheet():
    snap = R.build_ttm_snapshot(QUARTERS, [])
    assert snap["revenue"] == 460 and snap["net_income"] == 46
    assert snap["equity"] == 300 and snap["total_assets"] == 600
    assert snap["_basis"] == 1.0


def test_snapshot_falls_back_to_annual():
    annual = [q("2024-12-31", revenue=400, net_income=40, equity=250, total_assets=500)]
    snap = R.build_ttm_snapshot([], annual)
    assert snap["revenue"] == 400 and snap["_basis"] == 0.0


def test_valuation_and_profitability():
    snap = R.build_ttm_snapshot(QUARTERS, [])
    r = R.compute_ratios(snap, price=10.0, market_cap=460.0, dividend_per_share_ttm=0.5)
    assert r["pe"] == 10.0                      # 460 / 46
    assert r["pb"] == pytest.approx(1.53, abs=0.01)  # 460 / 300
    assert r["net_margin"] == 10.0              # 46 / 460
    assert r["roe"] == pytest.approx(15.33, abs=0.01)
    assert r["dividend_yield"] == 5.0
    assert r["net_debt"] == 110                 # 170 - 60
    assert r["enterprise_value"] == 570
    assert r["ev_ebitda"] == pytest.approx(570 / 92, abs=0.01)
    assert r["net_debt_ebitda"] == pytest.approx(110 / 92, abs=0.01)
    assert r["fcf"] == 46                       # cfo 82 - capex 36
    assert r["current_ratio"] == 1.6
    assert r["quick_ratio"] == 1.2              # (240-60)/150


def test_negative_earnings_gives_none_multiples():
    snap = R.build_ttm_snapshot(QUARTERS, [])
    snap["net_income"] = -5
    r = R.compute_ratios(snap, price=10, market_cap=460)
    assert r["pe"] is None
    assert r["net_margin"] < 0


def test_zero_denominators_are_none_not_crash():
    r = R.compute_ratios({"net_income": 5}, price=None, market_cap=None)
    assert r["pe"] is None and r["pb"] is None and r["roe"] is None


def test_financial_company_gets_reduced_set():
    snap = {"net_income": 100, "equity": 800, "total_assets": 9000, "revenue": 500, "ebitda": None}
    r = R.compute_ratios(snap, price=20, market_cap=1000, financial=True)
    assert set(r) == set(R.FINANCIAL_RATIO_KEYS)
    assert r["pe"] == 10.0 and r["pb"] == 1.25 and r["equity_to_assets"] == pytest.approx(8.89, abs=0.01)


def test_growth_rules():
    assert R.growth(120, 100) == 20.0
    assert R.growth(50, -10) is None   # önceki negatif → tanımsız
    assert R.growth(50, None) is None
    assert R.cagr(100, 200, 3) == pytest.approx(25.99, abs=0.01)
    assert R.cagr(-1, 5, 3) is None


def test_growth_series_lag():
    ps = [q("2023", revenue=100), q("2024", revenue=110), q("2025", revenue=132)]
    s = R.growth_series(ps, "revenue", 1)
    assert s[0]["growth_pct"] is None and s[1]["growth_pct"] == 10.0 and s[2]["growth_pct"] == 20.0


def test_cash_cycle_and_roic():
    snap = R.build_ttm_snapshot(QUARTERS, [])
    r = R.compute_ratios(snap, price=10, market_cap=460)
    # DSO 70/460*365, DIO 60/(460-138)*365, DPO 50/322*365
    assert r["dso_days"] == pytest.approx(55.5, abs=1)
    assert r["cash_cycle_days"] == pytest.approx(r["dso_days"] + r["dio_days"] - r["dpo_days"])
    assert r["roic"] == pytest.approx(70 * 0.75 / (300 + 170 - 60) * 100, abs=0.1)


def test_quarterly_history_series():
    qs = [
        q("2025-06-30", revenue=100, gross_profit=30, ebitda=20, net_income=10,
          total_assets=500, equity=200, current_assets=150, current_liabilities=100),
        q("2025-09-30", revenue=0, total_assets=0, equity=-5),
    ]
    h = R.quarterly_history(qs)
    assert h[0]["gross_margin"] == 30.0 and h[0]["net_margin"] == 10.0
    assert h[0]["current_ratio"] == 1.5
    assert h[0]["leverage"] == 60.0            # (500-200)/500
    assert h[0]["roe_annualized"] == 20.0      # 10*4/200
    assert h[1]["gross_margin"] is None and h[1]["leverage"] is None and h[1]["roe_annualized"] is None


def test_outlier_flags():
    ok = R.outlier_flags({"pe": 10, "pb": 1.2, "roe": 20, "dividend_yield": 3}, {"pe": 11}, "TRY")
    assert ok == []
    assert "temettu_verimi_uc" in R.outlier_flags({"dividend_yield": 24}, None, "TRY")
    assert "carpan_uc_deger" in R.outlier_flags({"pe": 1.5}, None, "TRY")
    assert "roe_uc_deger" in R.outlier_flags({"roe": -208}, None, "TRY")
    # Yahoo ile >%35 fark → şüpheli; dövizli raporlayanda karşılaştırma yapılmaz
    assert "pe_yahoo_farkli" in R.outlier_flags({"pe": 10.9}, {"pe": 188}, "TRY")
    assert R.outlier_flags({"pe": 3.35, "pb": 0.37}, {"pe": 80}, "USD") == []


def test_outlier_flag_low_ev_ebitda():
    assert "carpan_uc_deger" in R.outlier_flags({"ev_ebitda": 0.81}, None, "TRY")
    assert R.outlier_flags({"ev_ebitda": 4.5}, None, "TRY") == []
