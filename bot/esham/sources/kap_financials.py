"""KAP "Finansal Rapor" bildirimlerinden IFRS/XBRL tablolarını okur (birincil, doğrulanabilir kaynak).

Neden: Yahoo'nun satır adları ve para birimi etiketleri güvenilmez (THYAO tablosu Yahoo'da USD,
KAP'ta 1.000.000 TL). KAP bildirim detay sayfası tabloları ``ifrs-full_Revenue`` gibi XBRL kavram
kodlarıyla verir → eşleme deterministik.

Sayfa yapısı (13 Kas 2026'da doğrulandı):
- HTML, ``self.__next_f.push([1,"..."])`` parçalarında JSON-kaçışlı gömülü.
- Her tablo bir ``*_role_<n>``: satırlar ``tr.data-input-row``; kavram ``.taxonomy-field-name``
  (``ifrs-full_Revenue|...``); değerler ``td.taxonomy-context-value`` (Türkçe sayı biçimi).
- Başlık metni: "Sunum Para Birimi 1.000.000 TL", "Finansal Tablo Niteliği Konsolide",
  "Cari Dönem 01.01.2026 - 30.09.2026", "Cari Dönem 3 Aylık 01.07.2026 - 30.09.2026", ...
- Gelir tablosu sütunları: [kümülatif cari, kümülatif önceki, 3 aylık cari, 3 aylık önceki];
  bilanço: [cari dönem sonu, önceki yıl sonu]; nakit akışı yalnızca kümülatif.

Bu modül ağsız çalışan saf fonksiyonlar (``parse_report``, ``build_periods``) + ince bir indirme
katmanı (``KapFinancials``) içerir. Parse sonuçları ``bot/cache/kap`` altında bildirim numarasıyla
önbelleğe alınır (rapor başına ~5 MB HTML; yalnızca yeni raporlar indirilir).
"""
from __future__ import annotations

import json
import re
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from ..config import default_headers, get_logger, settings
from ..http import retry_get, retry_post
from ..ratios import Period

log = get_logger(__name__)

BASE_URL = "https://www.kap.org.tr"
QUERY_URL = f"{BASE_URL}/tr/api/disclosure/members/byCriteria"
MAX_ROWS = 1990  # KAP byCriteria üst sınırı 2000 satır
CACHE_DIR = Path(__file__).resolve().parents[2] / "cache" / "kap"

# Normalize kalem → (statement, [kavram ekleri (ön eksiz), ...]); ilk bulunan kullanılır.
# işaret: "abs" → mutlak değer (KAP gider/ödemeleri negatif yazar)
INCOME_MAP: dict[str, tuple[list[str], str]] = {
    "revenue": (["Revenue"], ""),
    "cogs": (["CostOfSales"], "abs"),
    "gross_profit": (["GrossProfit", "GrossProfitLossFromCommercialOperations"], ""),
    "ebit": (["ProfitLossFromOperatingActivities"], ""),
    "net_income": (["ProfitLossAttributableToOwnersOfParent", "ProfitLoss"], ""),
}
BALANCE_MAP: dict[str, tuple[list[str], str]] = {
    "total_assets": (["Assets"], ""),
    "current_assets": (["CurrentAssets"], ""),
    "current_liabilities": (["CurrentLiabilities"], ""),
    "cash": (["CashAndCashEquivalents"], ""),
    "inventory": (["Inventories"], ""),
    "receivables": (["CurrentTradeReceivables"], ""),
    "payables": (["CurrentTradePayables"], ""),
    "total_liabilities": (["Liabilities"], ""),
    "equity": (["EquityAttributableToOwnersOfParent", "Equity"], ""),
}
CASHFLOW_MAP: dict[str, tuple[list[str], str]] = {
    "cfo": (["CashFlowsFromUsedInOperatingActivities"], ""),
    "capex": (["PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities",
               "PurchaseOfPropertyPlantEquipmentAndIntangibleAssetsClassifiedAsInvestingActivities"], "abs"),
    "dividends_paid": (["DividendsPaidClassifiedAsFinancingActivities"], "abs"),
    "_da": (["AdjustmentsForDepreciationAndAmortisationExpense"], ""),
    "interest_expense": (["AdjustmentsForInterestExpense"], ""),
}
# Finansal borç = kısa vadeli borçlanma + uzun vadeli borçlananın kısa kısmı + uzun vadeli borçlanma
DEBT_PARTS: list[list[str]] = [
    ["CurrentBorrowings", "CurrentBorrowingsFromUnrelatedParties"],
    ["CurrentPortionOfNoncurrentBorrowings", "CurrentPortionOfNoncurrentBorrowingsFromUnrelatedParties"],
    ["LongtermBorrowings", "LongTermBorrowingsFromUnrelatedParties"],
]

