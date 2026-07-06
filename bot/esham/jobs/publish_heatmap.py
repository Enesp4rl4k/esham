import tempfile
from pathlib import Path

from ..config import get_logger, settings
from ..publishing.social import SocialPublisher
from ..sources.heatmap import generate_heatmap

log = get_logger(__name__)

def run_heatmap(publish_social: bool = True) -> bool:
    """Isı haritasını oluşturur ve Twitter/X'te yayınlar."""
    log.info("=== BIST30 Isı Haritası (Heatmap) başlatılıyor ===")
    
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tf:
        out_path = Path(tf.name)
        
    try:
        success = generate_heatmap(out_path)
        if not success:
            log.warning("Isı haritası üretilemedi, iptal.")
            return False

        if publish_social:
            text = (
                "🔥 Güncel BIST30 Isı Haritası\n\n"
                "Para nereye akıyor? Kutucuk boyutu işlem hacmini, renkler ise güncel değişimi gösteriyor.\n\n"
                "#Borsa #BIST100 #Hisse #Piyasa"
            )
            SocialPublisher().broadcast(text, image_path=out_path)
            
        log.info("=== Isı Haritası (Heatmap) başarıyla yayınlandı ===")
        return True
    finally:
        if out_path.exists():
            try:
                out_path.unlink()
            except OSError:
                pass
