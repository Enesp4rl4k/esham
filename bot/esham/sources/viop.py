"""VİOP (Vadeli İşlem ve Opsiyon Piyasası) veri kaynağı.

İki tür veri:
1. Piyasa kotasyonu — BIST30 endeksi (XU030) ve vadeli (XU030D) TradingView
   scanner API'sinden (canlı, sağlam).
2. Piyasa geneli teminat agregatı — Takasbank resmi kamu bülteninden (teminatlı hesap sayısı,
   margin-call toplamı, gereken teminat).
"""
from __future__ import annotations

import html
import re
from dataclasses import dataclass
from datetime import datetime, timezone

import requests

from ..config import default_headers, get_logger, sample_data_allowed, settings
from ..http import retry_get, retry_post
from ..formatting import tr_money, tr_number, tr_pct

log = get_logger(__name__)

TV_SCAN_URL = "https://scanner.tradingview.com/turkey/scan"
TAKASBANK_VIOP_PAGE = "https://www.takasbank.com.tr/tr/istatistikler/vadeli-islem-ve-opsiyon-piyasasi-viop"


@dataclass
class ViopQuote:
    index_symbol: str
    index_price: str
    index_change: str
    # Vadeli satırı yoksa tümü None: "vadeli kotasyon yok". Asla türetilmiş/sentetik fiyat yazılmaz.
    futures_symbol: str | None = None
    futures_price: str | None = None
    futures_change: str | None = None
    futures_volume: str | None = None
    # Ham sayısal değerler (basis hesabı için); yalnızca gerçek yanıttan doldurulur.
    index_value: float | None = None
    futures_value: float | None = None
    # TradingView tarama yanıtı işlem zamanı vermez; yalnız verinin ÇEKİLDİĞİ an bilinir (öyle etiketlenir).
    fetched_at: datetime | None = None

    @property
    def has_futures(self) -> bool:
        """Gerçek bir vadeli kotasyon (sembol + fiyat) var mı?"""
        return bool(self.futures_symbol and self.futures_price)


@dataclass
class ViopMarginSnapshot:
    as_of: str
    margined_account_count: int
    margin_call_total_tl: float
    required_margin_total_tl: float
    margin_call_to_required_pct: float
    futures_oi_value_tl: float = 0.0
    futures_volume_tl: float = 0.0
    options_volume_tl: float = 0.0
    profit_loss_total_tl: float = 0.0
    is_sample: bool = False

    def margin_call_pretty(self) -> str:
        return tr_money(self.margin_call_total_tl)

    def required_pretty(self) -> str:
        return tr_money(self.required_margin_total_tl)


@dataclass
class MarginStress:
    level: str  # "Yükseliyor" | "Sabit" | "Geriliyor" | "Bilinmiyor"
    note: str


def _change_str(pct: float) -> str:
    return tr_pct(pct)


