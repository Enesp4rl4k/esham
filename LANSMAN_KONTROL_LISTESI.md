# Esham — Lansman Kontrol Listesi (21 Kasım 2026)

Durum, canlı siteden (`esham.pages.dev`) ve depodan ölçüldü. ✅ tamam · 🟡 sizde · ❌ eksik/risk.

## 1. Teknik hazırlık
| | Madde | Not |
| --- | --- | --- |
| ✅ | Yayın akışı çalışıyor, sağlık kontrolü 5/5 | `health.yml` günlük; hafta sonu yayın yok (cron böyle) |
| ✅ | Hisse (110), fon (200), sektör, tarama, karşılaştırma sayfaları | Dosya bütçesi ~7.700 / 20.000 |
| ✅ | KAP birincil kaynak (25 hisse), Yahoo yedek | İlk GitHub çalıştırması izlenmeli (bkz. 4) |
| ✅ | robots.txt, sitemap (2.200+ URL), canonical, JSON-LD | `/_next/` engeli kaldırıldı |
| ✅ | Başlık/açıklama sınırları, OG varsayılan görseli | Hisse başına OG kartı sonra |
| ✅ | Açık/koyu tema, mobil menü, erişilebilirlik tabanı | |
| ✅ | Güvenlik başlıkları (`_headers`): X-Frame-Options, Permissions-Policy | HSTS Cloudflare'de |
| ✅ | 404 sayfası | |
| ❌ | Hata izleme (Sentry vb.) | İstemci hatalarını görmüyoruz; ilk ayda konsol taraması yeterli |

## 2. Yasal ve güven (bu PR ile eklendi)
| | Madde | Not |
| --- | --- | --- |
| ✅ | Yatırım tavsiyesi değildir uyarısı | Sayfalarda + Kullanım Şartları |
| ✅ | Gizlilik ve KVKK aydınlatma metni, Kullanım Şartları, İletişim | **Hukuki gözden geçirme önerilir** |
| 🟡 | **Veri sorumlusu bilgisi** | KVKK metnine ünvan/adres/e-posta eklenmeli; şu an yalnızca X hesabı var |
| 🟡 | **TEFAS verisi izni** | TEFAS "API paylaşımı yapılmamaktadır" diyor; Takasbank/hukuk görüşü |
| 🟡 | SPK uyumu | Yatırım danışmanlığı sayılmadığını bir hukukçuya teyit ettirin |
| ✅ | Çerezsiz ölçüm planı | Cloudflare Web Analytics (çerez bandı gerekmez) |

## 3. Bülten (lansmanın en zayıf halkası)
| | Madde | Not |
| --- | --- | --- |
| ❌ | **E-posta abonelik altyapısı yok** | `ESHAM_BOT_URL` ve SMTP secret'ları tanımlı değil; form şu an üçüncü tarafın Formspree adresine gidiyor (sahibi belirsiz). Bu hali KVKK ve güven açısından riskli |
| 🟡 | Seçim | (a) Bot'u Render'a kurup `ESHAM_BOT_URL` + `ESHAM_SMTP_*` secret'larını girmek, ya da (b) Buttondown/MailerLite gibi bir hizmete bağlamak |
| 🟡 | Formspree adresinin sahibi siz misiniz? | Değilse formu lansmandan önce kapatın |

## 4. Alan adı ve ölçüm (sizde)
1. Alan adını alın (ör. esham.com.tr), Cloudflare Pages → Custom domains'e ekleyin.
2. GitHub → Settings → Variables: `SITE_URL` (https://alanadi), `CF_ANALYTICS_TOKEN`, `GSC_VERIFICATION`. Ayrıca bot için `ESHAM_SITE_URL` (workflow'da sabit `esham.pages.dev`, geçişte güncellenecek).
3. Eski adresten yeni adrese 301 (Pages yönlendirme/redirect kuralı) ve Search Console'da **Adres değişikliği**.
4. Search Console'a sitemap gönderin; Core Web Vitals izleyin.
5. Bir hafta içi 18:45 (TR) çalıştırmasında KAP erişiminin GitHub sunucularından çalıştığını doğrulayın (workflow günlüğünde "KAP verisi alınamadı" uyarısı yoksa tamam).

## 5. Lansman günü
- [ ] Ana sayfa, bir hisse, bir fon, tarayıcı, karşılaştırma: mobil + masaüstü elle gezin
- [ ] Bülten formunu uçtan uca deneyin (abone ol → onay → çıkış)
- [ ] `https://alanadi/robots.txt` ve `sitemap.xml` alan adını gösteriyor mu
- [ ] X hesabından duyuru; Telegram kanalı (varsa)
- [ ] İlk hafta: Search Console kapsama raporu, 404'ler, Actions kırmızı çalıştırmaları

## 6. Bilinen sınırlar (lansmanda dürüstçe söylenmeli)
- Fonlarda portföy dağılımı yok; yalnızca ilk 200 fon.
- KAP kapsamı bankasız evrenin bir kısmı; bankalar/sigortalar Yahoo'dan.
- Endeks (BIST 30/100) sayfaları yok.
- Hafta sonu otomatik yayın yok.
