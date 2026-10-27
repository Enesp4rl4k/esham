# 🚀 Deploy — Cloudflare Pages (web) + Render (bot) + GitHub Actions

Tek bakışta canlıya alma sırası. Ayrıntılı sorun giderme:
`RENDER_KURULUM.md` (bot), `KURULUM_REHBERI.md` (yerel + Actions).

```
┌──────────────────────┐  commit   ┌────────────────────────┐
│ GitHub Actions       │ ────────▶ │ GitHub repo (master)   │
│ (cron → py -m esham  │           │  web/content/*.json    │
│  main <komut>)       │           └───────────┬────────────┘
└──────────┬───────────┘                       │ commit tetikleri / elle build
           │ npm build + wrangler              ▼
           ▼                          ┌────────────────────────┐
┌──────────────────────┐              │ Cloudflare Pages       │
│ Render (bot, uzun    │  git push    │  esham.pages.dev       │
│ süreç: run + /health)│ ───────────▶ │  (output: export)      │
└──────────────────────┘  içerik      └────────────────────────┘
```

## 0. ⚠️ Güvenlik rotasyonu (önce bunu yap)

`RENDER_KURULUM.md` içinde geçmişte **gerçek Twitter API ve Unsplash anahtarları**
düz metin commit edilmişti. Depo herkese açıksa bu anahtarlar görünür durumda:

1. Twitter/X anahtarlarını **regenerate et** (developer.x.com → App → Keys).
2. Unsplash anahtarını **regenerate et**.
3. Eski değerleri hiçbir yerde kullanma; dosyalara asla gerçek anahtar yazma.

## 1. GitHub Secrets (Settings → Secrets and variables → Actions)

| Secret | Zorunlu | Ne işe yarar |
| --- | --- | --- |
| `GROQ_API_KEY` / `GEMINI_API_KEY` / `DEEPSEEK_API_KEY` | ✅ (en az biri) | AI analiz + tweet. Yoksa şablon üretimi (zarif bozulma) |
| `CLOUDFLARE_ACCOUNT_ID`, `CLOUDFLARE_API_TOKEN` | ✅ | `wrangler pages deploy out` — yoksa deploy **sessizce atlanır** |
| `ESHAM_BOT_URL` | ✅ (bülten için) | Web abone formunun `POST /subscribe` yaptığı bot adresi, ör. `https://esham-bot.onrender.com` |
| `ESHAM_SMTP_HOST/PORT/USER/PASSWORD/SSL`, `ESHAM_EMAIL_FROM` | – | E-posta gönderimi. Yoksa newsletter **dry-run** olur |
| `ESHAM_UNSUBSCRIBE_SECRET` | – | Abonelikten çıkış imzası (rastgele uzun değer seç) |
| `GIT_PUSH_TOKEN` | Render tarafı | Bot'un içerik commit'lemesi (Render için) |
| `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` | – | Paylaşım/operasyon uyarıları |
| `ESHAM_TAKASBANK_VIOP_URL`, `UNSPLASH_ACCESS_KEY` | – | VİOP teminat verisi, haber fotoğrafı |

> Cloudflare token'ı `wrangler` kullanır: Dashboard → API Tokens →
> "Edit Cloudflare Workers" şablonu yerine **"Cloudflare Pages: Edit"** izni veren
> token oluştur; Account ID'yi dashboard sağ alt köşeden al.

## 2. Cloudflare Pages (web)

**Yol A — GitHub Actions ile (önerilen, zaten repoda):**
`.github/workflows/esham-schedule.yml` her publish job'ının sonunda
`npm ci && npm run build && npx wrangler pages deploy out --project-name esham`
çalıştırır. Secrets yoksa build yine yapılır, deploy atlanır.

- İlk kurulum: Cloudflare Dashboard → Workers & Pages → Create → Pages →
  **Connect to Git** yerine **Direct Upload** kullanacaksan `project-name` `esham`
  olmalı (workflow'daki `--project-name esham` ile aynı).
- `NEXT_PUBLIC_ESHAM_BOT_URL` build ortamı olarak workflow'da tanımlıdır
  (`ESHAM_BOT_URL` secret'ından okunur) — bülten formu buna yazar.

**Yol B — elle:**
```bash
cd web && npm ci && npm run build     # çıktı: web/out
npx wrangler pages deploy out --project-name esham
```

### Domain bağlama
Cloudflare Dashboard → your-domain → DNS → `CNAME esham CNAME esham.pages.dev`
veya Pages → Custom domains → `esham.com.tr` ekle. Sonra `ESHAM_SITE_URL` ve
sitemap'teki `BASE_URL` (`web/src/app/sitemap.ts`) gerçek domain ile güncellenmeli.

## 3. Render (bot — uzun-ömürlü süreç)

1. Render → New → Web Service → repo seç.
2. Ayarlar:
   - **Root Directory:** `bot`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `python render_app.py`
3. Environment Variables → `RENDER_KURULUM.md`'deki liste (placeholder'ları
   gerçek değerlerle değiştir; sır değerleri yalnızca burada).
4. **Kalıcı disk (bülten aboneleri için):** Render → Disks → Add Disk
   (ör. 1 GB) → mount `/data` → `ESHAM_SUBSCRIBER_FILE=/data/subscribers.json`
   ve `ESHAM_STATE_FILE=/data/esham_state.json`. Disk yoksa restart'ta
   seen-set/abone listesi sıfırlanır (fonksiyonel ama aboneler kaybolur).
5. Kontrol: `curl https://<servis>.onrender.com/health` → `status: ok`,
   `newsletter.subscribers` sayısı görünmeli.
6. Render'daki `GIT_AUTO_PUSH=true` + `GIT_PUSH_TOKEN` ile bot üretilen
   içeriği commit'ler; Cloudflare webhook'u (veya Actions build) siteyi
   yeniler.

## 4. Doğrulama checklist'i

```bash
# 1) Eval kapısı yeşil mi (CI ile aynı komut)
cd bot && py -m esham.main evals            # → 23/23 BAŞARILI

# 2) Web derleniyor mu
cd web && npm run build                      # → 1599 statik sayfa

# 3) Bot uç noktaları
curl https://<servis>.onrender.com/health
curl -X POST https://<servis>.onrender.com/subscribe -d "email=test@ornek.com"

# 4) Bülten dry-run (SMTP yokken bile üretim çalışır)
cd bot && py -m esham.main newsletter --dry-run --test-to test@ornek.com

# 5) Zamanlanmış işler
py -m esham.main run      # VPS/uzun süreç: iş listesi loglanır
# Actions: repo → Actions → "Esham Yayın Döngüsü" → workflow_dispatch
```

## 5. Sık yapılan hatalar

| Belirti | Neden | Çözüm |
| --- | --- | --- |
| Actions deploy "geçti" ama site eski | `CLOUDFLARE_*` secret yok → deploy `continue-on-error` ile atlandı | Secret'ları ekle, logda "deploy atlanıyor" çıktısını kontrol et |
| Bülten hiç gitmiyor | SMTP tanımlı değil | Logda `[DRY-RUN]` görürsün; `ESHAM_SMTP_*` ekle |
| Form "Bağlantı hatası" veriyor | `ESHAM_BOT_URL` yok/yanlış ya da Render uyuyor | Secret + servis URL'ini doğrula (ilk istekte uyku uyanır) |
| Aboneler restart'ta sıfırlanıyor | Kalıcı disk yok | Bölüm 3/4 — Render Disk bağla |
| Raporlar yayınlanmıyor | `ESHAM_PAUSED=true` veya guardrail | `/health` → `paused`; `ESHAM_GUARDRAILS=warn` |
