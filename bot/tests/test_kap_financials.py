"""KAP finansal rapor ayrıştırıcısı — sentetik HTML (gerçek sayfanın yapısını taklit eder, ağ yok)."""
import pytest

from esham.sources.kap_financials import (
    build_periods,
    classify_statement,
    parse_report,
    parse_tr_number,
    report_snapshot,
)


def _row(role: str, n: int, concept: str, *vals: str) -> str:
    cells = "".join(f'<td class="taxonomy-context-value">{v}</td>' for v in vals)
    return (
        f'<tr class="{role}-row-{n} data-input-row"><td class="taxonomy-field-name-cell">'
        f'<div class="gwt-Label taxonomy-field-name">{concept}|</div></td>{cells}</tr>'
    )


def _table(header: str, rows: str) -> str:
    return f"<table><tbody><tr><td>{header}</td></tr>{rows}</tbody></table>"


def make_html(*, three_month: bool = True, end_month: str = "09", months: int = 9, scale: str = "1.000.000 TL",
              consolidated: str = "Konsolide") -> str:
    start = "01.01.2026"
    end = {"03": "31.03", "06": "30.06", "09": "30.09", "12": "31.12"}[end_month] + ".2026"
    income_head = f"Cari Dönem {start} - {end} Önceki Dönem 01.01.2025 - {end[:6]}2025"
    inc_vals = ["981.030", "690.825"]
    if three_month:
        income_head += f" Cari Dönem 3 Aylık 01.07.2026 - {end} Önceki Dönem 3 Aylık 01.07.2025 - {end[:6]}2025"
        inc_vals += ["395.961", "282.789"]

    def inc(vals_by_concept):
        return "".join(_row("general_role_310003", i, c, *v) for i, (c, v) in enumerate(vals_by_concept.items()))

    income_rows = inc({
        "ifrs-full_Revenue": inc_vals,
        "ifrs-full_CostOfSales": ["-870.649", "-572.138"] + (["-328.167", "-220.248"] if three_month else []),
        "ifrs-full_GrossProfit": ["110.381", "118.687"] + (["67.794", "62.541"] if three_month else []),
        "ifrs-full_ProfitLossFromOperatingActivities": ["39.026", "67.607"] + (["44.124", "43.078"] if three_month else []),
        "ifrs-full_ProfitLoss": ["80.228", "80.951"] + (["61.462", "56.016"] if three_month else []),
        "ifrs-full_ProfitLossAttributableToOwnersOfParent": ["80.330", "81.064"] + (["61.466", "56.051"] if three_month else []),
    })
    bal = "".join(_row("general_role_210015", i, c, *v) for i, (c, v) in enumerate({
        "ifrs-full_CashAndCashEquivalents": ["85.290", "86.035"],
        "ifrs-full_CurrentTradeReceivables": ["75.114", "45.791"],
        "ifrs-full_Inventories": ["55.498", "41.472"],
        "ifrs-full_CurrentAssets": ["559.178", "436.412"],
        "ifrs-full_Assets": ["2.583.379", "1.996.745"],
        "kap-fr_CurrentTradePayables": ["105.289", "78.640"],
        "ifrs-full_CurrentLiabilities": ["578.404", "442.076"],
        "kap-fr_CurrentBorrowingsFromUnrelatedParties": ["75.947", "70.069"],
        "kap-fr_CurrentPortionOfNoncurrentBorrowings": ["122.329", "92.367"],
        "ifrs-full_LongtermBorrowings": ["813.564", "601.817"],
        "ifrs-full_Liabilities": ["1.448.330", "1.085.489"],
        "ifrs-full_EquityAttributableToOwnersOfParent": ["1.135.117", "911.222"],
        "ifrs-full_Equity": ["1.135.049", "911.256"],
    }.items()))
    cf = "".join(_row("general_role_520003", i, c, *v) for i, (c, v) in enumerate({
        "ifrs-full_CashFlowsFromUsedInOperatingActivities": ["138.336", "137.929"],
        "ifrs-full_AdjustmentsForDepreciationAndAmortisationExpense": ["92.559", "67.762"],
        "ifrs-full_AdjustmentsForInterestExpense": ["25.303", "15.343"],
        "ifrs-full_PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities": ["-84.816", "-52.218"],
        "ifrs-full_DividendsPaidClassifiedAsFinancingActivities": ["0", "-8.951"],
    }.items()))
    meta = f"Sunum Para Birimi {scale} Finansal Tablo Niteliği {consolidated}"
    return (
        f"<div>{meta}</div>"
        + _table(f"Cari Dönem 30.09.2026 Önceki Dönem 31.12.2025", bal)
        + _table(income_head, income_rows)
        + _table(f"Cari Dönem {start} - {end} Önceki Dönem 01.01.2025 - {end[:6]}2025", cf)
    )


