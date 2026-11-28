"""Ortak test ayarları.

- Hiçbir test gerçek giden kutusuna (bot/state/telegram_outbox.json) yazmaz.
- ``network`` işaretli OLMAYAN hiçbir test dış ağa çıkamaz: soket bağlantısı ve DNS çözümlemesi yalnız yerel
  adreslere (127.0.0.1, ::1, localhost) izinli; dış bağlantı denemesi testi KIRAR (sessizce canlı Yahoo/KAP'a
  gitmesin; ör. bir kaynak yeni bir HTTP çağrısı eklediğinde taklit edilmemişse hemen görünür).
"""
from __future__ import annotations

import socket

import pytest

_LOCAL = {"127.0.0.1", "::1", "localhost", "0.0.0.0"}


class ExternalNetworkBlocked(RuntimeError):
    """Test dış ağa çıkmaya çalıştı (``@pytest.mark.network`` işaretli değil)."""


def _host(address) -> str | None:
    if isinstance(address, tuple) and address:
        return str(address[0])
    return None  # AF_UNIX vb. (yol) — yerel


@pytest.fixture(autouse=True)
def _isolated_outbox(tmp_path, monkeypatch):
    monkeypatch.setenv("ESHAM_OUTBOX_FILE", str(tmp_path / "outbox" / "telegram_outbox.json"))
    monkeypatch.delenv("GITHUB_RUN_ID", raising=False)
    monkeypatch.delenv("GITHUB_RUN_ATTEMPT", raising=False)


@pytest.fixture(autouse=True)
def _no_external_network(request, monkeypatch):
    if request.node.get_closest_marker("network"):
        yield
        return
    attempts: list[str] = []
    request.node.esham_network_attempts = attempts  # öz-test temizleyebilsin
    real_connect = socket.socket.connect
    real_connect_ex = socket.socket.connect_ex
    real_getaddrinfo = socket.getaddrinfo

    def check(address) -> None:
        host = _host(address)
        if host is not None and host not in _LOCAL:
            attempts.append(repr(address))
            raise ExternalNetworkBlocked(f"test dış ağa çıkmaya çalıştı: {address!r}")

    def connect(self, address):
        check(address)
        return real_connect(self, address)

    def connect_ex(self, address):
        check(address)
        return real_connect_ex(self, address)

    def getaddrinfo(host, *args, **kwargs):
        if host is not None and str(host) not in _LOCAL:
            attempts.append(repr(host))
            raise ExternalNetworkBlocked(f"test dış adres çözümlemeye çalıştı: {host!r}")
        return real_getaddrinfo(host, *args, **kwargs)

    monkeypatch.setattr(socket.socket, "connect", connect)
    monkeypatch.setattr(socket.socket, "connect_ex", connect_ex)
    monkeypatch.setattr(socket, "getaddrinfo", getaddrinfo)
    yield
    # Kaynak kodu istisnayı yutsa bile (ör. `except Exception`) deneme kaydedilir ve test kırılır.
    if attempts:
        pytest.fail("network işaretsiz test dış ağa çıkmaya çalıştı: " + ", ".join(attempts[:5]))