_PERIOD_RE = re.compile(
    r"(Cari|Önceki)\s+Dönem(\s+3\s+Aylık)?\s+(\d{2}\.\d{2}\.\d{4})(?:\s*-\s*(\d{2}\.\d{2}\.\d{4}))?"
)


def parse_tr_number(s: str) -> float | None:
    """'2.583.379' → 2583379; '-870.649' → -870649; '1.234,5' → 1234.5; boş/geçersiz → None."""
    t = (s or "").strip().replace("\xa0", "").replace(" ", "")
    if not t or t in {"-", "—"}:
        return None
    t = t.replace(".", "").replace(",", ".")
    try:
        return float(t)
    except ValueError:
        return None


def _iso(d: str) -> str:
    dd, mm, yy = d.split(".")
    return f"{yy}-{mm}-{dd}"


def _concept(tr: Any) -> str | None:
    nm = tr.select_one(".taxonomy-field-name")
    if not nm:
        return None
    return nm.get_text(strip=True).split("|")[0]


def _bare(concept: str) -> str:
    return concept.split("_", 1)[1] if "_" in concept else concept


def classify_statement(concepts: set[str]) -> str | None:
    bare = {_bare(c) for c in concepts}
    if {"Assets", "Liabilities"} <= bare or ({"Assets", "Equity"} <= bare):
        return "balance"
    if "CashFlowsFromUsedInOperatingActivities" in bare:
        return "cashflow"
    if "Revenue" in bare and ("ProfitLoss" in bare or "GrossProfit" in bare):
        return "income"
    return None


def decode_page(raw: bytes) -> str:
    """KAP sayfası → gömülü HTML metni (next_f parçaları birleştirilip JSON çözülür)."""
    text = raw.decode("utf-8", errors="replace")
    parts = re.findall(r'self\.__next_f\.push\(\[1,("(?:[^"\\]|\\.)*")\]\)', text)
    return "".join(json.loads(p) for p in parts) if parts else text


def parse_report(html: str) -> dict[str, Any]:
    """Gömülü HTML → {scale, currency, consolidated, statements: {balance|income|cashflow: {columns, rows}}}.

    ``rows``: {kavram(ön eksiz): [değerler (rapor birimi cinsinden, ölçeksiz)]}; aynı kavram birden çok
    kez geçerse (boyutlu bağlamlar) İLK satır alınır (toplam satırı).
    """
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    plain = re.sub(r"\s+", " ", soup.get_text(" "))

    m = re.search(r"Sunum Para Birimi\s+([\d\.]+)\s+([A-Za-z]{2,3})", plain)
    scale = float(m.group(1).replace(".", "")) if m else 1.0
    cur = (m.group(2).upper() if m else "TL")
    currency = "TRY" if cur == "TL" else cur
    consolidated = bool(re.search(r"Finansal Tablo Niteliği\s+Konsolide(?!\s+Olmayan)", plain))

    roles: dict[str, list[Any]] = {}
    for tr in soup.select("tr.data-input-row"):
        mm = re.search(r"([a-z_]+_role_\d+)-row", " ".join(tr.get("class", [])))
        roles.setdefault(mm.group(1) if mm else "?", []).append(tr)

    statements: dict[str, dict[str, Any]] = {}
    for role, trs in roles.items():
        concepts = {c for c in (_concept(t) for t in trs) if c}
        kind = classify_statement(concepts)
        if not kind or (kind in statements and len(trs) <= statements[kind]["n_rows"]):
            continue
        rows: dict[str, list[float | None]] = {}
        for tr in trs:
            c = _concept(tr)
            if not c:
                continue
            vals = [parse_tr_number(td.get_text(" ", strip=True)) for td in tr.select("td.taxonomy-context-value")]
            vals = [v for v in vals if v is not None]
            if not vals:
                continue
            rows.setdefault(_bare(c), vals)
        table = trs[0].find_parent("table")
        head = re.sub(r"\s+", " ", table.get_text(" ")) if table else ""
        cols = []
        for mt in _PERIOD_RE.finditer(head):
            cols.append({
                "kind": "current" if mt.group(1) == "Cari" else "previous",
                "three_month": bool(mt.group(2)),
                "start": _iso(mt.group(3)) if mt.group(4) else None,
                "end": _iso(mt.group(4) or mt.group(3)),
            })
        statements[kind] = {"columns": cols, "rows": rows, "n_rows": len(trs)}
    return {"scale": scale, "currency": currency, "consolidated": consolidated, "statements": statements}


def _pick(rows: dict[str, list[float | None]], names: list[str], col: int) -> float | None:
    for n in names:
        v = rows.get(n)
        if v and len(v) > col and v[col] is not None:
            return v[col]
    return None


