"""Hesap bazlı teminat (margin) izleme ve margin-call motoru.

Deterministiktir; veri kaynağından bağımsız çalışır. Girdi: açık pozisyonlar,
güncel fiyatlar (mark), nakit bakiye ve kontrat teminat parametreleri (Takasbank/
broker değerleri). Çıktı: gereken başlangıç/sürdürme teminatı, özkaynak, teminat
kullanımı ve margin-call durumu.

Teminat parametreleri (initial/maintenance, kontrat çarpanı) Takasbank tarafından
belirlenir ve zamanla değişir; buradaki varsayılanlar TEMSİLİDİR — üretimde güncel
Takasbank değerleriyle beslenmelidir.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from ..formatting import tr_number

# Durum eşikleri
STATUS_OK = "OK"
STATUS_WARN = "UYARI"
STATUS_CALL = "MARGIN CALL"


@dataclass
class MarginParameter:
    symbol: str
    contract_size: float  # 1 kontratın çarpanı (fiyat puanı başına TL)
    initial_margin: float  # kontrat başına başlangıç teminatı (TL)
    maintenance_margin: float  # kontrat başına sürdürme teminatı (TL)


@dataclass
class Position:
    symbol: str
    side: str  # "long" | "short"
    quantity: int  # kontrat adedi
    entry_price: float
    mark: float | None = None  # güncel fiyat; yoksa entry kullanılır

    @property
    def direction(self) -> int:
        return 1 if self.side.lower().startswith("l") else -1

    def unrealized_pnl(self, param: MarginParameter) -> float:
        mark = self.mark if self.mark is not None else self.entry_price
        return (mark - self.entry_price) * self.quantity * param.contract_size * self.direction


@dataclass
class MarginReport:
    account: str
    equity: float
    cash_balance: float
    unrealized_pnl: float
    initial_required: float
    maintenance_required: float
    free_margin: float
    utilization_pct: float
    status: str
    shortfall: float = 0.0
    alerts: list[str] = field(default_factory=list)

    def utilization_pretty(self) -> str:
        import math

        if not math.isfinite(self.utilization_pct):
            return "aşıldı"
        return f"%{tr_number(self.utilization_pct, 1)}"

    def summary_line(self) -> str:
        return (
            f"[{self.status}] {self.account}: özkaynak {tr_number(self.equity, 0)} TL, "
            f"sürdürme {tr_number(self.maintenance_required, 0)} TL, "
            f"kullanım {self.utilization_pretty()}"
        )


class MarginMonitor:
    def __init__(self, parameters: dict[str, MarginParameter]) -> None:
        self.parameters = parameters

    def evaluate(
        self,
        positions: list[Position],
        cash_balance: float,
        account: str = "HESAP",
    ) -> MarginReport:
        unrealized = 0.0
        initial_req = 0.0
        maint_req = 0.0
        alerts: list[str] = []

        for pos in positions:
            param = self.parameters.get(pos.symbol)
            if param is None:
                alerts.append(
                    f"{pos.symbol}: teminat parametresi tanımlı değil; pozisyon atlandı."
                )
                continue
            unrealized += pos.unrealized_pnl(param)
            initial_req += pos.quantity * param.initial_margin
            maint_req += pos.quantity * param.maintenance_margin

        equity = cash_balance + unrealized
        free_margin = equity - maint_req
        utilization = (maint_req / equity * 100) if equity > 0 else float("inf")

        if equity < maint_req:
            status = STATUS_CALL
            shortfall = maint_req - equity
            alerts.append(
                f"🚨 MARGIN CALL: özkaynak ({tr_number(equity, 0)} TL) sürdürme "
                f"teminatının ({tr_number(maint_req, 0)} TL) altında. "
                f"Tamamlanması gereken: {tr_number(shortfall, 0)} TL."
            )
        elif equity < initial_req:
            status = STATUS_WARN
            shortfall = 0.0
            alerts.append(
                f"⚠️ Özkaynak başlangıç teminatının altında; yeni pozisyon açılamaz, "
                f"margin-call'a yakın."
            )
        else:
            status = STATUS_OK
            shortfall = 0.0

        return MarginReport(
            account=account,
            equity=equity,
            cash_balance=cash_balance,
            unrealized_pnl=unrealized,
            initial_required=initial_req,
            maintenance_required=maint_req,
            free_margin=free_margin,
            utilization_pct=utilization,
            status=status,
            shortfall=shortfall,
            alerts=alerts,
        )


def default_parameters() -> dict[str, MarginParameter]:
    """TEMSİLİ VİOP teminat parametreleri. Üretimde Takasbank değerleriyle güncelleyin."""
    return {
        # BIST30 endeks vadeli (temsili çarpan/teminat).
        "XU030": MarginParameter("XU030", contract_size=10.0, initial_margin=9000.0, maintenance_margin=7000.0),
        "XU100": MarginParameter("XU100", contract_size=10.0, initial_margin=11000.0, maintenance_margin=8500.0),
    }


def load_parameters_file(path: str | Path) -> dict[str, MarginParameter]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    params = {}
    for row in data:
        params[row["symbol"]] = MarginParameter(
            symbol=row["symbol"],
            contract_size=float(row["contract_size"]),
            initial_margin=float(row["initial_margin"]),
            maintenance_margin=float(row["maintenance_margin"]),
        )
    return params


def load_positions_file(path: str | Path) -> tuple[str, float, list[Position]]:
    """Pozisyon dosyasını okur: {account, cash_balance, positions:[...]}."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    account = str(data.get("account", "HESAP"))
    cash = float(data.get("cash_balance", 0))
    positions = [
        Position(
            symbol=p["symbol"],
            side=p.get("side", "long"),
            quantity=int(p["quantity"]),
            entry_price=float(p["entry_price"]),
            mark=float(p["mark"]) if p.get("mark") is not None else None,
        )
        for p in data.get("positions", [])
    ]
    return account, cash, positions
