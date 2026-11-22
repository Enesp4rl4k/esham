"""KAP kurumsal olaylar: kâr payı dağıtım bildirimleri ve pay geri alım bildirimleri.

Tek kaynak: KAP bildirim sorgusu (``/tr/api/disclosure/members/byCriteria``, konu kimliğiyle süzülmüş liste)
ve her bildirimin kendi sayfası (``/tr/Bildirim/<index>``). Finansal raporlarla AYNI nazik HTTP katmanını
(``kap_http``: aralık, bütçe, 429 devre kesici) ve aynı önbellek dizinini paylaşır; ikinci bir tarayıcı yoktur.

Kural: biçimi tanınmayan bildirim TAHMİN EDİLMEZ; neden sayılarak atlanır (``Unparsable.reason``).
Hiçbir sayı kodda gömülü değildir; her satır bildirimin kendi numarasını, yayın tarihini ve bağlantısını taşır.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import requests

from ..config import default_headers, get_logger
from ..kap_http import KapUnavailable, kap_get
from .kap_financials import BASE_URL, decode_page, iter_fr_rows, parse_tr_number

log = get_logger(__name__)

#: bildirim-sorgu sayfasındaki ``subjectOid`` değerleri (ODA sınıfı). Liste yanıtındaki ``subject`` adı ayrıca doğrulanır.
SUBJECT_DIVIDEND_OID = "4028328d5988e2630159d5fb51c81fe6"   # "Kar Payı Dağıtım İşlemlerine İlişkin Bildirim"
SUBJECT_BUYBACK_OID = "4028328d6233239a01629b43e4694fae"    # "Payların Geri Alınmasına İlişkin Bildirim"
SUBJECT_DIVIDEND = "Kar Payı Dağıtım İşlemlerine İlişkin Bildirim"
SUBJECT_BUYBACK = "Payların Geri Alınmasına İlişkin Bildirim"

#: Ayrıştırıcı sürümü: sürüm değişince eski "ayrıştırılamadı" kayıtları yeniden denenir.
PARSER_VERSION = 2  # 2: geri alım sütunları başlık adıyla bulunur; banka şablonu ve program başlangıç bildirimi
EVENT_CACHE_DIR = Path(__file__).resolve().parents[2] / "cache" / "kap" / "events"
TOLERANCE_NET = 1e-6  # brüt*(1-stopaj) ile net arasındaki izinli fark (KAP 7 hane yuvarlar)


class Unparsable(Exception):
    """Bildirim tanınan biçimde değil; ``reason`` kısa ve sayılabilir bir neden."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def _iso(d: str) -> str | None:
    m = re.fullmatch(r"\s*(\d{2})\.(\d{2})\.(\d{4})\s*", d or "")
    if not m:
        return None
    try:
        return date(int(m.group(3)), int(m.group(2)), int(m.group(1))).isoformat()
    except ValueError:
        return None


def _rows_of(table: Any) -> list[list[str]]:
    out = []
    for tr in table.find_all("tr"):
        cells = [td.get_text(" ", strip=True) for td in tr.find_all("td", recursive=False)]
        if cells:
            out.append(cells)
    return out


def _soup(raw_or_html: bytes | str):
    from bs4 import BeautifulSoup

    html = decode_page(raw_or_html) if isinstance(raw_or_html, bytes) else raw_or_html
    return BeautifulSoup(html, "html.parser")


def _label_values(soup: Any) -> dict[str, str]:
    """"Etiket | değer" ikili satırları (ör. 'Karar Tarihi | 18.11.2026')."""
    out: dict[str, str] = {}
    for tr in soup.find_all("tr"):
        if tr.find("tr"):
            continue
        tds = tr.find_all("td", recursive=False)
        if len(tds) == 2:
            k = re.sub(r"\s+", " ", tds[0].get_text(" ", strip=True)).strip()
            v = re.sub(r"\s+", " ", tds[1].get_text(" ", strip=True)).strip()
            if k and k not in out:
                out[k] = v
    return out


def _find_table(soup: Any, table_id: str, header_has: str) -> Any | None:
    for t in soup.select(f"table[id={table_id}]"):
        rows = _rows_of(t)
        if rows and header_has in " ".join(rows[0]):
            return t
    return None


# --------------------------------------------------------------------------------------------
# Kâr payı dağıtımı
# --------------------------------------------------------------------------------------------

def _group_matches(group: str, ticker: str) -> bool:
    toks = [t.strip().upper() for t in group.split(",")]
    return len(toks) >= 2 and toks[-2] == ticker.upper()


