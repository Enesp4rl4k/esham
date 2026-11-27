"""Yayın kapısı kırıldığında döngüyü durduran durum kaydı.

İş akışı (``.github/workflows/esham-schedule.yml``) yeni raporlarla web testlerini koşar. Testler kırılırsa
raporlar commit'lenmez, Telegram'a hiçbir şey gitmez ve bu modül YALNIZ şunları yazar (sonra yalnız durum
dosyası + giden kutusu commit'lenir):

- bu koşunun giden kutusu kayıtları silinir (hiç gönderilmediler, origin'de de yoklar),
- bu koşuda yayınlanan her KAP bildirimi için ``gate_failures`` sayacı artar. Sayaç
  ``MAX_PUBLISH_ATTEMPTS`` (3) altındaysa bildirimin "görüldü" işareti kaldırılır, sonraki koşu yeniden
  dener; sınıra ulaşınca ``failed_disclosures``'a neden ve deneme sayısıyla yazılır ve bir daha denenmez.

Sayaç ``publish_attempts``'tan AYRIDIR: o sayaç başarılı rapor yazımında sıfırlanır; kapı ise rapor
yazıldıktan SONRA kırıldığı için aynı sayaç her koşuda sıfırlanır ve sınıra hiç ulaşılmazdı.
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


def handle_gate_failure(reason: str, state: StateStore | None = None, outbox: Outbox | None = None) -> dict:
    state = state or get_state()
    outbox = outbox or Outbox()
    run = current_run_id()
    dropped = outbox.drop_run(run)

    now = time.time()
    counters: dict = {
        k: v for k, v in (state.get("gate_failures", {}) or {}).items()
        if now - float(v.get("last", 0)) < _GATE_RETENTION_SECONDS
    }
    seen: dict = dict(state.get("seen_disclosures", {}) or {})
    failed = list(state.get("failed_disclosures", []) or [])
    retry, given_up = [], []
    for p in [p for p in (state.get("run_publications", []) or []) if p.get("run") == run]:
        key = p["key"]
        c = counters.get(key, {"count": 0})
        c = {"count": int(c.get("count", 0)) + 1, "last": now, "reason": reason[:300]}
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

    state.set("gate_failures", counters)
    state.set("seen_disclosures", seen)
    state.set("failed_disclosures", failed[-200:])
    state.set("run_publications", [])
    state.set("last_gate_failure", {
        "run": run, "at": now, "reason": reason[:300],
        "dropped_posts": [e["key"] for e in dropped], "retry": retry, "given_up": given_up,
    })
    return {"dropped_posts": len(dropped), "retry": retry, "given_up": given_up}