def test_parse_tr_number():
    assert parse_tr_number("2.583.379") == 2583379
    assert parse_tr_number("-870.649") == -870649
    assert parse_tr_number("1.234,5") == 1234.5
    assert parse_tr_number("0") == 0
    assert parse_tr_number("") is None and parse_tr_number("abc") is None and parse_tr_number("-") is None


def test_classify_statement():
    assert classify_statement({"ifrs-full_Assets", "ifrs-full_Liabilities"}) == "balance"
    assert classify_statement({"ifrs-full_Revenue", "ifrs-full_ProfitLoss"}) == "income"
    assert classify_statement({"ifrs-full_CashFlowsFromUsedInOperatingActivities"}) == "cashflow"
    assert classify_statement({"ifrs-full_Equity"}) is None


def test_parse_report_meta_and_columns():
    p = parse_report(make_html())
    assert p["scale"] == 1_000_000 and p["currency"] == "TRY" and p["consolidated"] is True
    assert set(p["statements"]) == {"balance", "income", "cashflow"}
    cols = p["statements"]["income"]["columns"]
    assert [(c["kind"], c["three_month"]) for c in cols] == [("current", False), ("previous", False), ("current", True), ("previous", True)]
    assert cols[0]["start"] == "2026-01-01" and cols[0]["end"] == "2026-09-30"
    assert p["statements"]["income"]["rows"]["Revenue"][:3] == [981030.0, 690825.0, 395961.0]


def test_non_consolidated_and_usd_scale():
    p = parse_report(make_html(scale="1.000 USD", consolidated="Konsolide Olmayan"))
    assert p["consolidated"] is False and p["currency"] == "USD" and p["scale"] == 1000


def test_snapshot_mapping_and_units():
    s = report_snapshot(parse_report(make_html()))
    assert s["end"] == "2026-09-30" and s["months"] == 9
    y, q, b = s["ytd"], s["quarter"], s["balance"]
    assert y["revenue"] == 981_030e6 and q["revenue"] == 395_961e6
    assert y["cogs"] == 870_649e6                      # KAP negatif yazar → mutlak değer
    assert y["net_income"] == 80_330e6                 # ana ortaklık payı, ProfitLoss değil
    assert y["capex"] == 84_816e6 and y["dividends_paid"] == 0
    assert y["ebitda"] == (39_026 + 92_559) * 1e6      # FVÖK + amortisman
    assert b["total_assets"] == 2_583_379e6 and b["equity"] == 1_135_117e6
    assert b["payables"] == 105_289e6                  # kap-fr_ önekli kavram da bulunur
    assert b["total_debt"] == (75_947 + 122_329 + 813_564) * 1e6


def test_build_periods_prefers_three_month_column():
    s = report_snapshot(parse_report(make_html()))
    q, a = build_periods([s])
    assert len(q) == 1 and a == []
    assert q[0]["revenue"] == 395_961e6 and q[0]["net_income"] == 61_466e6
    assert "revenue" not in q[0].get("derived", [])


def test_build_periods_derives_q4_and_annual():
    # Ç3 (9 ay kümülatif) + yıllık rapor (3 aylık sütun yok) → Ç4 = yıllık − 9 ay, `derived` işaretli
    s9 = report_snapshot(parse_report(make_html()))
    s12 = report_snapshot(parse_report(make_html(three_month=False, end_month="12", months=12)))
    s12["months"] = 12
    s12["ytd"] = {**s12["ytd"], "revenue": 1_400_000e6}
    q, a = build_periods([s12, s9])               # sırasız verilse de tarihe göre dizilmeli
    assert [x["date"] for x in q] == ["2026-09-30", "2026-12-31"]
    assert q[1]["revenue"] == pytest.approx((1_400_000 - 981_030) * 1e6)
    assert "revenue" in q[1]["derived"]
    assert len(a) == 1 and a[0]["revenue"] == 1_400_000e6


def test_snapshot_returns_none_without_core_statements():
    assert report_snapshot({"scale": 1, "currency": "TRY", "consolidated": True, "statements": {}}) is None
