"""KAP'tan kâr payı takvimi ve pay geri alımları → ``web/public/data/kap-dividends.json`` / ``kap-buybacks.json``.

Kurallar (PR #25 ile aynı):
  - Her satır kaynak bildirim numarası + bağlantısı + veri tarihi (bildirimin yayın zamanı) + çekiliş zamanı taşır.
  - Liste alınamazsa dosyaya DOKUNULMAZ (son iyi veri gerçek tarihiyle kalır; tazelik ölçümü "eski" der).
  - Bütçe/429 nedeniyle tamamlanamayan bildirimler sayılır ve sayfada "N bildirim henüz işlenmedi" olarak görünür;
    sonraki koşu önbellekten devam eder (resumable). Önceki dosyadaki satırlar, önbellek yoksa geri dönüş olarak korunur.
  - Kapsam açıkça yazılır: "110 hisseden N'i tarandı; son tam tarama tarihi".
"""
from __future__ import annotations

import json
import os
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from ..config import get_logger
from ..kap_http import KapUnavailable, gate
from ..sources import kap_events as KE
from ..universe import load_universe

log = get_logger(__name__)
DATA_DIR = Path(__file__).resolve().parents[3] / "web" / "public" / "data"
DIVIDEND_FILE = "kap-dividends.json"
BUYBACK_FILE = "kap-buybacks.json"
SOURCE_URL = "https://www.kap.org.tr/tr/bildirim-sorgu"
DEFAULT_DIVIDEND_DAYS = 150
DEFAULT_BUYBACK_DAYS = 30
TR_TZ = timezone(timedelta(hours=3))  # Europe/Istanbul (DST yok)
EVENTS_MIN_INTERVAL = 2.5  # sn; bildirim sayfaları arasında en az bu kadar bekle
DEFAULT_MAX_DETAILS = 40  # koşu başına en çok bu kadar bildirim sayfası indirilir (önbellekten okuma sayılmaz)


def _read(path: Path) -> dict[str, Any] | None:
    try:
        d = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return d if isinstance(d, dict) else None


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def amount_note(inst: dict[str, Any]) -> str:
    """Brüt/net tutarın kaynağı hakkında dürüst not. Net HİÇBİR ZAMAN varsayılan stopajla türetilmez: ikisi de bildirimdeki
    rakamdır (ayrıştırıcı, bildirimde ikisi de yoksa satırı reddeder)."""
    wh = inst["withholding_pct"]
    if inst["gross"] == inst["net"]:
        return (f"Bildirimde brüt ve net tutar aynı ({inst['gross']:g} TL) olarak verilmiş (stopaj %{wh:g}); "
                "net tutar bu bildirimdeki rakamdır, bot hesaplamadı.")
    return (f"Brüt ve net tutar bildirimdeki rakamlardır (bildirimdeki tek stopaj satırı %{wh:g}); "
            "başka hissedar türleri için farklı bir oran bildirimde ayrıca yer alabilir, burada gösterilmez.")


def generation_date(fetched_at: str) -> str:
    """Verinin üretildiği gün (Europe/Istanbul, YYYY-MM-DD). Okunamazsa ValueError."""
    d = datetime.fromisoformat(fetched_at.replace("Z", "+00:00"))
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return d.astimezone(TR_TZ).date().isoformat()


def mark_past(items: list[dict[str, Any]], fetched_at: str) -> None:
    """Her taksite ``exDatePast``: hak kullanım tarihi, verinin üretim gününden ÖNCE mi (ISO tarihler sözlük sırasıyla kıyaslanır).
    Önceki dosyadan taşınan satırlar da yeniden işaretlenir; bayrak bayat kalmaz."""
    today = generation_date(fetched_at)
    for it in items:
        for x in it["installments"]:
            x["exDatePast"] = x["exDate"] < today


def dividend_item(d: KE.Disclosure, name: str, data: dict[str, Any], fetched_at: str) -> dict[str, Any]:
    return {
        "ticker": d.ticker, "name": name, "disclosureIndex": d.index, "sourceUrl": KE.disclosure_url(d.index),
        "publishedAt": d.published, "asOf": d.published[:10], "fetchedAt": fetched_at,
        "status": data["status"], "decisionDate": data["decision_date"], "agmDate": data["agm_date"],
        "installments": [
            {"label": i["label"], "payGroup": i["pay_group"], "grossPerShare": i["gross"], "netPerShare": i["net"],
             "withholdingPct": i["withholding_pct"], "exDate": i["ex_date"], "exDateFinal": i["ex_date_final"],
             "paymentDate": i["payment_date"], "recordDate": i["record_date"], "amountNote": amount_note(i)}
            for i in data["installments"]
        ],
    }


