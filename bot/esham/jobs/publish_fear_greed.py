"""Fear & Greed endeksini hesaplayıp sosyal medyada yayınlar."""
from __future__ import annotations

from pathlib import Path
from ..ai.fear_greed import calculate_fear_greed
from ..publishing.cards import CardGenerator, CardSpec
from ..publishing.social import SocialPublisher
from ..config import get_logger, settings

log = get_logger(__name__)

def run_fear_greed_report() -> None:
    res = calculate_fear_greed()
    
    # Kicker ve Başlık
    kicker = "Korku ve Açgözlülük Endeksi"
    headline = f"BIST & Küresel Piyasa Durumu: {res.label}"
    
    body = f"## Güncel Skor: {res.score}/100\n\n{res.summary}\n"
    
    # Kart şablonu olarak 'bist' kullanabiliriz (sol üst kicker, ortada büyük metin)
    spec = CardSpec(
        category="gundem",
        kicker=kicker,
        headline=f"Skor: {res.score} / 100\nDurum: {res.label}",
        ticker="ENDEKS",
        template="gundem",
    )
    
    cards = CardGenerator()
    try:
        img_path = cards.render(spec)
    except Exception as exc:
        log.warning("Kart üretilemedi: %s", exc)
        img_path = None
        
    tweet_text = f"📊 Korku ve Açgözlülük Endeksi güncellendi!\n\nSkor: {res.score}/100\nDurum: {res.label}\n\n{res.summary}\n#Borsa #BIST100 #FearGreed"
    
    log.info("Yayınlanıyor: Fear & Greed %s", res.score)
    SocialPublisher().broadcast(tweet_text, image_path=img_path)

if __name__ == "__main__":
    run_fear_greed_report()
