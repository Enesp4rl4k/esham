"""TEFAS fonları için web JSON'u üretir (en büyük N fon; varsayılan 200).

Çıktılar (web/public/data/):
  universe-funds.json   — tarayıcı/sıralama için özet (kategori sıraları dahil)
  funds/<KOD>.json      — fon detayı: getiriler, risk, kategori kıyası, fiyat serisi

Hata toleransı: tek fon başarısız olursa (ya da TEFAS engellerse) o fonun önceki dosyası korunur; hiç fon
üretilemezse ve önceki evren yoksa 0 döner (CLI çıkış kodu 1). Portföy dağılımı v1'de yoktur (bkz. sources/tefas.py).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..config import get_logger
from ..sources import tefas as T

log = get_logger(__name__)

DATA_DIR = Path(__file__).resolve().parents[3] / "web" / "public" / "data"
SOURCE = "TEFAS (Takasbank)"
MAX_FUNDS = 2000  # dosya bütçesi koruması: bu sayının üstü web tarafında client-side veri stratejisi ister


def _write(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def select_top(rows: list[dict[str, Any]], sizes: dict[str, dict[str, float | None]], limit: int) -> list[dict[str, Any]]:
    """Portföy büyüklüğüne göre en büyük ``limit`` fon; büyüklüğü bilinmeyenler sona düşer."""
    limit = max(1, min(limit, MAX_FUNDS))
    ranked = sorted(rows, key=lambda r: -(sizes.get(r["code"], {}).get("aum") or 0))
    return [r for r in ranked if (sizes.get(r["code"], {}).get("aum") or 0) > 0][:limit]


def build_fund(
    base: dict[str, Any],
    prices: list[tuple[str, float]],
    info: dict[str, Any] | None,
    size: dict[str, float | None],
    fee: float | None,
    bench: dict[str, float],
    rank: tuple[int, int] | None,
    median_1y: float | None,
) -> dict[str, Any]:
    returns = dict(base["returns"])
    # TEFAS'ın bildirdiği getiri esastır; eksikse (yeni fon vb.) fiyat serisinden hesapla
    for key, days in (("1m", 30), ("3m", 91), ("6m", 182), ("1y", 365), ("3y", 1095), ("5y", 1826)):
        if returns.get(key) is None:
            returns[key] = T.period_return(prices, days)
    metrics = T.risk_metrics(prices, bench.get("deposit"))
    last_date, last_price = (prices[-1] if prices else (None, None))
    info = info or {}
    r1y = returns.get("1y")
    return {
        "code": base["code"],
        "name": base["name"],
        "category": base["category"],
        "risk": base["risk"],
        "updated_at": T.now_iso(),
        "as_of": last_date,
        "price": info.get("price") or last_price,
        "daily": info.get("daily"),
        "aum": info.get("aum") or size.get("aum"),
        "units": info.get("units") or size.get("units"),
        "investors": info.get("investors"),
        "market_share": info.get("market_share"),
        "fee": fee,
        "returns": returns,
        "real_1y": T.real_return(r1y, bench.get("cpi")),
        "usd_1y": T.real_return(r1y, bench.get("usd")),
        "metrics": metrics,
        "category_rank": {"rank": rank[0], "of": rank[1], "by": "1y"} if rank else None,
        "category_median_1y": median_1y,
        "benchmarks": bench,
        "allocation": None,  # v1: JSON ucu yok (sayfa SSR + JS-challenge); arayüz bölümü gizler
        "prices": T.thin_series(prices),
        "source": SOURCE,
    }


def _category_medians(rows: list[dict[str, Any]], key: str = "1y") -> dict[str, float]:
    import statistics

    by: dict[str, list[float]] = {}
    for r in rows:
        v = r["returns"].get(key)
        if v is not None:
            by.setdefault(r["category"], []).append(v)
    return {c: round(statistics.median(v), 2) for c, v in by.items() if len(v) >= 3}


def summary_row(f: dict[str, Any]) -> dict[str, Any]:
    r = f["returns"]
    return {
        "code": f["code"], "name": f["name"], "category": f["category"], "risk": f["risk"], "price": f["price"],
        "daily": f["daily"], "aum": f["aum"], "investors": f["investors"], "fee": f["fee"], "as_of": f["as_of"],
        "r1m": r.get("1m"), "r3m": r.get("3m"), "r6m": r.get("6m"), "ytd": r.get("ytd"), "r1y": r.get("1y"),
        "r3y": r.get("3y"), "r5y": r.get("5y"), "real_1y": f["real_1y"], "vol": f["metrics"]["volatility"],
        "mdd": f["metrics"]["max_drawdown"], "sharpe": f["metrics"]["sharpe"],
        "rank": f["category_rank"]["rank"] if f["category_rank"] else None,
        "rank_of": f["category_rank"]["of"] if f["category_rank"] else None,
    }


def _collect(
    client: T.TefasClient,
    chosen: list[dict[str, Any]],
    sizes: dict[str, dict[str, float | None]],
    fees: dict[str, float | None],
    bench: dict[str, float],
    ranks: dict[str, tuple[int, int]],
    medians: dict[str, float],
) -> list[dict[str, Any]]:
    """Seçilen fonların ayrıntısını sırayla çeker ve yazar; engelde durur, tek fon hatasında atlar."""
    funds: list[dict[str, Any]] = []
    for i, base in enumerate(chosen, 1):
        code = base["code"]
        try:
            prices = T.fetch_prices(client, code)
            info = T.fetch_fund_info(client, code)
            fund = build_fund(base, prices, info, sizes.get(code, {}), fees.get(code), bench, ranks.get(code), medians.get(base["category"]))
        except T.TefasBlocked as exc:
            log.error("TEFAS engeli, kalan fonlar atlandı (%d/%d): %s", i, len(chosen), exc)
            break
        except T.TefasError as exc:
            log.warning("Fon atlandı %s: %s", code, exc)
            continue
        if not fund["prices"]:
            log.warning("Fiyat serisi yok, atlandı: %s", code)
            continue
        funds.append(fund)
        _write(DATA_DIR / "funds" / f"{code}.json", fund)
        if i % 25 == 0:
            log.info("Fon ilerleme: %d/%d", i, len(chosen))
    return funds


def run_funds(limit: int = 200, codes: list[str] | None = None, min_interval: float = 0.4) -> int:
    client = T.TefasClient(min_interval=min_interval)
    table = T.fetch_return_table(client)
    if not table:
        log.error("TEFAS getiri tablosu boş")
        return 0
    sizes = T.fetch_sizes(client)
    try:
        fees = T.fetch_fees(client)
    except T.TefasError as exc:  # zorunlu değil
        log.warning("Yönetim ücreti alınamadı: %s", exc)
        fees = {}
    ranks = T.rank_in_categories(table)
    medians = _category_medians(table)

    if codes:
        want = {c.upper() for c in codes}
        chosen = [r for r in table if r["code"] in want]
    else:
        chosen = select_top(table, sizes, limit)
    if not chosen:
        return 0

    bench: dict[str, float] = {}
    try:
        bench = T.fetch_benchmarks(client, chosen[0]["code"])
    except T.TefasError as exc:
        log.warning("Kıyas getirileri alınamadı: %s", exc)

    funds = _collect(client, chosen, sizes, fees, bench, ranks, medians)
    if not funds:
        return 0
    _merge_universe(funds, medians, partial=bool(codes), chosen={c['code'] for c in chosen})
    log.info("Fon verisi yazıldı: %d/%d", len(funds), len(chosen))
    return len(funds)


def _merge_universe(funds: list[dict[str, Any]], medians: dict[str, float], partial: bool, chosen: set[str]) -> None:
    path = DATA_DIR / "universe-funds.json"
    rows: dict[str, dict[str, Any]] = {}
    if partial and path.exists():  # kısmi çalıştırma mevcut evreni bozmaz
        rows = {r["code"]: r for r in json.loads(path.read_text(encoding="utf-8")).get("funds", [])}
    elif path.exists():
        # engel yüzünden eksik kalan fonların önceki satırı korunsun (dosyası da yerinde duruyor)
        prev = json.loads(path.read_text(encoding="utf-8")).get("funds", [])
        rows = {r["code"]: r for r in prev if r["code"] in chosen and (DATA_DIR / "funds" / f"{r['code']}.json").exists()}
    for f in funds:
        rows[f["code"]] = summary_row(f)
    if not partial:  # evrenden çıkan fonların eski dosyalarını sil (dosya bütçesi + bayat veri)
        for f in (DATA_DIR / "funds").glob("*.json"):
            if f.stem not in rows:
                f.unlink()
    ordered = sorted(rows.values(), key=lambda r: -(r.get("aum") or 0))
    _write(path, {
        "updated_at": T.now_iso(),
        "source": SOURCE,
        "count": len(ordered),
        "category_median_1y": medians,
        "funds": ordered,
    })
