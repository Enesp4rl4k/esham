# Esham Piyasa Botu - Kurulum ve Çalıştırma Rehberi

## 🚨 Sistem Neden Çalışmıyor?

Sisteminiz çalışıyor ancak içerik üretemiyor. Sebebi: **API anahtarları yapılandırılmamış**.

---

## ✅ Hızlı Başlangıç (5 Dakika)

### 1. API Anahtarlarını Alın

#### A) Groq API (ÖNERİLEN - Tamamen Ücretsiz)
- https://console.groq.com adresine gidin
- Ücretsiz hesap oluşturun (kredi kartı gerekmez)
- API Keys bölümünden yeni anahtar oluşturun
- **Dakikada 30 istek, günde 14.400 istek ücretsiz**

#### B) Gemini API (Alternatif)
- https://aistudio.google.com/app/apikey adresine gidin
- Google hesabınızla giriş yapın
- "Create API Key" butonuna tıklayın
- **Günde 1.500 istek ücretsiz**

#### C) Twitter API (Opsiyonel - Paylaşım için)
- https://developer.twitter.com/en/portal/dashboard adresine gidin
- Geliştirici hesabı oluşturun
- Free tier yeterli
- API Key, API Secret, Access Token ve Access Secret'ı kopyalayın

### 2. `.env` Dosyasını Oluşturun

```bash
cd bot
cp .env.example .env
```

Ardından `.env` dosyasını düzenleyin:

```env
# === ZORUNLU: AI Analiz için ===
GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# === OPSIYONEL: Sosyal Medya Paylaşımı ===
TWITTER_API_KEY=your_twitter_api_key
TWITTER_API_SECRET=your_twitter_api_secret
TWITTER_ACCESS_TOKEN=your_twitter_access_token
TWITTER_ACCESS_SECRET=your_twitter_access_secret

# === OPSIYONEL: Telegram Bildirimleri ===
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id

# === Site Yapılandırması ===
ESHAM_SITE_URL=https://esham.pages.dev
ESHAM_BRAND_ACCENT=Es
ESHAM_BRAND_REST=ham
```

**ÖNEMLİ:** Sadece `GROQ_API_KEY` bile sistemi çalıştırmak için yeterli! Twitter anahtarları olmadan da raporlar üretilecek, sadece paylaşılmayacak.

### 3. Bağımlılıkları Kurun

```bash
cd bot
pip install -r requirements.txt
```

### 4. İlk Testi Yapın

```bash
# Sabah raporunu üret (sosyal medya paylaşımı olmadan)
python -m esham.main morning-report --no-social

# Sonuç: web/content/reports/ klasöründe yeni bir JSON dosyası göreceksiniz
```

---

## 📊 Sistemin Nasıl Çalıştığını Anlayın

### Veri Akışı

```
KAP Kaynakları → Bot (AI Analiz) → JSON Raporlar → Web Sitesi
     ↓              ↓                   ↓
Global Makro    Groq/Gemini        /content/reports/
     ↓              ↓                   ↓
  Sektör        Markdown           Cloudflare Pages
```

### Ana Komutlar

```bash
# Haber akışını kontrol et (tek tur, max 3 haber)
python -m esham.main news-stream --once --max-publish 3

# Sabah bülteni üret ve paylaş
python -m esham.main morning-report

# Kapanış raporu
python -m esham.main closing

# VİOP teminat raporu
python -m esham.main viop --publish

# Küresel makro raporu
python -m esham.main global-report

# Haftalık sektör rotasyonu
python -m esham.main sector

# Tam otomasyon (uzun-ömürlü süreç, VPS için)
python -m esham.main run
```

---

## 🤖 GitHub Actions ile Otomasyona Geçiş

Lokal testler başarılıysa, GitHub Actions ile otomatik yayın kurabilirsiniz:

### 1. GitHub Secrets Ekleyin

Repository → Settings → Secrets and variables → Actions → New repository secret

Eklenecek secret'lar:
- `GROQ_API_KEY` veya `GEMINI_API_KEY`
- `TWITTER_API_KEY` (opsiyonel)
- `TWITTER_API_SECRET` (opsiyonel)
- `TWITTER_ACCESS_TOKEN` (opsiyonel)
- `TWITTER_ACCESS_SECRET` (opsiyonel)
- `TELEGRAM_BOT_TOKEN` (opsiyonel)
- `TELEGRAM_CHAT_ID` (opsiyonel)
- `CLOUDFLARE_ACCOUNT_ID` (web deploy için)
- `CLOUDFLARE_API_TOKEN` (web deploy için)

### 2. Workflow'u Etkinleştirin

`.github/workflows/esham-schedule.yml` zaten yapılandırılmış. Schedule:

