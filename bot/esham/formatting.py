"""Türkçe sayı / yüzde / tarih biçimleme — TEK kaynak.

Yayınlanan her metin (rapor, özet, kart başlığı, Telegram) sayıları buradan geçirir; üreticilerde
ad-hoc ``f"{x:.2f}%"`` yazılmaz (``tests/test_formatting_and_sentences.py`` kaynakta denetler).

Seçilen kural (bir kez seçildi, her yerde aynı):

- Ondalık ayırıcı virgül, binlik ayırıcı nokta: ``1234567.891 -> "1.234.567,89"``.
- Yüzde işareti sayının ÖNÜNDE (TDK yazımı): ``"%4,91"``.
- İşaretli değişimde işaret yüzde işaretinin önünde: ``"+%2,18"``, ``"-%0,06"``. Yuvarlanınca sıfır olan
  değer işaretsiz yazılır (``"%0,00"``; ``"-%0,00"`` yazılmaz). Eksi işareti ASCII ``-`` (kart ve PDF
  renklendirmesi ``startswith("+")`` / ``startswith("-")`` ile çalışır).
- Tahvil faizi gibi zaten yüzde olan büyüklüklerin değişimi baz puanla yazılır: ``"+6 baz puan"``.
- Zaman damgaları Türkiye saatiyle: ``"27.11.2026 18:10 TSİ"``; tarih ``"27.11.2026"``.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

TR_TZ = timezone(timedelta(hours=3))


def tr_number(value: float, decimals: int = 2) -> str:
    """1234567.89 -> '1.234.567,89'."""
    s = f"{value:,.{decimals}f}"
    return s.replace(",", "\x00").replace(".", ",").replace("\x00", ".")


def _is_zero(value: float, decimals: int) -> bool:
    return round(abs(value), decimals) == 0


def tr_signed(value: float, decimals: int = 2) -> str:
    """İşaretli sayı: +1.234,50 / -0,06 / 0,00 (yuvarlanınca sıfırsa işaretsiz)."""
    if _is_zero(value, decimals):
        return tr_number(0.0, decimals)
    return ("+" if value > 0 else "-") + tr_number(abs(value), decimals)


def tr_pct(value: float, decimals: int = 2, *, signed: bool = True) -> str:
    """Yüzde: işaretli ``+%2,18`` / ``-%1,02`` / ``%0,00``; ``signed=False`` ile düzey ``%4,91``."""
    if not signed:
        return f"%{tr_number(value, decimals)}"
    if _is_zero(value, decimals):
        return f"%{tr_number(0.0, decimals)}"
    return ("+" if value > 0 else "-") + f"%{tr_number(abs(value), decimals)}"


def tr_bp(points: float) -> str:
    """Yüzde puan cinsinden değişimi baz puanla yazar: 0.06 -> '+6 baz puan'."""
    bp = points * 100
    if round(abs(bp)) == 0:
        return "0 baz puan"
    return ("+" if bp > 0 else "-") + f"{tr_number(abs(bp), 0)} baz puan"


def parse_tr_pct(text: str) -> float | None:
    """'+%2,18' / '-%1,02' / '+2,18%' / '%0,00' -> float; çözülemezse None."""
    s = (text or "").strip().replace("%", "").replace(".", "").replace(",", ".").replace(" ", "")
    try:
        return float(s)
    except ValueError:
        return None


def tr_money(value: float) -> str:
    """Büyüklüğe göre Milyar/Milyon TL biçimler."""
    if abs(value) >= 1e9:
        return f"{tr_number(value / 1e9, 1)} Milyar TL"
    if abs(value) >= 1e6:
        return f"{tr_number(value / 1e6, 1)} Milyon TL"
    return f"{tr_number(value, 0)} TL"


def tr_date(value: date | datetime) -> str:
    """Tarih: '27.11.2026' (datetime ise Türkiye saatine çevrilerek)."""
    if isinstance(value, datetime):
        value = to_tr(value).date()
    return value.strftime("%d.%m.%Y")


def tr_datetime(value: datetime) -> str:
    """Zaman damgası: '27.11.2026 18:10 TSİ'."""
    return to_tr(value).strftime("%d.%m.%Y %H:%M") + " TSİ"


def to_tr(value: datetime) -> datetime:
    """Saat dilimi olmayan değer UTC kabul edilir; Türkiye saatine çevrilir."""
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(TR_TZ)


def from_epoch(ts: object) -> datetime | None:
    """Unix zaman damgası (sn) -> Türkiye saatli datetime; geçersizse None."""
    try:
        return datetime.fromtimestamp(float(ts), tz=timezone.utc).astimezone(TR_TZ)  # type: ignore[arg-type]
    except (TypeError, ValueError, OverflowError, OSError):
        return None
