"""Fear & Greed (Korku ve Açgözlülük) Endeksi Hesaplayıcı.

Piyasa duygu durumunu 0-100 arası bir skora çevirir:
0-25: Aşırı Korku
26-45: Korku
46-55: Nötr
56-75: Açgözlülük
76-100: Aşırı Açgözlülük
"""
from __future__ import annotations

from dataclasses import dataclass
from ..sources.bist import BistSource
from ..sources.global_macro import GlobalMacroSource

@dataclass
class FearGreedResult:
    score: int
    label: str
    summary: str


def calculate_fear_greed() -> FearGreedResult:
    """BIST ve Küresel piyasa verilerine bakarak duygu durumunu hesaplar."""
    score = 50  # Başlangıç: Nötr
    reasons = []

    # BIST Durumu
    try:
        bist = BistSource().market_summary()
        pct_str = bist.change.replace("+", "").replace("%", "").replace(",", ".")
        bist_change = float(pct_str) if pct_str else 0.0
        
        if bist_change <= -2.0:
            score -= 20
            reasons.append(f"BIST sert düştü ({bist.change})")
        elif bist_change <= -0.5:
            score -= 10
            reasons.append(f"BIST satıcılı ({bist.change})")
        elif bist_change >= 2.0:
            score += 20
            reasons.append(f"BIST güçlü alıcılı ({bist.change})")
        elif bist_change >= 0.5:
            score += 10
            reasons.append(f"BIST alıcılı ({bist.change})")
    except Exception:
        pass

    # Küresel Makro Durum (VIX ve Altın)
    try:
        macro = GlobalMacroSource().snapshot()
        vix = next((t for t in macro.tickers if t.label == "VIX"), None)
        gold = next((t for t in macro.tickers if t.label == "ALTIN"), None)

        if vix:
            if vix.price >= 25.0:
                score -= 15
                reasons.append(f"Küresel volatilite çok yüksek (VIX: {vix.price})")
            elif vix.price <= 13.0:
                score += 10
                reasons.append("Küresel piyasalarda rehavet hakim (VIX düşük)")
                
        if gold and gold.change_pct >= 1.0:
            score -= 10
            reasons.append("Güvenli liman talebi (Altın) artıyor")
    except Exception:
        pass

    # Sınırlandırma
    score = max(0, min(100, score))

    if score <= 25:
        label = "AŞIRI KORKU 🥶"
    elif score <= 45:
        label = "KORKU 😨"
    elif score <= 55:
        label = "NÖTR 😐"
    elif score <= 75:
        label = "AÇGÖZLÜLÜK 😏"
    else:
        label = "AŞIRI AÇGÖZLÜLÜK 🤑"

    summary_text = "Piyasa Faktörleri: " + ", ".join(reasons) if reasons else "Endeks bileşenlerinde belirgin bir değişim yok."
    return FearGreedResult(score=score, label=label, summary=summary_text)

if __name__ == "__main__":
    res = calculate_fear_greed()
    print(f"Skor: {res.score}")
    print(f"Durum: {res.label}")
    print(f"Özet: {res.summary}")
