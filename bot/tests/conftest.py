"""Ortak test ayarı: hiçbir test gerçek giden kutusuna (bot/state/telegram_outbox.json) yazmaz."""
from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _isolated_outbox(tmp_path, monkeypatch):
    monkeypatch.setenv("ESHAM_OUTBOX_FILE", str(tmp_path / "outbox" / "telegram_outbox.json"))
    monkeypatch.delenv("GITHUB_RUN_ID", raising=False)
    monkeypatch.delenv("GITHUB_RUN_ATTEMPT", raising=False)
