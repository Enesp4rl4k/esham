# Render'da Esham Bot Kurulumu ve Sorun Giderme

## Mevcut Durum Analizi

Bot Render'da çalışıyor **AMA**:
- ❌ X'te (Twitter) tweet yok
- ❌ Web sitesi güncellenmiyor  
- ❌ İçerik üretilmiyor

## Sorunun Nedenleri ve Çözümleri

### 1. Render Environment Variables Eksik

Render Dashboard → Your Service → Environment → Environment Variables

**Şu anda eksik olabilecek değişkenler:**

```bash
# === ZORUNLU: AI ===
GROQ_API_KEY=gsk_xxxxxxxxxxxxx
# veya
GEMINI_API_KEY=AIzaSyxxxxxxxxx

# === ZORUNLU: Twitter (paylaşım için) ===
TWITTER_API_KEY=ZbwQbXNxRIu8B9bOTWBrC79V7
TWITTER_API_SECRET=yBlVZoiat0wtgMNyfH8kEiEHpLmOsgcH2yYQffe65FT0RV6vWK
TWITTER_ACCESS_TOKEN=2073728398958968832-l9RfEgUCI5YGqE8Kgc0JTEj81QtgOI
TWITTER_ACCESS_SECRET=HGleUUYtfJEgPDcnc91NkVkhKcAqk5xu33L95wPKLtbw2

# === ZORUNLU: Git Push (web güncellemesi için) ===
GIT_AUTO_PUSH=true
GIT_PUSH_TOKEN=ghp_xxxxxxxxxxxxxxxx  # GitHub Personal Access Token
GIT_REPO_URL=https://github.com/Enesp4rl4k/esham.git

# === Opsiyonel ===
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
UNSPLASH_ACCESS_KEY=EwDeC1ibKQ6f3OKVs5GZTKiUnxukAZP2zXBvbC0epva2ti73JKyNbEVm
ESHAM_SITE_URL=https://esham.pages.dev
ESHAM_KAP_MIN_IMPORTANCE=1
```

### 2. GitHub Personal Access Token Oluşturma

Bot'un ürettiği içeriği git'e push edebilmesi için:

1. https://github.com/settings/tokens adresine git
2. "Generate new token" → "Generate new token (classic)"
3. Note: `render-esham-bot`
4. Expiration: `No expiration` veya `1 year`
5. Scopes:
   - ✅ `repo` (tüm repo erişimi)
   - ✅ `workflow` (GitHub Actions tetikleme)
6. "Generate token" tıkla
7. Token'ı kopyala (ghp_xxxxx...)
8. Render → Environment → `GIT_PUSH_TOKEN` = token'ı yapıştır

### 3. Render Service Restart

Environment değişkenlerini ekledikten sonra:
- Render Dashboard → Your Service → Manual Deploy → "Deploy latest commit"
- Veya Settings → "Restart Service"

### 4. Kontrol Noktaları

#### A) Render Logs
```
Render Dashboard → Your Service → Logs
```
Şunları ara:
- ✅ `"Esham orkestratörü başladı"`
- ✅ `"LLM: Groq primary"`
- ✅ `"Tweet gönderildi"`
- ✅ `"Git push başarılı"`
- ❌ `"[DRY-RUN][Twitter]"` → Twitter anahtarları yok
- ❌ `"LLM: API key yok"` → Groq/Gemini yok
- ❌ `"Git push atlandı"` → GIT_AUTO_PUSH yok

#### B) Health Endpoint
```bash
curl https://your-render-service.onrender.com/health
```

Yanıt:
```json
{
  "status": "ok",  // veya "stale"
  "paused": false,
  "heartbeat_age_seconds": 25.3,  // 300'den küçük olmalı
  "daily_post_count": 5,
  "seen_disclosures_tracked": 127,
  "failing_jobs": {}  // boş olmalı
}
```

**Sorun işaretleri:**
- `"status": "stale"` → Bot takılmış, restart gerek
- `"paused": true` → Bot durdurulmuş, `ESHAM_PAUSED=false` yap
- `heartbeat_age_seconds > 300` → Bot donmuş
- `failing_jobs` dolu → Logları incele

#### C) Web Sitesi
```bash
# Son raporlar var mı?
ls -la web/content/reports/ | tail -20

# En son commit ne zaman?
git log --oneline -10
```

Güncel rapor yoksa:
- Git push çalışmıyor → `GIT_AUTO_PUSH` ve `GIT_PUSH_TOKEN` kontrol et
- Bot içerik üretmiyor → Logları incele

### 5. Twitter Developer Portal Kontrolü

https://developer.twitter.com/en/portal/dashboard

