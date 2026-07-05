import os
import threading
from flask import Flask
import esham.main as bot_main
import argparse

app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running!"

def run_bot():
    print("Starting esham bot in background...")
    # Simüle edilmiş bir argüman objesi oluşturuyoruz çünkü asıl bot argparse kullanıyor
    class DummyArgs:
        command = 'run'
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
