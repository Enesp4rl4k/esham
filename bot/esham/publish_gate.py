"""Yayın kapısının durum kayıtları (kapı mantığı: ``report_gate.py``).

Rapor başına kapı bir ya da birkaç raporu ayırdıysa (``partial``) YALNIZ o raporlar için:

- bu koşunun o raporlara ait giden kutusu kayıtları silinir (hiç gönderilmediler, origin'de de yoklar),
- o raporlara dönüşen KAP bildirimleri için ``gate_failures`` sayacı artar (aynı koşudaki sağlam raporlara
  ve bildirimlere dokunulmaz; onlar commit'lenir ve gönderilir). Sayaç
  ``MAX_PUBLISH_ATTEMPTS`` (3) altındaysa bildirimin "görüldü" işareti kaldırılır, sonraki koşu yeniden
  dener; sınıra ulaşınca ``failed_disclosures``'a neden ve deneme sayısıyla yazılır ve bir daha denenmez.

Sayaç ``publish_attempts``'tan AYRIDIR: o sayaç başarılı rapor yazımında sıfırlanır; kapı ise rapor
yazıldıktan SONRA kırıldığı için aynı sayaç her koşuda sıfırlanır ve sınıra hiç ulaşılmazdı.

Testler yeni raporlar OLMADAN da kırıksa (``code_broken``) hiçbir sayaç artmaz: koşunun durumu atılır, master'daki
duruma yalnız ``code_gate_broken`` işareti eklenir (günde bir commit = günlük tek uyarı); bildirimler sonraki
koşuda yeniden denenir (gönderimsiz, sınırsız).
"""
from __future__ import annotations

import time

from .config import get_logger
from .publishing.outbox import Outbox, current_run_id
from .state import StateStore, get_state

log = get_logger(__name__)

#: news_stream.MAX_PUBLISH_ATTEMPTS ile aynı kural (döngüsel içe aktarmayı önlemek için burada da).
MAX_GATE_ATTEMPTS = 3
_GATE_RETENTION_SECONDS = 14 * 24 * 3600


def record_publication(state: StateStore, *, key: str, title: str, date: str, index: str, slug: str) -> None:
    """news_stream: bu koşuda rapora dönüşen KAP bildirimini kaydeder (kapı kırılırsa geri alınabilsin)."""
    run = current_run_id()
    pubs = [p for p in (state.get("run_publications", []) or []) if p.get("run") == run]
    pubs.append({"run": run, "key": key, "title": title, "date": date, "index": index, "slug": slug})
    state.set("run_publications", pubs)


def reset_run_publications(state: StateStore) -> None:
    """Önceki koşuların kaydını atar (o koşular ya commit'lendi ya hiç commit'lenmedi)."""
    run = current_run_id()
    pubs = state.get("run_publications", []) or []
    if any(p.get("run") != run for p in pubs):
        state.set("run_publications", [p for p in pubs if p.get("run") == run])


def _blame(data: dict, pubs: list[dict], reason: str, now: float) -> tuple[list[str], list[str]]:
    """Suçu rapora yazar: ``gate_failures`` sayacı artar; 3'te ``failed_disclosures`` (``data`` yerinde değişir)."""
    counters: dict = {
        k: v for k, v in (data.get("gate_failures", {}) or {}).items()
        if now - float(v.get("last", 0)) < _GATE_RETENTION_SECONDS
    }
    seen: dict = dict(data.get("seen_disclosures", {}) or {})
    failed = list(data.get("failed_disclosures", []) or [])
    retry, given_up = [], []
    for p in pubs:
        key = p["key"]
        c = {"count": int(counters.get(key, {}).get("count", 0)) + 1, "last": now, "reason": reason[:300]}
        counters[key] = c
        if c["count"] >= MAX_GATE_ATTEMPTS:
            failed.append({
                "title": p.get("title", ""), "date": p.get("date", ""), "index": p.get("index", ""),
                "status": "gate_failed", "reason": reason[:300], "attempts": c["count"],
            })
            seen.setdefault(key, now)  # görüldü kalır: bir daha denenmez
            given_up.append(key)
            log.error("Yayın kapısı %d kez kırıldı; bildirim bırakıldı (elle kontrol): %s", c["count"], p.get("title", "")[:120])
        else:
            seen.pop(key, None)  # sonraki koşuda yeniden denenir
            retry.append(key)
            log.warning("Yayın kapısı kırıldı (deneme %d/%d); bildirim sonraki koşuda yeniden denenecek: %s",
                        c["count"], MAX_GATE_ATTEMPTS, p.get("title", "")[:120])
    data["gate_failures"] = counters
    data["seen_disclosures"] = seen
    data["failed_disclosures"] = failed[-200:]
    return retry, given_up


def _run_pubs(data: dict, slugs: set[str]) -> list[dict]:
    run = current_run_id()
    return [p for p in (data.get("run_publications", []) or []) if p.get("run") == run and p.get("slug") in slugs]


