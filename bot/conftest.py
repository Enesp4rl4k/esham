"""Bot testleri için ortak çevrimdışı ayar (``network`` işaretli testler hariç).

``BistSource.market_summary`` fiyat ve zaman damgasını aynı kaynaktan (Yahoo chart) almak için
``BistSource._yahoo_chart`` çağırır. Yalnız TradingView yanıtını (``retry_post``) sahteleyen testler
(ör. ``test_bist_market_summary_offline``) bu çağrı yüzünden canlı Yahoo'ya gitmesin diye, varsayılan
olarak ``_yahoo_chart`` "veri yok" (None) döner. Yahoo yanıtı gereken test kendi sahtesini monkeypatch ile kurar.

Dosya ``bot/tests/conftest.py`` yerine burada: o dosya başka bir PR'da (#31) ekleniyor; çakışmasın.
"""
from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _offline_yahoo_chart(request, monkeypatch):
    if request.node.get_closest_marker("network") is not None:
        return
    from esham.sources.bist import BistSource

    monkeypatch.setattr(BistSource, "_yahoo_chart", lambda self, *a, **k: None)