**Kontroller:**
- ✅ App Access: Read and Write
- ✅ App Type: Free veya Basic ($100/ay)
- ✅ Access Token: Active
- ✅ Rate Limits: Aşılmamış (günde 50 tweet Free tier'da)

**App Permissions düşükse:**
1. Settings → User authentication settings → Edit
2. App permissions: `Read and Write` seç
3. Save
4. Keys and tokens → Regenerate Access Token and Secret
5. Yeni token'ları Render'a ekle
6. Render'ı restart et

### 6. Cloudflare Pages Webhook (Web Güncellemesi)

Render bot'u içerik üretip git'e pushlıyor, **ama** Cloudflare Pages otomatik build tetiklenmiyor olabilir.

**Çözüm 1: GitHub Actions'tan Deploy**

`.github/workflows/esham-schedule.yml` zaten commit sonrası Cloudflare deploy yapıyor:
```yaml
- name: Web Sitesini Derle ve Cloudflare'e Gönder
  working-directory: web
  env:
    CLOUDFLARE_ACCOUNT_ID: ${{ secrets.CLOUDFLARE_ACCOUNT_ID }}
    CLOUDFLARE_API_TOKEN: ${{ secrets.CLOUDFLARE_API_TOKEN }}
  run: |
    npm ci
    npm run build
    npx wrangler pages deploy out --project-name esham --commit-dirty=true
```

Bu çalışıyorsa, Render'dan gelen push'lar GitHub Actions'ı tetikleyecek ve web otomatik güncellenecek.

**Çözüm 2: Cloudflare Pages Auto-Deploy**

Cloudflare Dashboard → Pages → esham → Settings → Builds & deployments:
- ✅ Branch: `master`
- ✅ Build command: `npm run build`
- ✅ Build output directory: `out`
- ✅ Production branch: `master`

Her push otomatik build tetikler.

### 7. Test Senaryosu (Elle)

Render service'e SSH erişimi yoksa, lokal test:

```bash
# .env dosyasını Render'daki ile aynı yap
cd bot

# Tek haber üret ve yayınla
python -m esham.main news-stream --once --max-publish 1

# Logları incele:
# - "Tweet gönderildi" → Twitter çalışıyor ✅
# - "Git push başarılı" → Web güncellemesi çalışıyor ✅
# - "Rapor yayınlandı" → İçerik üretimi çalışıyor ✅
```

### 8. Yaygın Hatalar

#### "ModuleNotFoundError: No module named 'PIL'"
```bash
# requirements.txt güncellendi, Render'da redeploy yap
```

#### "Twitter API 403 Forbidden"
```bash
# App permissions yanlış: Read and Write olmalı
# Token'ları regenerate et
```

#### "Git push başarısız: authentication failed"
```bash
# GIT_PUSH_TOKEN yanlış veya expired
# Yeni token oluştur ve Render'a ekle
```

#### "Rate limit exceeded (429)"
```bash
# Groq: dakikada 30, günde 14.400 istek
# Twitter Free: günde 50 tweet
# ESHAM_NEWS_PUBLISH_INTERVAL'ı yükselt (90 → 180 saniye)
```

#### "Cloudflare Pages build hatası"
```bash
# GitHub Secrets kontrol et:
# - CLOUDFLARE_ACCOUNT_ID
# - CLOUDFLARE_API_TOKEN
```

---

## Hızlı Kontrol Listesi

Render'da bot çalışıyor ama paylaşım/içerik yok:

- [ ] `GROQ_API_KEY` veya `GEMINI_API_KEY` Render'da var mı?
- [ ] `TWITTER_API_KEY`, `TWITTER_API_SECRET`, `TWITTER_ACCESS_TOKEN`, `TWITTER_ACCESS_SECRET` var mı?
- [ ] Twitter App'in Read and Write izni var mı?
- [ ] `GIT_AUTO_PUSH=true` Render'da set edildi mi?
- [ ] `GIT_PUSH_TOKEN` valid ve `repo` scope'u var mı?
- [ ] `GIT_REPO_URL` doğru mu? (https://github.com/Enesp4rl4k/esham.git)
- [ ] Render loglarında `"Esham orkestratörü başladı"` yazıyor mu?
- [ ] Health endpoint `/health` status: "ok" dönüyor mu?
- [ ] GitHub'da son commit bottan mı geldi?
- [ ] Cloudflare Pages son build ne zaman?

---

## Acil Durum: Manuel Tweet

Bot çalışmıyorsa manuel tweet için:

```bash
cd bot
python -c "
from esham.publishing.social import SocialPublisher
from esham.sources.bist import BistSource

bist = BistSource().market_summary()
msg = f'BIST {bist.index}: {bist.price} ({bist.change})'
SocialPublisher().post_tweet(msg)
print('Tweet gönderildi:', msg)
"
```

Bu çalışırsa Twitter anahtarları doğru demektir.
