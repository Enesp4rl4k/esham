"""Fintables tarzı finansal oran motoru — saf fonksiyonlar, ağ yok.

Girdi: normalize edilmiş dönem listesi (``Period``) + fiyat/piyasa değeri.
Çıktı: oran sözlüğü (TTM), yıllık seri ve büyüme.

Kurallar
--------
- Payda 0/None/negatif anlamsızsa oran ``None`` döner (UI "—" gösterir), asla 0 değil.
- Akım kalemleri (gelir tablosu/nakit akışı) TTM = son 4 çeyreğin toplamı.
  Stok kalemleri (bilanço) son dönem sonu değeridir.
- Finansal şirketlerde (banka/sigorta) FAVÖK, FD, stok vb. anlamsızdır;
  yalnızca ``FINANCIAL_RATIO_KEYS`` hesaplanır.
"""
from __future__ import annotations

from typing import Any

Period = dict[str, Any]  # {"date": "2025-12-31", "revenue": ..., ...}; eksik kalem = anahtar yok/None

FLOW_KEYS = (
    "revenue", "gross_profit", "ebit", "ebitda", "net_income",
    "interest_expense", "cfo", "capex", "cogs", "dividends_paid",
)
STOCK_KEYS = (
    "total_assets", "current_assets", "current_liabilities", "cash", "inventory",
    "receivables", "payables", "total_debt", "equity", "total_liabilities", "shares",
)
FINANCIAL_RATIO_KEYS = (
    "pe", "pb", "roe", "roa", "net_margin", "equity_to_assets",
    "dividend_yield", "market_cap",
)


def _num(v: Any) -> float | None:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if f != f else f  # NaN -> None


def div(a: Any, b: Any, *, positive_denominator: bool = False) -> float | None:
    """Güvenli bölme. ``positive_denominator`` True ise b <= 0 → None."""
    x, y = _num(a), _num(b)
    if x is None or y is None or y == 0:
        return None
    if positive_denominator and y < 0:
        return None
    return x / y


def pct(a: Any, b: Any) -> float | None:
    r = div(a, b)
    return None if r is None else round(r * 100, 2)


def _r(v: float | None, nd: int = 2) -> float | None:
    return None if v is None else round(v, nd)


def ttm(quarters: list[Period], key: str) -> float | None:
    """Son 4 çeyreğin toplamı; 4 çeyrekten biri eksikse None."""
    last4 = quarters[-4:]
    if len(last4) < 4:
        return None
    vals = [_num(q.get(key)) for q in last4]
    if any(v is None for v in vals):
        return None
    return sum(vals)  # type: ignore[arg-type]


def latest(periods: list[Period], key: str) -> float | None:
    for p in reversed(periods):
        v = _num(p.get(key))
        if v is not None:
            return v
    return None


def build_ttm_snapshot(quarters: list[Period], annual: list[Period]) -> dict[str, float | None]:
    """TTM akım kalemleri + son bilanço. Çeyreklik yetersizse son yıllığa düşer."""
    snap: dict[str, float | None] = {}
    use_q = len(quarters) >= 4
    for k in FLOW_KEYS:
        snap[k] = ttm(quarters, k) if use_q else latest(annual, k)
        if snap[k] is None and use_q:
            snap[k] = latest(annual, k)
    src = quarters if quarters else annual
    for k in STOCK_KEYS:
        snap[k] = latest(src, k)
        if snap[k] is None:
            snap[k] = latest(annual, k)
    if snap.get("ebitda") is None and snap.get("ebit") is not None:
        snap["ebitda"] = snap["ebit"]  # amortisman bilinmiyorsa alt sınır; UI notu için ayrı bayrak
        snap["_ebitda_approx"] = 1.0
    snap["_basis"] = 1.0 if use_q else 0.0  # 1=TTM, 0=yıllık
    return snap