- **08:30 TR** - Günlük sabah bülteni
- **08:45 TR** - Küresel makro raporu
- **09:30 TR** - VİOP açılış
- **10:00 TR** - BIST açılış
- **13:00 TR** - Öğle ısı haritası
- **18:15 TR** - Kapanış bülteni
- **18:30 TR** - Akşam ısı haritası
- **Her 15 dk** - KAP/haber tarama (seans içi)

### 3. Manuel Tetikleme (Test için)

GitHub → Actions → "Esham Yayın Döngüsü" → Run workflow → Komut seçin → Run

---

## 🔍 Sorun Giderme

### "Paylaşım yok, içerikler nerede?"

**Kontrol edin:**

```bash
# 1. API anahtarı var mı?
cd bot
python -c "from esham.config import settings; print('Groq:', bool(settings.groq_api_key), 'Gemini:', bool(settings.gemini_api_key))"

# 2. Raporlar üretildi mi?
ls -la ../web/content/reports/

# 3. Logları inceleyin
python -m esham.main news-stream --once --max-publish 1
```

### "Python bulunamadı" Hatası

Windows'ta:
```powershell
py -m esham.main morning-report --no-social
```

Linux/Mac'te:
```bash
python3 -m esham.main morning-report --no-social
```

### "Gemini/Groq API Hatası"

- API anahtarının doğru kopyalandığından emin olun (başında/sonunda boşluk yok)
- Groq: https://console.groq.com/keys - anahtarı yeniden oluşturun
- Gemini: https://aistudio.google.com/app/apikey - yeni anahtar alın
- Kotanızı kontrol edin

### "Twitter Paylaşım Hatası"

Twitter anahtarları olmadan da sistem çalışır! Raporlar üretilir, sadece paylaşılmaz.

Paylaşım istiyorsanız:
1. https://developer.twitter.com/en/portal/dashboard
2. Elevated Access başvurusu yapın (ücretsiz)
3. Read and Write izinleri ekleyin
4. Anahtarları yenileyin

---

## 📈 İleri Seviye: VPS'te Sürekli Çalıştırma

GitHub Actions yerine sürekli çalışan bir bot istiyorsanız:

```bash
# tmux ile arka planda çalıştır
tmux new -s esham
cd bot
python -m esham.main run

# tmux'tan çıkmak için: Ctrl+B, sonra D
# tekrar bağlanmak için: tmux attach -t esham
```

Veya systemd servisi:

```ini
# /etc/systemd/system/esham.service
[Unit]
Description=Esham Piyasa Botu
After=network.target

[Service]
Type=simple
User=yourusername
WorkingDirectory=/path/to/PiyasaBotu_Proje/bot
ExecStart=/usr/bin/python3 -m esham.main run
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable esham
sudo systemctl start esham
sudo systemctl status esham
```

---

## 📝 Notlar

1. **İlk çalıştırmada:** Bot son ~50 KAP bildirimini tarayacak. Normal.

2. **Rate limit:** Groq günde 14.400 istek veriyor. Ortalama 50-100 haber/gün için fazlasıyla yeterli.

3. **Maliyet:** Groq ve Gemini free tier'ları bu proje için yeterli. Ödeme yapmadan aylarca çalıştırabilirsiniz.

4. **Filtreleme:** `ESHAM_KAP_MIN_IMPORTANCE=3` ile önem eşiğini ayarlayabilirsiniz. Düşürürseniz daha çok haber, yükseltirseniz daha az haber yayınlanır.

5. **Acil durdurma:** `.env` dosyasına `ESHAM_PAUSED=true` eklerseniz tüm yayın durdurulur.

---

## 🎯 Hızlı Kontrol Listesi

- [ ] Groq veya Gemini API anahtarı aldım
- [ ] `bot/.env` dosyasını oluşturup anahtarı ekledim
- [ ] `pip install -r requirements.txt` çalıştırdım
- [ ] `python -m esham.main morning-report --no-social` ile test ettim
- [ ] `web/content/reports/` klasöründe yeni rapor gördüm
- [ ] (Opsiyonel) Twitter anahtarlarını ekledim
- [ ] (Opsiyonel) GitHub Secrets'ı yapılandırdım
- [ ] (Opsiyonel) GitHub Actions workflow'unu tetikledim

---

## ❓ Hala Sorun mu Var?

1. Logları paylaşın: `python -m esham.main morning-report --no-social 2>&1 | tee log.txt`
2. API anahtarını doğrulayın
3. Python versiyonunu kontrol edin: `python --version` (3.10+ gerekli)
4. Bağımlılıkları yeniden kurun: `pip install -r requirements.txt --force-reinstall`

**En yaygın sorun:** `.env` dosyası yok veya API anahtarı hatalı. Önce bunu kontrol edin!