def buyback_item(d: KE.Disclosure, name: str, data: dict[str, Any], fetched_at: str) -> dict[str, Any]:
    return {
        "ticker": d.ticker, "name": name, "disclosureIndex": d.index, "sourceUrl": KE.disclosure_url(d.index),
        "publishedAt": d.published, "asOf": d.published[:10], "fetchedAt": fetched_at,
        "nature": data["nature"], "boardDecisionDate": data["board_decision_date"], "programPeriod": data["program_period"],
        "maxNominal": data["max_nominal"], "fundTotalTry": data["fund_total_try"],
        "trades": [{"date": t["date"], "nominal": t["nominal"], "price": t["price"], "capitalPct": t["capital_pct"]} for t in data["trades"]],
        "totalNominal": data["total_nominal"], "amountTry": data["amount_try"], "avgPrice": data["avg_price"],
        "firstTradeDate": data["first_trade_date"], "lastTradeDate": data["last_trade_date"],
        "programCumulativeNominal": data["program_cumulative_nominal"],
    }


def _ref(d: KE.Disclosure) -> dict[str, str]:
    return {"ticker": d.ticker, "disclosureIndex": d.index, "sourceUrl": KE.disclosure_url(d.index)}


def _resolve(kind: str, picks: list[KE.Disclosure], names: dict[str, str], prev_items: dict[str, dict[str, Any]],
             build, max_details: int, fetched_at: str, cache_dir: Path | None = None
             ) -> tuple[list[dict[str, Any]], dict[str, int], list[dict[str, str]], list[dict[str, str]]]:
    """(satırlar, atlama nedeni sayaçları, atlanan bildirimler, henüz taranmamış (bekleyen) bildirimler)."""
    cdir = cache_dir or KE.EVENT_CACHE_DIR
    items: list[dict[str, Any]] = []
    skipped: dict[str, int] = {}
    skipped_list: list[dict[str, str]] = []
    pending: list[dict[str, str]] = []
    fetched = 0
    for d in picks:
        doc = KE.cached(kind, d.index, cdir)
        if doc is None:
            if fetched >= max_details or gate.stopped:
                prev = prev_items.get(d.index)
                if prev:
                    items.append(prev)
                else:
                    pending.append(_ref(d))
                continue
            try:
                doc = KE.fetch_and_parse(kind, d, fetched_at, cdir)
                fetched += 1
            except KapUnavailable as exc:
                log.warning("KAP olay bildirimi alınamadı %s: %s", d.index, exc)
                prev = prev_items.get(d.index)
                if prev:
                    items.append(prev)
                else:
                    pending.append(_ref(d))
                continue
        if doc.get("ok"):
            items.append(build(d, names.get(d.ticker, d.ticker), doc["data"], doc.get("fetched_at") or fetched_at))
        else:
            reason = str(doc.get("reason") or "bilinmeyen")
            skipped[reason] = skipped.get(reason, 0) + 1
            skipped_list.append({"ticker": d.ticker, "disclosureIndex": d.index, "sourceUrl": KE.disclosure_url(d.index), "reason": reason})
    return items, skipped, skipped_list, pending


def _scan_block(prev: dict[str, Any] | None, universe: int, listed: list[KE.Disclosure], w: tuple[date, date],
                parsed: int, skipped: dict[str, int], skipped_list: list[dict[str, str]], pending_list: list[dict[str, str]], now_iso: str) -> dict[str, Any]:
    pending = len(pending_list)
    complete = pending == 0
    last_complete = now_iso if complete else ((prev or {}).get("scan", {}) or {}).get("lastCompleteScanAt")
    return {
        "windowFrom": w[0].isoformat(), "windowTo": w[1].isoformat(), "universeSize": universe,
        "tickersWithDisclosure": len({d.ticker for d in listed}), "disclosuresListed": len(listed),
        "parsed": parsed, "skipped": skipped, "skippedItems": skipped_list, "pending": pending, "pendingItems": pending_list,
        "complete": complete, "lastCompleteScanAt": last_complete,
    }