def handle_gate_failure(reason: str, slugs: list[str] | set[str], state: StateStore | None = None,
                        outbox: Outbox | None = None) -> dict:
    """``partial`` (aynı koşuda EN AZ BİR rapor geçti): YALNIZ kırılan raporlar (``slugs``) için gönderiler
    iptal, KAP bildirimlerinin sayacı artar. Aynı koşudaki sağlam raporlara ve bildirimlere dokunulmaz."""
    state = state or get_state()
    outbox = outbox or Outbox()
    run = current_run_id()
    slugs = set(slugs)
    dropped = outbox.drop_run(run, slugs=slugs)
    now = time.time()
    data = {k: state.get(k) for k in ("gate_failures", "seen_disclosures", "failed_disclosures", "run_publications")}
    retry, given_up = _blame(data, _run_pubs(data, slugs), reason, now)
    for k in ("gate_failures", "seen_disclosures", "failed_disclosures"):
        state.set(k, data[k])
    suspects = dict(state.get("gate_suspects", {}) or {})
    if any(k in suspects for k in given_up):
        state.set("gate_suspects", {k: v for k, v in suspects.items() if k not in given_up})
    state.set("last_gate_failure", {
        "run": run, "at": now, "reason": reason[:300], "reports": sorted(slugs),
        "dropped_posts": [e["key"] for e in dropped], "retry": retry, "given_up": given_up,
    })
    return {"dropped_posts": len(dropped), "retry": retry, "given_up": given_up}


def note_successful_gate(state: StateStore, passed_slugs: list[str] | set[str]) -> None:
    """Koşuda EN AZ BİR yeni rapor kapıdan geçti: kodun yeni raporları kabul ettiği görüldü.

    Şüpheli (daha önce "hepsi kırıldı" koşusunda kırılmış) her bildirime ``success_since = True`` yazılır;
    bu koşuda raporu geçen bildirim şüpheliden çıkar."""
    suspects = dict(state.get("gate_suspects", {}) or {})
    if not suspects:
        return
    passed = {p["key"] for p in _run_pubs({"run_publications": state.get("run_publications")}, set(passed_slugs))}
    state.set("gate_suspects", {k: {**v, "success_since": True} for k, v in suspects.items() if k not in passed})


def code_broken_marker(head_state: dict, today: str) -> tuple[dict, bool]:
    """Kod/test kırık: koşunun durumu ATILIR (hiçbir sayaç artmaz, bildirimler sonraki koşuda yeniden denenir).
    Yalnız master'daki duruma ``code_gate_broken`` işareti eklenir; günde bir kez commit'lenir (günlük tek
    uyarı). Döner: (yazılacak durum, bugün ilk uyarı mı)."""
    st = dict(head_state)
    mark = dict(st.get("code_gate_broken") or {})
    first_today = mark.get("last_alert_day") != today
    mark.setdefault("since", today)
    mark["last_alert_day"] = today
    st["code_gate_broken"] = mark
    return st, first_today


def handle_all_broken(head_state: dict, pubs: list[dict], reason: str, today: str,
                      now: float | None = None) -> tuple[dict, dict]:
    """Temel yeşil ama yeni raporların HEPSİ kırık (tek raporlu koşu dahil) → KOD sorunu sayılır.

    Durum makinesi (bildirim başına ``gate_suspects[key]``):

    - yok ──(hepsi-kırık koşuda kırıldı)──▶ şüpheli{success_since=False}       [sayaç YOK]
    - şüpheli{False} ──(hepsi-kırık koşuda yine kırıldı)──▶ aynı                 [sayaç YOK, kod sorunu]
    - şüpheli{False} ──(başka raporların geçtiği bir koşu)──▶ şüpheli{True}      (``note_successful_gate``)
    - şüpheli{True} ──(hepsi-kırık koşuda yine kırıldı)──▶ şüpheli{False}       [suç RAPORA: sayaç +1]
    - herhangi ──(rapor geçti)──▶ yok;  sayaç 3 ──▶ ``failed_disclosures``, yok
    - (``partial`` koşuda kırılan rapor şüpheli olmadan da doğrudan sayılır: ``handle_gate_failure``.)

    Koşunun kendi durumu atılır; ``head_state`` (master) üzerine yalnız işaret, şüpheliler ve suçlanan
    bildirimlerin sayaçları yazılır. Döner: (yazılacak durum, bilgi).
    """
    now = time.time() if now is None else now
    st, first_today = code_broken_marker(head_state, today)
    before = dict(st.get("gate_suspects", {}) or {})
    suspects = dict(before)
    blame: list[dict] = []
    for p in pubs:
        s = suspects.get(p["key"])
        if s and s.get("success_since"):
            blame.append(p)
            suspects[p["key"]] = {**s, "success_since": False}
        elif s is None:
            suspects[p["key"]] = {"since": today, "success_since": False, "title": p.get("title", "")[:120]}
    retry, given_up = _blame(st, blame, reason, now) if blame else ([], [])
    for k in given_up:
        suspects.pop(k, None)
    st["gate_suspects"] = suspects
    info = {"first_alert": first_today, "blamed": [p["key"] for p in blame], "retry": retry, "given_up": given_up,
            "commit": first_today or suspects != before or bool(blame)}
    return st, info