def parse_dividend(raw: bytes | str, ticker: str) -> dict[str, Any]:
    """Kâr payı dağıtım bildirimi → {decision_date, agm_date, installments:[...], status, summary}.

    ``status``: "teklif" (yalnız teklif edilen hak kullanım tarihi), "kesinlesti" (kesinleşen tarih dolu),
    "dagitim_yok" (nakit brüt tutar 0). Tanınmayan biçim → ``Unparsable``.
    """
    soup = _soup(raw)
    labels = _label_values(soup)
    summary = labels.get("Özet Bilgi", "")
    t2 = _find_table(soup, "SHARE_DIVIDEND_FLEX_TABLE_2", "Pay Grup Bilgileri")
    if t2 is None:
        raise Unparsable("nakit kâr payı tablosu yok")
    rows2 = _rows_of(t2)
    head = rows2[0]
    if len(head) < 7 or "Brüt(TL)" not in head[2] or "Stopaj" not in head[4] or "Net(TL)" not in head[5]:
        raise Unparsable("nakit kâr payı tablo başlığı tanınmadı")
    mine = [r for r in rows2[1:] if len(r) >= 7 and _group_matches(r[0], ticker)]
    if not mine:
        raise Unparsable("pay grubu hisse koduyla eşleşmedi")
    t4 = _find_table(soup, "SHARE_DIVIDEND_FLEX_TABLE_4", "Pay Biçiminde")
    if t4 is not None:
        for r in _rows_of(t4)[1:]:
            if len(r) >= 2 and _group_matches(r[0], ticker):
                v = parse_tr_number(r[1])
                if v is None:
                    raise Unparsable("pay biçimindeki kâr payı okunamadı")
                if v > 0:
                    raise Unparsable("pay biçiminde (bedelsiz) dağıtım: desteklenmiyor")

    decision = _iso(labels.get("Karar Tarihi", ""))
    agm = _iso(labels.get("Konunun Gündemde Yer Aldığı Genel Kurul Tarihi", ""))
    if decision is None:
        raise Unparsable("karar tarihi okunamadı")
    currency = labels.get("Para Birimi") or None

    parsed = []
    for r in mine:
        gross, net, wh = parse_tr_number(r[2]), parse_tr_number(r[5]), parse_tr_number(r[4])
        if gross is None or net is None or wh is None:
            raise Unparsable("brüt/net/stopaj sayısı okunamadı")
        if gross < 0 or net < 0 or not (0 <= wh <= 100):
            raise Unparsable("brüt/net/stopaj makul aralıkta değil")
        if abs(gross * (1 - wh / 100) - net) > TOLERANCE_NET:
            raise Unparsable("net tutar brüt ve stopajla tutarsız")
        parsed.append({"label": r[1].strip(), "pay_group": r[0], "gross": gross, "net": net, "withholding_pct": wh,
                       "gross_pct": parse_tr_number(r[3]), "net_pct": parse_tr_number(r[6])})

    if all(p["gross"] == 0 for p in parsed):
        return {"status": "dagitim_yok", "decision_date": decision, "agm_date": agm, "currency": currency,
                "installments": [], "summary": summary}
    if currency not in {"TRY", "TL"}:
        raise Unparsable("para birimi TRY değil")

    t3 = _find_table(soup, "SHARE_DIVIDEND_FLEX_TABLE_3", "Hak Kullanım")
    if t3 is None:
        raise Unparsable("kâr payı ödeme tarihleri tablosu yok")
    rows3 = _rows_of(t3)
    h3 = " ".join(rows3[0])
    if not ("Teklif Edilen" in h3 and "Kesinleşen" in h3 and "Ödeme Tarihi" in h3 and "Kayıt Tarihi" in h3) or len(rows3[0]) < 5:
        raise Unparsable("tarih tablosu başlığı tanınmadı")
    dates = {r[0].strip(): r for r in rows3[1:] if len(r) >= 5}

    inst = []
    for p in parsed:
        if p["gross"] == 0:
            continue
        d = dates.get(p["label"])
        if d is None:
            raise Unparsable("ödeme etiketi tarih tablosuyla eşleşmedi")
        proposed, final, pay, record = (_iso(x) for x in d[1:5])
        for raw_val, iso in zip(d[1:5], (proposed, final, pay, record)):
            if raw_val.strip() and iso is None:
                raise Unparsable("tarih okunamadı")
        ex = final or proposed
        if ex is None or pay is None:
            raise Unparsable("hak kullanım veya ödeme tarihi boş")
        if pay < ex:
            raise Unparsable("ödeme tarihi hak kullanım tarihinden önce")
        inst.append({**p, "ex_date": ex, "ex_date_final": final is not None, "ex_date_proposed": proposed,
                     "payment_date": pay, "record_date": record})
    return {"status": "kesinlesti" if all(i["ex_date_final"] for i in inst) else "teklif",
            "decision_date": decision, "agm_date": agm, "currency": "TRY", "installments": inst, "summary": summary}