def build_dividends(listed: list[KE.Disclosure], names: dict[str, str], prev: dict[str, Any] | None, max_details: int,
                    fetched_at: str, universe: int, w: tuple[date, date], cache_dir: Path | None = None) -> dict[str, Any]:
    newest: dict[str, KE.Disclosure] = {}
    for d in listed:  # listed: yeniden eskiye
        newest.setdefault(d.ticker, d)
    picks = list(newest.values())
    prev_items = {i["disclosureIndex"]: i for i in (prev or {}).get("items", []) if isinstance(i, dict) and i.get("disclosureIndex")}
    items, skipped, skipped_list, pending = _resolve("div", picks, names, prev_items, dividend_item, max_details, fetched_at, cache_dir)
    shown_items = [i for i in items if i["status"] != "dagitim_yok"]
    mark_past(shown_items, fetched_at)
    none = [i for i in items if i["status"] == "dagitim_yok"]
    shown = [i for i in items if i["status"] != "dagitim_yok"]
    return {
        "source": "KAP — Kar Payı Dağıtım İşlemlerine İlişkin Bildirim", "sourceUrl": SOURCE_URL, "fetchedAt": fetched_at, "updatedAt": fetched_at,
        "asOf": max((i["asOf"] for i in items), default=None),
        "items": sorted(shown, key=lambda i: min(x["exDate"] for x in i["installments"])),
        "noDividend": sorted(none, key=lambda i: i["ticker"]),
        "scan": _scan_block(prev, universe, listed, w, len(items), skipped, skipped_list, pending, fetched_at),
    }


def build_buybacks(listed: list[KE.Disclosure], names: dict[str, str], prev: dict[str, Any] | None, max_details: int,
                   fetched_at: str, universe: int, w: tuple[date, date], cache_dir: Path | None = None) -> dict[str, Any]:
    prev_items = {i["disclosureIndex"]: i for i in (prev or {}).get("items", []) if isinstance(i, dict) and i.get("disclosureIndex")}
    items, skipped, skipped_list, pending = _resolve("bb", listed, names, prev_items, buyback_item, max_details, fetched_at, cache_dir)
    items.sort(key=lambda i: (i["lastTradeDate"], i["publishedAt"]), reverse=True)
    return {
        "source": "KAP — Payların Geri Alınmasına İlişkin Bildirim", "sourceUrl": SOURCE_URL, "fetchedAt": fetched_at, "updatedAt": fetched_at,
        "asOf": max((i["asOf"] for i in items), default=None), "items": items,
        "scan": _scan_block(prev, universe, listed, w, len(items), skipped, skipped_list, pending, fetched_at),
    }


def _write(path: Path, doc: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def run_kap_events(dividend_days: int | None = None, buyback_days: int | None = None, max_details: int | None = None,
                   data_dir: Path | None = None, cache_dir: Path | None = None) -> int:
    """Çıkış: yazılan dosya sayısı (0 = KAP listesi alınamadı, hiçbir dosya değişmedi)."""
    ddir = data_dir or DATA_DIR
    dividend_days = dividend_days or int(os.getenv("ESHAM_KAP_DIVIDEND_DAYS", "") or DEFAULT_DIVIDEND_DAYS)
    buyback_days = buyback_days or int(os.getenv("ESHAM_KAP_BUYBACK_DAYS", "") or DEFAULT_BUYBACK_DAYS)
    max_details = max_details if max_details is not None else int(os.getenv("ESHAM_KAP_EVENTS_MAX_DETAILS", "") or DEFAULT_MAX_DETAILS)
    universe = load_universe()
    tickers = {str(u["ticker"]) for u in universe}
    names = {str(u["ticker"]): str(u["name"]) for u in universe}
    # Ölçüm (23 Kas): 1-1,5 sn aralıkla ~100 ardışık bildirim sayfası 429 verdi; 2-3 sn aralıkla verilmedi.
    gate.min_interval = max(gate.min_interval, EVENTS_MIN_INTERVAL)
    gate.begin_stage()
    written = 0
    for subject, oid, days, file, builder in (
        (KE.SUBJECT_DIVIDEND, KE.SUBJECT_DIVIDEND_OID, dividend_days, DIVIDEND_FILE, build_dividends),
        (KE.SUBJECT_BUYBACK, KE.SUBJECT_BUYBACK_OID, buyback_days, BUYBACK_FILE, build_buybacks),
    ):
        w = KE.window(days)
        before_failed = gate.failed
        try:
            listed = KE.list_disclosures(oid, subject, tickers, *w)
        except KapUnavailable as exc:
            log.warning("KAP %s listesi alınamadı, %s dosyası değiştirilmedi: %s | %s", subject, file, exc, gate.summary())
            continue
        if gate.failed > before_failed or gate.stopped:
            log.warning("KAP %s listesi eksik olabilir, %s dosyası değiştirilmedi. %s", subject, file, gate.summary())
            continue
        fetched_at = _now_iso()
        prev = _read(ddir / file)
        doc = builder(listed, names, prev, max_details, fetched_at, len(tickers), w, cache_dir)
        _write(ddir / file, doc)
        written += 1
        sc = doc["scan"]
        print(f"{file}: {len(tickers)} hisseden {sc['tickersWithDisclosure']}'inde bildirim var; {sc['disclosuresListed']} bildirim listelendi, "
              f"{sc['parsed']} işlendi, {sc['pending']} bekliyor, atlanan: {sc['skipped'] or 'yok'}")
    print(gate.summary())
    return written