class ViopSource:
    def __init__(self) -> None:
        self.headers = default_headers()

    # ---- piyasa kotasyonu ------------------------------------------------------

    def market_quote(self) -> ViopQuote | None:
        try:
            resp = retry_post(
                TV_SCAN_URL,
                json={
                    "symbols": {"tickers": ["BIST:XU030", "BIST:XU030D"]},
                    "columns": ["name", "close", "change", "volume"],
                },
                headers=self.headers,
                timeout=settings.http_timeout,
            )
            resp.raise_for_status()
            quote = self._parse_quote(resp.json())
            if quote:
                return quote
            log.warning("VİOP kotasyonu ayrıştırılamadı.")
        except (requests.RequestException, ValueError) as exc:
            log.warning("VİOP kotasyonu alınamadı (%s).", exc)
        if sample_data_allowed():
            log.warning("ESHAM_ALLOW_SAMPLE_DATA açık: VİOP için ÖRNEK veri kullanılıyor (yalnızca geliştirme).")
            return self._sample_quote()
        log.warning("VİOP kotasyonu temin edilemedi; örnek veri üretilmiyor (None).")
        return None

    def _parse_quote(self, payload: dict) -> ViopQuote | None:
        rows = {r["s"]: r["d"] for r in payload.get("data", []) if "s" in r and "d" in r}
        idx = rows.get("BIST:XU030")
        fut = rows.get("BIST:XU030D")
        if not idx:
            return None
        # d = [name, close, change, volume]
        q = ViopQuote(
            index_symbol="XU030",
            index_price=tr_number(float(idx[1])) if idx[1] is not None else "",
            index_change=_change_str(float(idx[2])) if idx[2] is not None else "",
            index_value=float(idx[1]) if idx[1] is not None else None,
            fetched_at=datetime.now(timezone.utc),
        )
        if fut and len(fut) > 1 and fut[1] is not None:
            q.futures_symbol = "XU030D"
            q.futures_price = tr_number(float(fut[1]))
            q.futures_value = float(fut[1])
            q.futures_change = _change_str(float(fut[2])) if len(fut) > 2 and fut[2] is not None else None
            # TradingView "volume" vadelide kontrat ADEDİDİR; eskiden tr_money ile "Milyar TL" diye yazılıyordu
            # (yanlış birim). Birim doğrulanamadığı için yayınlanmaz.
            q.futures_volume = None
        else:
            log.warning("VİOP vadeli (XU030D) satırı yok; vadeli kotasyon yayınlanmayacak (sentetik fiyat üretilmez).")
        return q

    def _sample_quote(self) -> ViopQuote:
        return ViopQuote(
            index_symbol="XU030",
            index_price="16.740,68",
            index_change="-0,31%",
            futures_symbol="XU030D",
            futures_price="16.910,00",
            futures_change="-0,28%",
            futures_volume="113,5 Milyar TL",
        )

    # ---- marketwide teminat agregatı ------------------------------------------

    def margin_snapshot(self) -> ViopMarginSnapshot | None:
        """Takasbank resmi kamu bülteninden gerçek VİOP teminat verilerini çeker.
        
        Kullanıcı güvenliği ve yasal hassasiyet gereği ASLA yapay/sentetik rakam üretilmez.
        Veri çekilemezse None döner.
        """
        # 1. Öncelikli Kaynak: Takasbank Resmi Kamu İstatistik Sayfası
        try:
            snap = self._fetch_takasbank_official()
            if snap:
                return snap
        except Exception as exc:
            log.warning("Takasbank resmi bülteni ayrıştırılamadı (%s).", exc)

        # 2. İkincil Kaynak: Özel tanımlı Takasbank API URL'si
        url = settings.takasbank_viop_url
        if url:
            try:
                resp = retry_get(url, headers=self.headers, timeout=settings.http_timeout)
                resp.raise_for_status()
                snap = self._parse_margin(resp.json())
                if snap:
                    return snap
            except (requests.RequestException, ValueError) as exc:
                log.warning("Özel Takasbank API verisi alınamadı (%s).", exc)

        # ASLA sahte / yapay teminat rakamı üretme!
        log.warning("Takasbank resmi teminat verisi temin edilemedi; yapay veri üretilmiyor.")
        return None

    def _fetch_takasbank_official(self) -> ViopMarginSnapshot | None:
        """Takasbank VİOP Takas Merkezi günlük resmi bültenini çeker ve ayrıştırır."""
        try:
            # Takasbank HTML sayfası Accept: application/json başlığı aldığında bot kalkanı devreye girer;
            # bu nedenle temiz tarayıcı User-Agent başlığı kullanılır.
            takas_headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            resp = requests.get(TAKASBANK_VIOP_PAGE, headers=takas_headers, timeout=settings.http_timeout)
            resp.raise_for_status()
            text = resp.text

            date_match = re.search(r"(\d{2}\.\d{2}\.\d{4})\s*Tarihli", text)
            as_of = date_match.group(1) if date_match else datetime.now(timezone.utc).strftime("%d.%m.%Y")

            table_match = re.search(r"<table[^>]*class=['\"]grey-table['\"][^>]*>(.*?)</table>", text, re.S)
            if not table_match:
                table_match = re.search(r"<table[^>]*>(.*?)</table>", text, re.S)
            if not table_match:
                return None

            rows = re.findall(r"<tr[^>]*>(.*?)</tr>", table_match.group(1), re.S)
            data = {}
            for r in rows:
                cells = [html.unescape(re.sub(r"<[^>]+>", "", c).strip()) for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", r, re.S)]
                if len(cells) >= 2:
                    key = cells[0].strip()
                    val = cells[1].strip()
                    data[key] = val

            def parse_num(v_str: str) -> float:
                clean = v_str.replace(".", "").replace(",", ".").strip()
                return float(clean)

            def get_num(key_substr: str) -> float:
                for k, v in data.items():
                    if key_substr.lower() in k.lower():
                        m = re.search(r"(\d+(?:\.\d+)*(?:,\d+)?)", v)
                        if m:
                            return parse_num(m.group(1))
                return 0.0

            def get_int(key_substr: str) -> int:
                return int(get_num(key_substr))

            req = get_num("Bulunması Gereken Teminat") or get_num("Bulunmas Gereken Teminat")
            call = get_num("Teminat Tamamlama Çağrısı") or get_num("Teminat Tamamlama ars")
            acc = get_int("Teminatlı Hesap Sayısı") or get_int("Teminatl Hesap Says")
            fut_vol = get_num("Vadeli İşlem Sözleşmesi İşlem Hacmi") or get_num("Vadeli lem Szlemesi lem Hacmi")
            opt_vol = get_num("Opsiyon İşlem Hacmi") or get_num("Opsiyon lem Hacmi")
            oi_val = get_num("Vadeli İşlem Sözleşmesi Açık Pozisyon Değeri") or get_num("Vadeli lem Szlemesi Ak Pozisyon Deeri")
            pnl = get_num("Kar / Zarar Tutarı") or get_num("Kar / Zarar Tutar")

            if req <= 0:
                return None

            pct = (call / req * 100.0) if req > 0 else 0.0

            return ViopMarginSnapshot(
                as_of=as_of,
                margined_account_count=acc,
                margin_call_total_tl=call,
                required_margin_total_tl=req,
                margin_call_to_required_pct=round(pct, 4),
                futures_oi_value_tl=oi_val,
                futures_volume_tl=fut_vol,
                options_volume_tl=opt_vol,
                profit_loss_total_tl=pnl,
                is_sample=False,
            )
        except Exception as exc:
            log.warning("Takasbank resmi sayfası çekilemedi: %s", exc)
            return None

    def _parse_margin(self, payload: dict) -> ViopMarginSnapshot | None:
        snap = payload.get("snapshot", payload)
        if not isinstance(snap, dict) or "required_margin_total_tl" not in snap:
            return None

        def num(key: str) -> float:
            v = snap.get(key, 0)
            return float(v) if isinstance(v, (int, float)) else 0.0

        required = num("required_margin_total_tl")
        call = num("margin_call_total_tl")
        if required <= 0:
            return None

        pct = snap.get("margin_call_to_required_pct")
        if not isinstance(pct, (int, float)):
            pct = (call / required * 100) if required else 0.0
        return ViopMarginSnapshot(
            as_of=str(payload.get("as_of", datetime.now(timezone.utc).isoformat())),
            margined_account_count=int(num("margined_account_count")),
            margin_call_total_tl=call,
            required_margin_total_tl=required,
            margin_call_to_required_pct=float(pct),
            futures_oi_value_tl=num("futures_oi_value_tl"),
            futures_volume_tl=num("futures_volume_tl"),
            options_volume_tl=num("options_volume_tl"),
            profit_loss_total_tl=num("profit_loss_total_tl"),
            is_sample=False,
        )


def assess_margin_stress(
    today_pct: float, prior_pct: float | None = None, *, jump_threshold: float = 0.05
) -> MarginStress:
    """margin_call/required oranını ÖNCEKİ KAYITLI ÖLÇÜMLE kıyaslayarak yönünü çıkarır.

    Önceki değer, bir önceki VİOP raporu koşusunda kaydedilen orandır; tarihi saklanmadığı için metin
    "önceki güne göre" DEMEZ ("önceki kayıtlı ölçüme göre"). Oranlar tablodaki gibi 3 ondalıkla yazılır.
    `jump_threshold`: oranın yüzde-puan bazında anlamlı değişim eşiği.
    """
    if prior_pct is None:
        return MarginStress("Bilinmiyor", "Karşılaştırma için önceki kayıtlı ölçüm yok.")
    before, now = tr_pct(prior_pct, 3, signed=False), tr_pct(today_pct, 3, signed=False)
    delta = today_pct - prior_pct
    if delta >= jump_threshold:
        return MarginStress(
            "Yükseliyor",
            f"Margin-call/gereken teminat oranı {before} → {now} (önceki kayıtlı ölçüme göre yükseldi).",
        )
    if delta <= -jump_threshold:
        return MarginStress(
            "Geriliyor",
            f"Margin-call/gereken teminat oranı {before} → {now} (önceki kayıtlı ölçüme göre geriledi).",
        )
    return MarginStress(
        "Sabit",
        f"Margin-call/gereken teminat oranı {before} → {now} (önceki kayıtlı ölçüme göre fark "
        f"{tr_number(jump_threshold, 2)} puanın altında).",
    )
