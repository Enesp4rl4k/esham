"""Türkçe sayı/para biçimleme yardımcıları."""
from __future__ import annotations


def tr_number(value: float, decimals: int = 2) -> str:
    """1234567.89 -> '1.234.567,89'."""
    s = f"{value:,.{decimals}f}"
    return s.replace(",", "\x00").replace(".", ",").replace("\x00", ".")


def tr_money(value: float) -> str:
    """Büyüklüğe göre Milyar/Milyon TL biçimler."""
    if abs(value) >= 1e9:
        return f"{tr_number(value / 1e9, 1)} Milyar TL"
    if abs(value) >= 1e6:
        return f"{tr_number(value / 1e6, 1)} Milyon TL"
    return f"{tr_number(value, 0)} TL"