def _first_col(columns: list[dict[str, Any]], *, current: bool, three_month: bool) -> int | None:
    for i, c in enumerate(columns):
        if (c["kind"] == "current") == current and c["three_month"] == three_month:
            return i
    return None


def report_snapshot(parsed: dict[str, Any]) -> dict[str, Any] | None:
    """Tek raporun cari dönem değerleri: kümülatif (ytd), 3 aylık (varsa) ve bilanço. Tutarlar TL/USD (ölçekli)."""
    st = parsed["statements"]
    if "income" not in st or "balance" not in st:
        return None
    k = parsed["scale"]
    inc, bal, cf = st["income"], st["balance"], st.get("cashflow")

    def take(stmt: dict[str, Any], mapping: dict[str, tuple[list[str], str]], col: int | None) -> dict[str, float | None]:
        out: dict[str, float | None] = {}
        if col is None:
            return out
        for key, (names, sign) in mapping.items():
            v = _pick(stmt["rows"], names, col)
            out[key] = None if v is None else (abs(v) if sign == "abs" else v) * k
        return out

    ycol = _first_col(inc["columns"], current=True, three_month=False)
    qcol = _first_col(inc["columns"], current=True, three_month=True)
    bcol = _first_col(bal["columns"], current=True, three_month=False)
    if ycol is None or bcol is None:
        return None
    end = inc["columns"][ycol]["end"]
    start = inc["columns"][ycol]["start"]
    months = None
    if start:
        sy, sm = int(start[:4]), int(start[5:7])
        ey, em = int(end[:4]), int(end[5:7])
        months = (ey - sy) * 12 + (em - sm) + 1

    ytd = take(inc, INCOME_MAP, ycol)
    quarter = take(inc, INCOME_MAP, qcol) if qcol is not None else None
    cfcol = _first_col(cf["columns"], current=True, three_month=False) if cf else None
    cfy = take(cf, CASHFLOW_MAP, cfcol) if cf and cfcol is not None else {}
    balance = take(bal, BALANCE_MAP, bcol)

    parts = []
    for names in DEBT_PARTS:
        v = _pick(bal["rows"], names, bcol)
        parts.append(v)
    balance["total_debt"] = None if all(p is None for p in parts) else sum(p or 0.0 for p in parts) * k

    da = cfy.pop("_da", None)
    if ytd.get("ebit") is not None:
        cfy["ebitda"] = ytd["ebit"] + da if da is not None else None
    return {
        "end": end,
        "months": months,
        "currency": parsed["currency"],
        "consolidated": parsed["consolidated"],
        "ytd": {**ytd, **cfy},
        "quarter": quarter,
        "balance": balance,
    }


def build_periods(snapshots: list[dict[str, Any]]) -> tuple[list[Period], list[Period]]:
    """Rapor görüntülerinden (çeyreklik, yıllık) Period listeleri.

    Çeyreklik akım: raporun kendi 3 aylık sütunu varsa o (aynı fiyat seviyesi, TMS 29 tutarlı);
    yoksa Ç1 → kümülatif; Ç4 → yıllık − Ç3 kümülatifi (``derived`` bayrağı: farklı fiyat seviyesi karışabilir).
    Nakit akışı kalemleri yalnızca kümülatif → ardışık kümülatiflerin farkı (``derived``).
    """
    snaps = sorted((s for s in snapshots if s), key=lambda s: s["end"])
    by_end = {s["end"]: s for s in snaps}
    flow_keys = ("revenue", "cogs", "gross_profit", "ebit", "net_income")
    cf_keys = ("cfo", "capex", "dividends_paid", "ebitda", "interest_expense")

    def prev_ytd(s: dict[str, Any]) -> dict[str, Any] | None:
        y = int(s["end"][:4])
        want = {"06": "03", "09": "06", "12": "09"}.get(s["end"][5:7])
        if not want:
            return None
        return next((p for p in snaps if p["end"].startswith(f"{y}-{want}")), None)

    quarterly: list[Period] = []
    annual: list[Period] = []
    for s in snaps:
        derived: list[str] = []
        q: dict[str, Any] = {"date": s["end"], "currency": s["currency"], **s["balance"]}
        pv = prev_ytd(s)
        for key in flow_keys:
            if s["quarter"] and s["quarter"].get(key) is not None:
                q[key] = s["quarter"][key]
            elif s["months"] == 3:
                q[key] = s["ytd"].get(key)
            elif pv and pv["ytd"].get(key) is not None and s["ytd"].get(key) is not None:
                q[key] = s["ytd"][key] - pv["ytd"][key]
                derived.append(key)
            else:
                q[key] = None
        for key in cf_keys:
            if s["months"] == 3:
                q[key] = s["ytd"].get(key)
            elif pv and pv["ytd"].get(key) is not None and s["ytd"].get(key) is not None:
                q[key] = s["ytd"][key] - pv["ytd"][key]
                derived.append(key)
            else:
                q[key] = None
        if derived:
            q["derived"] = sorted(set(derived))
        quarterly.append(q)
        if s["months"] == 12:
            annual.append({"date": s["end"], "currency": s["currency"], **s["balance"],
                           **{k: s["ytd"].get(k) for k in flow_keys + cf_keys}})
    _ = by_end
    return quarterly, annual