# --------------------------------------------------------------------------------------------
# Pay geri alımı
# --------------------------------------------------------------------------------------------

def _col(head: list[str], *needles: str) -> int | None:
    for i, h in enumerate(head):
        if all(n in h for n in needles):
            return i
    return None


def parse_buyback(raw: bytes | str, ticker: str) -> dict[str, Any]:
    """Pay geri alım bildirimi → program bilgisi + işlem satırları (tarih, adet, fiyat). Tanınmayan biçim → ``Unparsable``.

    Sütunlar başlık adıyla bulunur (bankaların şablonunda "Daha Önce Geri Alınan" sütunu yoktur → None).
    Program başlangıç bildirimi (işlem satırı yok) ``Unparsable`` ile sayılır.
    """
    soup = _soup(raw)
    labels = _label_values(soup)
    table = None
    planned = False
    for t in soup.find_all("table"):
        rows = _rows_of(t)
        if rows and rows[0][:2] == ["İşleme Konu Pay", "İşlem Tarihi"]:
            table = rows
            break
        if rows and rows[0][:2] == ["İşleme Konu Pay", "Başlangıç Tarihi"]:
            planned = True
    if table is None:
        started = "Başlat" in labels.get("Özet Bilgi", "")
        raise Unparsable("program başlangıç bildirimi (işlem satırı yok)" if (planned or started) else "geri alım işlem tablosu yok")
    head = table[0]
    i_nom, i_pct = _col(head, "Nominal"), _col(head, "Sermayeye Oranı")
    i_price, i_prior = _col(head, "İşlem Fiyatı"), _col(head, "Daha Önce")
    if i_nom is None or i_price is None or i_pct is None:
        raise Unparsable("geri alım tablo başlığı tanınmadı")
    trades = []
    for r in table[1:]:
        if len(r) < len(head) or not _group_matches(r[0], ticker):
            continue
        d, nominal, pct, price = _iso(r[1]), parse_tr_number(r[i_nom]), parse_tr_number(r[i_pct]), parse_tr_number(r[i_price])
        prior = parse_tr_number(r[i_prior]) if i_prior is not None else None
        if d is None or nominal is None or price is None or nominal <= 0 or price <= 0:
            raise Unparsable("işlem satırı okunamadı")
        trades.append({"date": d, "nominal": nominal, "capital_pct": pct, "price": price, "prior_nominal": prior})
    if not trades:
        raise Unparsable("işlem satırı hisse koduyla eşleşmedi")
    nature = labels.get("Geri Alım İşleminin Niteliği") or None
    board = _iso(labels.get("Yönetim Kurulu Karar Tarihi", ""))
    max_nominal = parse_tr_number(labels.get("Geri Alıma Konu Azami Pay Miktarı (Nominal TL)") or labels.get("Geri Alıma Konu Pay Miktarı (Nominal TL)") or "")
    fund = parse_tr_number(labels.get("Geri Alım İçin Ayrılan Fonun Toplam Tutarı (TL)") or labels.get("Ödenecek Azami Tutar (TL)") or "")
    total = sum(t["nominal"] for t in trades)
    amount = sum(t["nominal"] * t["price"] for t in trades)
    last = max(trades, key=lambda t: t["date"])
    cumulative = None
    if all(t["prior_nominal"] is not None for t in trades):
        # Program çerçevesinde bu bildirimin son satırına kadar toplam (KAP "daha önce" sütunu + son satır)
        last_row = max(trades, key=lambda t: (t["date"], t["prior_nominal"]))
        cumulative = last_row["prior_nominal"] + last_row["nominal"]
    return {
        "nature": nature, "board_decision_date": board, "program_period": labels.get("Varsa Geri Alım Programının Uygulanacağı Süre") or None,
        "max_nominal": max_nominal, "fund_total_try": fund, "trades": trades,
        "total_nominal": total, "amount_try": round(amount, 2), "avg_price": round(amount / total, 4),
        "first_trade_date": min(t["date"] for t in trades), "last_trade_date": last["date"],
        "program_cumulative_nominal": cumulative,
    }