def compute_ratios(
    snap: dict[str, float | None],
    *,
    price: float | None,
    market_cap: float | None,
    dividend_per_share_ttm: float | None = None,
    financial: bool = False,
) -> dict[str, float | None]:
    """TTM anlık görüntüsünden oran seti. Tutarlar TL, oranlar x veya %."""
    s = snap
    mcap = _num(market_cap)
    if mcap is None and price and s.get("shares"):
        mcap = price * s["shares"]  # type: ignore[operator]

    debt = s.get("total_debt")
    cash = s.get("cash")
    net_debt = None if debt is None or cash is None else debt - cash
    ev = None if mcap is None or net_debt is None else mcap + net_debt

    out: dict[str, float | None] = {
        "market_cap": _r(mcap, 0),
        "pe": _r(div(mcap, s.get("net_income"), positive_denominator=True)),
        "pb": _r(div(mcap, s.get("equity"), positive_denominator=True)),
        "roe": pct(s.get("net_income"), s.get("equity")) if (s.get("equity") or 0) > 0 else None,
        "roa": pct(s.get("net_income"), s.get("total_assets")),
        "net_margin": pct(s.get("net_income"), s.get("revenue")),
        "equity_to_assets": pct(s.get("equity"), s.get("total_assets")),
        "dividend_yield": pct(dividend_per_share_ttm, price) if price else None,
    }
    if financial:
        return {k: out.get(k) for k in FINANCIAL_RATIO_KEYS}

    ebitda = s.get("ebitda")
    out.update({
        "enterprise_value": _r(ev, 0),
        "net_debt": _r(net_debt, 0),
        "ev_ebitda": _r(div(ev, ebitda, positive_denominator=True)),
        "ev_sales": _r(div(ev, s.get("revenue"), positive_denominator=True)),
        "p_sales": _r(div(mcap, s.get("revenue"), positive_denominator=True)),
        "gross_margin": pct(s.get("gross_profit"), s.get("revenue")),
        "ebit_margin": pct(s.get("ebit"), s.get("revenue")),
        "ebitda_margin": pct(ebitda, s.get("revenue")),
        "roic": _roic(s),
        "net_debt_ebitda": _r(div(net_debt, ebitda, positive_denominator=True)),
        "debt_to_equity": _r(div(debt, s.get("equity"), positive_denominator=True)),
        "interest_coverage": _r(div(s.get("ebit"), abs(s["interest_expense"]) if s.get("interest_expense") else None)),
        "current_ratio": _r(div(s.get("current_assets"), s.get("current_liabilities"), positive_denominator=True)),
        "quick_ratio": _r(div(
            None if s.get("current_assets") is None else s["current_assets"] - (s.get("inventory") or 0),  # type: ignore[operator]
            s.get("current_liabilities"), positive_denominator=True)),
        "fcf": _fcf(s),
        "fcf_yield": pct(_fcf(s), mcap) if mcap else None,
        "asset_turnover": _r(div(s.get("revenue"), s.get("total_assets"), positive_denominator=True)),
    })
    cogs = s.get("cogs") if s.get("cogs") is not None else (
        None if s.get("revenue") is None or s.get("gross_profit") is None else s["revenue"] - s["gross_profit"])  # type: ignore[operator]
    out["dso_days"] = _r(_days(s.get("receivables"), s.get("revenue")), 0)
    out["dio_days"] = _r(_days(s.get("inventory"), cogs), 0)
    out["dpo_days"] = _r(_days(s.get("payables"), cogs), 0)
    if None not in (out["dso_days"], out["dio_days"], out["dpo_days"]):
        out["cash_cycle_days"] = out["dso_days"] + out["dio_days"] - out["dpo_days"]  # type: ignore[operator]
    else:
        out["cash_cycle_days"] = None
    return out


def _days(balance: float | None, flow: float | None) -> float | None:
    r = div(balance, flow, positive_denominator=True)
    return None if r is None else r * 365


def _fcf(s: dict[str, float | None]) -> float | None:
    cfo, capex = s.get("cfo"), s.get("capex")
    if cfo is None or capex is None:
        return None
    return round(cfo - abs(capex), 0)  # capex işareti kaynağa göre değişir → mutlak değer


