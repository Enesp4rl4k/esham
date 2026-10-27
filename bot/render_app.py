import os
import threading
import time

from flask import Flask, jsonify, request

import esham.main as bot_main
from esham.config import settings
from esham.newsletter import SubscriberStore
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
        "newsletter": {
            "subscribers": _safe_subscriber_count(),
            "smtp_configured": settings.smtp_enabled,
        },
    }
    return jsonify(body), 503 if stale else 200


def _safe_subscriber_count() -> int:
    """Abone sayısını sayar; depo okunamazsa 0 (health'i asla düşürmesin)."""
    try:
        return SubscriberStore().count()
    except Exception:  # noqa: BLE001 — sağlık ucunda asla çökmemeli
        return 0


@app.after_request
def _add_cors(resp):
    """Statik site (esham.pages.dev) farklı origin'den istek atar — CORS başlıkları.

    Form `application/x-www-form-urlencoded` ile gönderildiği için preflight
    (OPTIONS) tetiklenmez; yine de OPTIONS yanıtlanır ve gövde okunabilsin diye
    `Access-Control-Allow-Origin` eklenir.
    """
    resp.headers.setdefault("Access-Control-Allow-Origin", "*")
    resp.headers.setdefault("Access-Control-Allow-Headers", "Content-Type")
    resp.headers.setdefault("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
    return resp


@app.route("/subscribe", methods=["POST", "OPTIONS"])
def subscribe():
    """Bülten aboneliği — web formunun POST ettiği uç nokta.

    JSON veya URL-encoded gövde kabul eder; e-posta doğrular, tekrarı engeller,
    abone tavanını uygular. Her durumda insan-okunur mesaj döner (formda gösterilir).
    """
    if request.method == "OPTIONS":
        return ("", 204)
    data = request.get_json(silent=True) or request.form or {}
    email = str(data.get("email", "")).strip()
    ok, message = SubscriberStore().add(email)
    return jsonify({"ok": ok, "message": message}), (200 if ok else 400)


@app.route("/unsubscribe", methods=["GET", "POST"])
def unsubscribe():
    """İmzalı çıkış bağlantısı — token doğrulanmadan liste değiştirilemez."""
    data = request.args if request.method == "GET" else (request.form or request.args)
    email = str(data.get("email", "")).strip()
    token = str(data.get("token", "")).strip()
    store = SubscriberStore()
    if not email or not store.verify_token(email, token):
        return jsonify({"ok": False, "message": "Geçersiz veya eksik çıkış bağlantısı."}), 400
    removed = store.remove(email)
    return jsonify(
        {
            "ok": True,
            "message": "Aboneliğiniz sonlandırıldı." if removed else "Zaten listede değilsiniz.",
        }
    )


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
