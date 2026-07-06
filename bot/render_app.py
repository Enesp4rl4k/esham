import os
import threading
import time

from flask import Flask, jsonify

import esham.main as bot_main
from esham.config import settings
from esham.state import get_state

app = Flask(__name__)

# Bir uptime pinger'ın (UptimeRobot vb.) düzenli ziyaret edeceği eşik: heartbeat
# bundan eskiyse süreç muhtemelen takılmış/çökmüş demektir.
STALE_HEARTBEAT_SECONDS = 300


@app.route("/")
def home():
    return "Bot is running!"


@app.route("/health")
def health():
    """Dış izleme (UptimeRobot vb.) veya elle kontrol için JSON durum özeti.

    `heartbeat_age_seconds` düzenli aralıklarla (scheduler tick'i kadar sık)
    güncellenmeli; büyükse süreç muhtemelen takılmış demektir — dıştan bir
    izleme aracı bunu 5xx'e çevirip alarm üretebilir.
    """
    snap = get_state().snapshot()
    heartbeat = snap.get("last_heartbeat")
    age = (time.time() - heartbeat) if heartbeat else None
    stale = age is None or age > STALE_HEARTBEAT_SECONDS

    failing_jobs = {
        name: info
        for name, info in snap.get("jobs", {}).items()
        if info.get("consecutive_failures", 0) > 0
    }

    body = {
        "status": "stale" if stale else "ok",
        "paused": settings.paused,
        "heartbeat_age_seconds": round(age, 1) if age is not None else None,
        "daily_post_count": snap.get("daily_post_count"),
        "max_posts_per_day": settings.max_posts_per_day,
        "seen_disclosures_tracked": snap.get("seen_count"),
        "margin_prev_pct": snap.get("margin_prev_pct"),
        "failing_jobs": failing_jobs,
    }
    return jsonify(body), 503 if stale else 200


def run_bot():
    print("Starting esham bot in background...")
    # Simüle edilmiş bir argüman objesi oluşturuyoruz çünkü asıl bot argparse kullanıyor
    class DummyArgs:
        command = "run"
        scan_interval = 300
        publish_interval = 90
        margin_interval = 1800
        func = bot_main._cmd_run

    args = DummyArgs()
    # Botu çalıştır
    bot_main._cmd_run(args)


if __name__ == "__main__":
    # Botu arka planda ayrı bir thread (iş parçacığı) olarak başlat
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()

    # Render'ın beklediği port numarasını al (varsayılan 10000)
    port = int(os.environ.get("PORT", 10000))
    # Sahte web sunucusunu başlat
    app.run(host="0.0.0.0", port=port)