def _roic(s: dict[str, float | None]) -> float | None:
    """NOPAT / yatırılan sermaye; vergi oranı sabit %25 (TR kurumlar vergisi)."""
    ebit, eq, debt, cash = s.get("ebit"), s.get("equity"), s.get("total_debt"), s.get("cash")
    if None in (ebit, eq, debt, cash):
        return None
    invested = eq + debt - cash  # type: ignore[operator]
    if invested <= 0:
        return None
    return pct(ebit * 0.75, invested)  # type: ignore[operator]


def growth(cur: Any, prev: Any) -> float | None:
    """Büyüme %. Önceki dönem <= 0 ise tanımsız (işaret değişimi yanıltıcı) → None."""
    c, p = _num(cur), _num(prev)
    if c is None or p is None or p <= 0:
        return None
    return round((c / p - 1) * 100, 2)


def cagr(first: Any, last: Any, years: float) -> float | None:
    f, l = _num(first), _num(last)
    if f is None or l is None or f <= 0 or l <= 0 or years <= 0:
        return None
    return round(((l / f) ** (1 / years) - 1) * 100, 2)


def growth_series(periods: list[Period], key: str, lag: int) -> list[dict[str, Any]]:
    """Her dönem için ``lag`` dönem öncesine göre büyüme (yıllık: lag=1, çeyreklik YoY: lag=4)."""
    out = []
    for i, p in enumerate(periods):
        prev = periods[i - lag].get(key) if i - lag >= 0 else None
        out.append({"date": p.get("date"), "value": _num(p.get(key)), "growth_pct": growth(p.get(key), prev)})
    return out


def quarterly_history(quarters: list[Period]) -> list[dict[str, Any]]:
    """Çeyrek bazlı marj ve bilanço oranı serisi (grafikler için).

    Marjlar o çeyreğin kendi gelirine göre. ROE yıllıklandırılmış (çeyrek net kâr × 4 / özkaynak):
    yalnızca ~6-7 çeyrek veri olduğundan gerçek TTM-ROE serisi kurulamaz.
    Kaldıraç = toplam yükümlülük / toplam aktif (%); yükümlülük yoksa aktif − özkaynak.
    """
    out = []
    for p in quarters:
        assets, equity = _num(p.get("total_assets")), _num(p.get("equity"))
        liab = _num(p.get("total_liabilities"))
        if liab is None and assets is not None and equity is not None:
            liab = assets - equity
        ni = _num(p.get("net_income"))
        out.append({
            "date": p.get("date"),
            "gross_margin": pct(p.get("gross_profit"), p.get("revenue")),
            "ebitda_margin": pct(p.get("ebitda"), p.get("revenue")),
            "net_margin": pct(ni, p.get("revenue")),
            "current_ratio": _r(div(p.get("current_assets"), p.get("current_liabilities"), positive_denominator=True)),
            "leverage": pct(liab, assets) if (assets or 0) > 0 else None,
            "roe_annualized": pct(None if ni is None else ni * 4, equity) if (equity or 0) > 0 else None,
        })
    return out


def ratio_history(annual: list[Period]) -> list[dict[str, Any]]:
    """Yıllık dönem sonu bazında marj/ROE/ROA/borçluluk geçmişi (fiyatsız oranlar)."""
    hist = []
    for p in annual:
        debt, cash, ebitda = _num(p.get("total_debt")), _num(p.get("cash")), _num(p.get("ebitda"))
        nd = None if debt is None or cash is None else debt - cash
        hist.append({
            "date": p.get("date"),
            "gross_margin": pct(p.get("gross_profit"), p.get("revenue")),
            "ebitda_margin": pct(ebitda, p.get("revenue")),
            "net_margin": pct(p.get("net_income"), p.get("revenue")),
            "roe": pct(p.get("net_income"), p.get("equity")) if (_num(p.get("equity")) or 0) > 0 else None,
            "roa": pct(p.get("net_income"), p.get("total_assets")),
            "net_debt_ebitda": _r(div(nd, ebitda, positive_denominator=True)),
            "current_ratio": _r(div(p.get("current_assets"), p.get("current_liabilities"), positive_denominator=True)),
        })
    return hist