class KapFinancials:
    """Bildirim listesi + rapor indirme (önbellekli)."""

    def __init__(self) -> None:
        self.headers = {**default_headers(), "Content-Type": "application/json", "Referer": f"{BASE_URL}/tr/bildirim-sorgu"}

    def list_reports(self, tickers: set[str], months: int = 24) -> list[dict[str, Any]]:
        """Son ``months`` aydaki 'Finansal Rapor' bildirimleri (konsolide öncelikli), 60 günlük pencerelerle."""
        end = date.today()
        found: dict[str, dict[str, Any]] = {}
        start = end - timedelta(days=int(months * 30.5))

        def fetch(w_start: date, w_end: date) -> None:
            """KAP tek sorguda en fazla 2000 satır döndürür (rapor sezonunda aşılır) → dolunca pencereyi böl."""
            payload = {
                "fromDate": w_start.isoformat(), "toDate": w_end.isoformat(), "memberType": "IGS",
                "mkkMemberOidList": [], "inactiveMkkMemberOidList": [], "disclosureClass": "FR", "subjectList": [],
                "isLate": "", "mainSector": "", "sector": "", "subSector": "", "marketOid": "", "index": "",
                "bdkReview": "", "bdkMemberOidList": [], "year": "", "term": "", "ruleType": "", "period": "",
                "fromSrc": False, "srcCategory": "", "disclosureIndexList": [],
            }
            try:
                resp = retry_post(QUERY_URL, json=payload, headers=self.headers, timeout=max(settings.http_timeout, 40))
                resp.raise_for_status()
                rows = resp.json()
            except Exception as exc:
                log.warning("KAP FR listesi alınamadı (%s – %s): %s", w_start, w_end, exc)
                return
            rows = rows if isinstance(rows, list) else rows.get("data", [])
            if len(rows) >= MAX_ROWS and w_end > w_start:
                mid = w_start + (w_end - w_start) // 2
                fetch(w_start, mid)
                fetch(mid + timedelta(days=1), w_end)
                return
            if len(rows) >= MAX_ROWS:
                log.warning("KAP: %s günü %d satır — kesilmiş olabilir", w_start, len(rows))
            for r in rows:
                subj = str(r.get("subject") or "")
                if not subj.startswith("Finansal Rapor"):
                    continue
                codes = {c.strip() for c in str(r.get("stockCodes") or "").split(",")}
                hit = codes & tickers
                if not hit:
                    continue
                r["_ticker"] = sorted(hit)[0]
                r["_consolidated"] = "Konsolide Olmayan" not in subj
                found[str(r["disclosureIndex"])] = r

        w_start = start
        while w_start < end:
            w_end = min(w_start + timedelta(days=60), end)
            fetch(w_start, w_end)
            w_start = w_end + timedelta(days=1)
        # aynı (ticker, yıl, dönem) için konsolide olanı tercih et, sonra en yeni bildirim (düzeltme)
        best: dict[tuple[str, Any, Any], dict[str, Any]] = {}
        for r in found.values():
            key = (r["_ticker"], r.get("year"), r.get("period"))
            cur = best.get(key)
            if cur is None or (r["_consolidated"], int(r["disclosureIndex"])) > (cur["_consolidated"], int(cur["disclosureIndex"])):
                best[key] = r
        return sorted(best.values(), key=lambda r: (r["_ticker"], r.get("year") or 0, r.get("period") or 0))

    def snapshot(self, disclosure_index: str) -> dict[str, Any] | None:
        """Bildirim → ``report_snapshot``; önbellekten ya da KAP'tan."""
        cache = CACHE_DIR / f"{disclosure_index}.json"
        if cache.exists():
            return json.loads(cache.read_text(encoding="utf-8"))
        try:
            resp = retry_get(f"{BASE_URL}/tr/Bildirim/{disclosure_index}", headers=default_headers(), timeout=90)
            resp.raise_for_status()
            snap = report_snapshot(parse_report(decode_page(resp.content)))
        except Exception as exc:
            log.warning("KAP rapor işlenemedi %s: %s", disclosure_index, exc)
            return None
        if snap:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            cache.write_text(json.dumps(snap, ensure_ascii=False), encoding="utf-8")
        return snap