# --------------------------------------------------------------------------------------------
# Liste + önbellek
# --------------------------------------------------------------------------------------------

@dataclass
class Disclosure:
    index: str
    ticker: str
    published: str  # ISO tarih-saat (KAP: gg.aa.yyyy ss:dd:ss, TR saati)
    summary: str
    subject: str


def _publish_iso(s: str) -> str | None:
    m = re.fullmatch(r"(\d{2})\.(\d{2})\.(\d{4})(?: (\d{2}:\d{2}:\d{2}))?", (s or "").strip())
    if not m:
        return None
    return f"{m.group(3)}-{m.group(2)}-{m.group(1)}T{m.group(4) or '00:00:00'}+03:00"


def list_disclosures(oid: str, subject: str, tickers: set[str], w_start: date, w_end: date) -> list[Disclosure]:
    """Konuya göre süzülmüş KAP listesi → evrendeki hisselerin bildirimleri (konu adı ayrıca doğrulanır)."""
    headers = {**default_headers(), "Content-Type": "application/json", "Referer": f"{BASE_URL}/tr/bildirim-sorgu"}
    rows = iter_fr_rows(headers, w_start, w_end, disclosure_class="ODA", subject_oids=(oid,))
    out: dict[str, Disclosure] = {}
    for r in rows:
        if str(r.get("subject") or "").strip() != subject:
            continue
        codes = {c.strip().upper() for c in str(r.get("stockCodes") or "").split(",")}
        hit = sorted(codes & tickers)
        pub = _publish_iso(str(r.get("publishDate") or ""))
        if not hit or not pub or not r.get("disclosureIndex"):
            continue
        out[str(r["disclosureIndex"])] = Disclosure(str(r["disclosureIndex"]), hit[0], pub, str(r.get("summary") or ""), subject)
    return sorted(out.values(), key=lambda d: (d.published, int(d.index)), reverse=True)


def _cache_file(kind: str, index: str, cache_dir: Path) -> Path:
    return cache_dir / f"{kind}-{index}.json"


def cached(kind: str, index: str, cache_dir: Path = EVENT_CACHE_DIR) -> dict[str, Any] | None:
    try:
        doc = json.loads(_cache_file(kind, index, cache_dir).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if isinstance(doc, dict) and doc.get("parser_version") == PARSER_VERSION:
        return doc
    return None


def fetch_and_parse(kind: str, d: Disclosure, fetched_at: str, cache_dir: Path = EVENT_CACHE_DIR) -> dict[str, Any]:
    """Bildirimi önbellekten ya da KAP'tan al. Dönüş: {"ok": True, "data": ...} veya {"ok": False, "reason": ...}.

    İndirme hatası ``KapUnavailable`` olarak çıkar (önbelleğe YAZILMAZ); biçim hatası kalıcı "ayrıştırılamadı" kaydı olur."""
    hit = cached(kind, d.index, cache_dir)
    if hit:
        return hit
    try:
        resp = kap_get(f"{BASE_URL}/tr/Bildirim/{d.index}", headers=default_headers(), timeout=90)
        resp.raise_for_status()
    except requests.RequestException as exc:
        raise KapUnavailable(f"KAP bildirimi indirilemedi {d.index}: {exc}") from exc
    parser = parse_dividend if kind == "div" else parse_buyback
    try:
        data = parser(resp.content, d.ticker)
        doc: dict[str, Any] = {"ok": True, "data": data}
    except Unparsable as exc:
        doc = {"ok": False, "reason": exc.reason}
    except Exception as exc:  # beklenmeyen: kalıcı sayma, bir sonraki koşuda yeniden dene
        log.warning("KAP olay bildirimi işlenemedi %s: %s", d.index, exc)
        raise KapUnavailable(f"beklenmeyen ayrıştırma hatası {d.index}") from exc
    doc.update({"parser_version": PARSER_VERSION, "fetched_at": fetched_at, "disclosure_index": d.index})
    cache_dir.mkdir(parents=True, exist_ok=True)
    _cache_file(kind, d.index, cache_dir).write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    return doc


def disclosure_url(index: str) -> str:
    return f"{BASE_URL}/tr/Bildirim/{index}"


def window(days: int, today: date | None = None) -> tuple[date, date]:
    end = today or date.today()
    return end - timedelta(days=days), end
