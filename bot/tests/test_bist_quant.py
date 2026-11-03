"""Unit tests for BistQuantAnalyzer, key levels, and contract amount extraction."""
import pytest
from esham.sources.bist_quant import (
    BistQuantAnalyzer,
    KeyLevelsResult,
    FundamentalResult,
    extract_contract_amount,
    _fmt_try_money,
)


def test_fmt_try_money():
    assert _fmt_try_money(1_500_000_000) == "1.5 Milyar TL"
    assert _fmt_try_money(250_000_000) == "250.0 Milyon TL"
    assert "TL" in _fmt_try_money(50_000)


def test_extract_contract_amount():
    # Milyar TL
    res1 = extract_contract_amount("Yeni iş ilişkisi: Şirketimiz 1,5 milyar TL tutarında sözleşme imzaladı.")
    assert res1 == 1_500_000_000.0

    # Milyon TL
    res2 = extract_contract_amount("Toplam 750 milyon TL bedelle ihale kazanılmıştır.")
    assert res2 == 750_000_000.0

    # Milyon USD
    res3 = extract_contract_amount("Yurtdışı müşterisiyle 10 milyon USD bedelli anlaşma yapıldı.", usd_try=34.0)
    assert res3 == 340_000_000.0

    # Tam sayı formatı
    res4 = extract_contract_amount("Proje bedeli 500.000.000 TL olarak belirlenmiştir.")
    assert res4 == 500_000_000.0

    # Boş / geçersiz
    assert extract_contract_amount("") is None
    assert extract_contract_amount("Herhangi bir tutar içermeyen rutin bildirim.") is None


def test_key_levels_result_format():
    kl = KeyLevelsResult(
        ticker="THYAO",
        last_price=310.0,
        change_pct=1.5,
        pivot=308.0,
        r1=315.0,
        r2=320.0,
        s1=305.0,
        s2=300.0,
        fib_382=304.0,
        fib_500=307.0,
        fib_618=310.0,
        rsi_14=62.5,
        rsi_zone="NÖTR",
        sma_20=302.0,
        sma_50=295.0,
        support_20d=298.0,
        resistance_20d=318.0,
        year_high=330.0,
        year_low=220.0,
    )
    tbl = kl.format_table()
    assert "THYAO" in tbl
    assert "308.00 TL" in tbl
    assert "315.00 TL" in tbl
    d = kl.to_dict()
    assert d["ticker"] == "THYAO"
    assert d["pivot_noktasi"] == 308.0


def test_fundamental_result_format():
    fr = FundamentalResult(
        ticker="ASELS",
        company_name="Aselsan",
        sector="Savunma",
        industry="Elektronik",
        market_cap_try=250_000_000_000.0,
        market_cap_str="250.0 Milyar TL",
        trailing_pe=12.5,
        price_to_book=3.1,
        ev_to_ebitda=9.4,
        total_revenue_try=80_000_000_000.0,
        revenue_str="80.0 Milyar TL",
        profit_margin_pct=18.5,
        roe_pct=24.2,
        contract_analysis={
            "sozlesme_tutari_str": "15.0 Milyar TL",
            "ciro_orani_yuzde": 18.75,
            "tier": "TIER-1 (MEGA İŞ ANLAŞMASI)",
            "degerlendirme": "Hasılatın %10'undan fazlasına tekabül eden sözleşme.",
        },
    )
    tbl = fr.format_table()
    assert "ASELS" in tbl
    assert "250.0 Milyar TL" in tbl
    assert "TIER-1" in tbl
    assert "18.8" in tbl


def test_dcf_valuation_result_format():
    from esham.sources.bist_quant import DcfValuationResult, _fmt_money

    assert _fmt_money(2_500_000_000, "USD") == "2.50 Milyar USD"
    assert _fmt_money(-500_000_000, "TL") == "-500.00 Milyon TL"

    res = DcfValuationResult(
        ticker="THYAO",
        company_name="Türk Hava Yolları",
        currency="TRY",
        financial_currency="USD",
        current_price=260.0,
        shares_outstanding=1_372_283_353,
        base_fcf=2_281_000_000.0,
        base_fcf_str="2.28 Milyar USD",
        wacc=0.13,
        growth_rate=0.08,
        terminal_growth=0.035,
        projection_years=5,
        projected_fcfs=[
            {"yil": 1, "fcf": 2_463_480_000, "pv_fcf": 2_179_185_840, "buyume": 0.08},
            {"yil": 2, "fcf": 2_640_850_560, "pv_fcf": 2_068_173_357, "buyume": 0.072},
        ],
        pv_of_fcfs=8_120_000_000.0,
        terminal_value=21_650_000_000.0,
        pv_of_terminal_value=11_750_000_000.0,
        enterprise_value=19_870_000_000.0,
        total_cash=6_300_000_000.0,
        total_debt=19_500_000_000.0,
        net_debt=13_200_000_000.0,
        equity_value=6_670_000_000.0,
        fair_value_per_share=11.2,
        fair_value_try=383.04,
        upside_pct=47.3,
        rating="GÜÇLÜ İSKONTO (CAZİP)",
        sensitivity_matrix={
            "wacc_rates": [0.09, 0.11, 0.13, 0.15, 0.17],
            "terminal_rates": [0.015, 0.025, 0.035, 0.045, 0.055],
            "rows": [
                {"wacc": 0.13, "values": [320.0, 350.0, 383.04, 420.0, 465.0]}
            ],
        },
        scenarios={
            "bear": {"ad": "Ayı", "adil_deger_try": 310.0, "potansiyel_yuzde": 19.2},
            "base": {"ad": "Baz", "adil_deger_try": 383.04, "potansiyel_yuzde": 47.3},
            "bull": {"ad": "Boğa", "adil_deger_try": 460.0, "potansiyel_yuzde": 76.9},
        },
    )

    tbl = res.format_table()
    assert "THYAO" in tbl
    assert "383.04 TL" in tbl
    assert "GÜÇLÜ İSKONTO" in tbl
    d = res.to_dict()
    assert d["ticker"] == "THYAO"
    assert d["hisse_basina_adil_deger_try"] == 383.04
    assert "senaryolar" in d
