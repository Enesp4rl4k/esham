"""Yahoo Finance bilanço/gelir/nakit akışı → normalize ``Period`` listesi.

Yahoo'nun satır adları şirkete göre değişir; ``ROW_MAP`` her normalize kalem için
sırayla denenecek satır adlarını tutar. Eksik kalem ``None`` kalır (uydurma yok).
Ağ gerektirmeyen kısım (``normalize_frames``) pandas DataFrame alır → test edilebilir.
"""
from __future__ import annotations

import math
from typing import Any

from ..config import get_logger
from ..ratios import Period

log = get_logger(__name__)

# normalize kalem → (statement, [denenecek satırlar])
ROW_MAP: dict[str, tuple[str, list[str]]] = {
    "revenue": ("income", ["Total Revenue", "Operating Revenue"]),
    "cogs": ("income", ["Cost Of Revenue", "Reconciled Cost Of Revenue"]),
    "gross_profit": ("income", ["Gross Profit"]),
    "ebit": ("income", ["EBIT", "Operating Income", "Total Operating Income As Reported"]),
    "ebitda": ("income", ["EBITDA", "Normalized EBITDA"]),
    "net_income": ("income", ["Net Income Common Stockholders", "Net Income"]),
    "interest_expense": ("income", ["Interest Expense", "Interest Expense Non Operating"]),
    "total_assets": ("balance", ["Total Assets"]),
    "current_assets": ("balance", ["Current Assets"]),
    "current_liabilities": ("balance", ["Current Liabilities"]),
    "cash": ("balance", ["Cash Cash Equivalents And Short Term Investments", "Cash And Cash Equivalents"]),
    "inventory": ("balance", ["Inventory"]),
    "receivables": ("balance", ["Accounts Receivable", "Receivables"]),
    "payables": ("balance", ["Accounts Payable", "Payables"]),
    "total_debt": ("balance", ["Total Debt"]),
    "equity": ("balance", ["Stockholders Equity", "Common Stock Equity"]),
    "total_liabilities": ("balance", ["Total Liabilities Net Minority Interest"]),
    "shares": ("balance", ["Ordinary Shares Number", "Share Issued"]),
    "cfo": ("cashflow", ["Operating Cash Flow"]),
    "capex": ("cashflow", ["Capital Expenditure", "Purchase Of PPE"]),
    "dividends_paid": ("cashflow", ["Cash Dividends Paid", "Common Stock Dividend Paid"]),
}


def _cell(df: Any, rows: list[str], col: Any) -> float | None:
    if df is None or getattr(df, "empty", True):
        return None
    for row in rows:
        if row in df.index:
            v = df.at[row, col] if col in df.columns else None
            try:
                f = float(v)
            except (TypeError, ValueError):
                continue
            if not math.isnan(f):
                return f
    return None


def normalize_frames(income: Any, balance: Any, cashflow: Any) -> list[Period]:
    """Üç DataFrame'i tarih bazında birleştirir; eskiden yeniye sıralı Period listesi."""
    frames = {"income": income, "balance": balance, "cashflow": cashflow}
    dates: set[Any] = set()
    for df in frames.values():
        if df is not None and not getattr(df, "empty", True):
            dates.update(df.columns)
    periods: list[Period] = []
    for col in sorted(dates):
        p: Period = {"date": str(getattr(col, "date", lambda: col)())}
        for key, (stmt, rows) in ROW_MAP.items():
            p[key] = _cell(frames[stmt], rows, col)
        # Yahoo bazen ebitda vermez; EBIT + amortisman yedeği
        if p.get("ebitda") is None and p.get("ebit") is not None:
            da = _cell(frames["cashflow"], ["Depreciation And Amortization", "Depreciation"], col)
            if da is not None:
                p["ebitda"] = p["ebit"] + da
        if p.get("gross_profit") is None and p.get("revenue") is not None and p.get("cogs") is not None:
            p["gross_profit"] = p["revenue"] - p["cogs"]
        periods.append(p)
    return periods


def fetch_financials(ticker: str) -> dict[str, Any] | None:
    """{quarterly, annual, price, market_cap, dividends, currency} veya veri yoksa None."""
    import yfinance as yf

    sym = f"{ticker.strip().upper().replace('.IS', '')}.IS"
    try:
        t = yf.Ticker(sym)
        quarterly = normalize_frames(t.quarterly_income_stmt, t.quarterly_balance_sheet, t.quarterly_cashflow)
        annual = normalize_frames(t.income_stmt, t.balance_sheet, t.cashflow)
        if not quarterly and not annual:
            return None
        info = t.info or {}
        divs = t.dividends
        return {
            "quarterly": quarterly,
            "annual": annual,
            "price": info.get("currentPrice") or info.get("regularMarketPrice"),
            "market_cap": info.get("marketCap"),
            "name": info.get("longName") or info.get("shortName"),
            # Yahoo'nun kendi çarpanı: yalnızca çapraz kontrol için (bkz. ratios.outlier_flags)
            "yahoo_ref": {"pe": info.get("trailingPE"), "pb": info.get("priceToBook")},
            "currency": info.get("financialCurrency") or "TRY",
            "dividends": [(str(d.date()), float(v)) for d, v in divs.items()] if divs is not None else [],
        }
    except Exception as exc:  # ağ/şema hatası tek hisseyi düşürmemeli
        log.warning("Finansallar alınamadı %s: %s", sym, exc)
        return None


def dividend_ttm(dividends: list[tuple[str, float]], as_of: str) -> float:
    """as_of tarihinden geriye 365 gün içindeki hisse başı brüt temettü toplamı (yoksa 0)."""
    from datetime import date, timedelta

    end = date.fromisoformat(as_of)
    start = end - timedelta(days=365)
    return sum(v for d, v in dividends if start < date.fromisoformat(d) <= end)


_FX_CACHE: dict[str, float | None] = {}


def fx_to_try(currency: str) -> float | None:
    """1 birim ``currency`` kaç TL (güncel kur). TRY için 1.0; alınamazsa None."""
    cur = (currency or "TRY").upper()
    if cur == "TRY":
        return 1.0
    if cur not in _FX_CACHE:
        try:
            import yfinance as yf

            h = yf.Ticker(f"{cur}TRY=X").history(period="5d")
            _FX_CACHE[cur] = float(h["Close"].dropna().iloc[-1])
        except Exception as exc:
            log.warning("Kur alınamadı %sTRY: %s", cur, exc)
            _FX_CACHE[cur] = None
    return _FX_CACHE[cur]
