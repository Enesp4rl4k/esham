# Veri grafikleri (`/veri`)

Kamuya açık resmî istatistiklerden üretilen zaman serisi grafikleri. Her grafik bir sayfa (`/veri/<slug>`), veri tablosu,
CSV ve paylaşım görseli (PNG, 1600×900 ve 1080×1350) olarak yayımlanır. Metinler yalnız betimleyicidir: yorum, sıralama,
tahmin yoktur. Başka bir ürünün görsel kimliği kopyalanmamıştır; esham'ın kendi renkleri, yazı tipleri (Outfit + Inter) ve
kart dili kullanılmıştır.

## 1. İlk grafik: altı halka açık bankanın şube sayısı (TBB)

**Durum: GERÇEK veri.** 37 çeyrek, 3Ç 2017 – 3Ç 2026, her değer TBB'nin kendi çeyreklik raporundan.

| | |
|---|---|
| Kaynak | Türkiye Bankalar Birliği › İstatistiki Raporlar › Seçilmiş İstatistikler › **Banka, Çalışan ve Şube Bilgileri** (https://www.tbb.org.tr/istatistiki-raporlar/11237) |
| Dönem sayfası | `https://www.tbb.org.tr/istatistiki-raporlar/<yıl>-<mart\|haziran\|eylul\|aralik>-banka-calisan-ve-sube-bilgileri` |
| Dosya | Sayfadaki Excel eki (PDF ve Word ekleri de var); ör. `Banka Çalışan ve Şube Sayıları-Eylül 2026.xlsx` |
| Tablo | "Tablo 1 – … İtibarıyla Banka, Şube ve Çalışan Sayıları", sütun "Şube Sayısı*" |
| Tanım | Dipnot: "Yurtiçi ve yurtdışı şube sayıları toplamından oluşmaktadır." 37 dosyanın tamamında aynı |
| Kapsam | TBB üyesi mevduat bankaları ile kalkınma ve yatırım bankaları; katılım bankaları kapsam dışı |
| Geçmiş | Ekli dosyalar 2017 Eylül döneminden başlar; 2008–2017/2 sayfaları var ama eksiz |
| Yayın takvimi | Mart → Mayıs 1. hafta, Haziran → Ağustos 1. hafta, Eylül → Kasım 1. hafta, Aralık → Şubat 1. hafta |
| Erişim | Düz GET/HEAD, oturum/çerez yok, bot koruması yok. `robots.txt` yalnız `/admin`, `/user`, `/search` vb. yolları kapatır; rapor ve indirme yolları açık |

Seri: Akbank (AKBNK), Garanti BBVA (GARAN), Halkbank (HALKB), İş Bankası (ISCTR), Vakıfbank (VAKBN), Yapı Kredi (YKBNK) —
hisseleri Borsa İstanbul'da işlem gören altı mevduat bankası. Grup sabittir, seri sırası alfabetiktir.

### Kullanım koşulları (okundu: 27.11.2026)

- **Site kullanım koşulları** (https://www.tbb.org.tr/kullanim-kosullari): "Web sitemizde yayınlanan çalışmalar kaynak
  gösterilmek suretiyle izinsiz yayımlanabilir, ancak bu bilgilerin ticari amaçlarla kullanımı Türkiye Bankalar Birliği'nin
  yazılı iznine tabidir."
- **Raporun kendi notu** (Excel, "sayı" sayfası): "Çalışma, kaynak gösterilmek şartıyla yapılacak alıntılar dışında Türkiye
  Bankalar Birliği'nin yazılı izni olmaksızın hiçbir yolla çoğaltılamaz."

Uygulama:
- Yalnızca altı satırın şube sayısı **kaynak gösterilerek alıntılanır**; rapor dosyası depoya konmaz ve yeniden dağıtılmaz.
  Bu yüzden ayrıştırıcı testi **sentetik** bir fikstürle çalışır (`bot/tests/fixtures/make_tbb_sube_fixture.py`).
- Her değer kaynak sayfa, dosya adı, dosya adresi, sayfa/hücre, özgün satır etiketi ve indirme tarihiyle saklanır.
- Bu, esham'ın zaten kullandığı TCMB verisinin koşuluyla aynı ailedendir ("kaynak gösterilerek kullanılabilir; ticari
  kullanım yazılı izne tabidir").

> **Sahip kararı gerekiyor:** esham ücretsiz ve reklamsızdır; yine de "ticari amaç" kapsamına girip girmediğini koşullar
> tanımlamıyor. Siteye gelir modeli (reklam, ücretli üyelik, sponsor) eklenecekse TBB'den yazılı izin alınmalı ya da bu sayfa
> kaldırılmalıdır. Kapatmak için veri dosyasını silmek yeterlidir (sayfa, kart ve site haritası girdisi derlemede kalkar).

## 2. Boru hattı

```
TBB çeyrek sayfası ──GET/HEAD──► bot/esham/sources/tbb_sube.py  (stdlib .xlsx okuyucu + Tablo 1 ayrıştırıcı)
        │
        ▼
bot/esham/jobs/publish_veri_tbb_sube.py ──► web/public/data/veri/<slug>.json   (şema 1, nokta bazında kaynak)
        │
        ▼
web/src/lib/veri.ts  validateDataset · tableRows · toCsv · textAlternative · buildScene   ◄── TEK grafik tanımı
        │                                   │
        ▼                                   ▼
/veri/<slug> (SVG, etkileşimli)      web/scripts/veri-scenes.mjs → sahne JSON
/veri/<slug>/veri.csv                        │
/veri (dizin), sitemap                       ▼
                         bot/esham/publishing/veri_cards.py (Pillow, kart üreticisinin yazı tipleri)
                                             ▼
                         web/public/veri-kart/<slug>-<boyut>.png  (sahne sha256'sı PNG içinde)
```

- **Veri biçimi** (`web/src/lib/veri.ts`, `VeriDataset`): `periods` (artan, kesintisiz), `unit` (izinli liste), `periodType`
  (quarter/month/year), `series[].values` (eksik = `null`, ara değer yok), `series[].provenance` (dolu her değer için
  `{file, sheet, cell, label}`), `files` (`{name, url, page, retrieved}`), `methodology`, `breaks`, `sample`.
  Doğrulayıcı derlemede çalışır: geçersiz dosya derlemeyi durdurur.
- **Tek tanım, iki çıktı:** `buildScene` grafiğin tüm geometrisini ve metnini renk jetonlarıyla üretir. Sayfa onu SVG olarak
  (CSS değişkenleriyle; açık/koyu tema), bot PNG olarak çizer. Sayılar yalnız `fmtValue` ile biçimlenir. PNG, sahne
  baytlarının sha256'sını `esham:scene-sha256` olarak taşır; `veri.test.mjs` yayımlanan kartın güncel veriden üretilen
  sahneyle aynı olduğunu doğrular (eski sayılı kart → test kırmızı → dağıtım durur).
- **Erişilebilirlik:** SVG `role="img"` + `<title>`/`<desc>`; görünür metin alternatifi (son değerler); tam veri tablosu;
  klavye (←/→/Home/End) ve dokunma ile dönem okuma (`aria-live`). Renkler Okabe–Ito ailesinden; her seri ayrıca farklı uç
  işaret şekli ve doğrudan etiketle ayırt edilir; renklere anlam yüklenmez (kırmızı/yeşil yok).
- **Dizin/SEO:** `isIndexableDataset` (örnek veri asla; ≥8 dolu nokta, ≥4 dönem) → robots ve site haritası. OG/Twitter
  görseli = kart. Örnek (`sample: true`) veri: noindex, sayfada uyarı, grafik ve kartta "ÖRNEK VERİ".
- **Tarafsız dil:** tüm veri kümesi metinleri, sahne/kart metinleri ve sayfa şablonları `neutral-rules.json` kurallarıyla
  ve ek olarak `COMMENTARY_PATTERNS` (geriledi, öne geçti, en çok, rekor…) ile test edilir (web ve bot).

### Çalıştırma

```bash
cd bot
python -m esham.jobs.publish_veri_tbb_sube          # yalnız eksik çeyrekleri indirir (ağ)
python -m esham.jobs.publish_veri_cards             # kartları yeniden üretir (node gerekir)
python -m esham.jobs.publish_veri_cards --all-variants --out <depo içi klasör>   # taslak varyantlar
```

### Zamanlama (henüz KURULU DEĞİL)

TBB raporu çeyrek bitiminden ~5 hafta sonra çıkar. Önerilen GitHub Actions adımı (esham-schedule.yml içine ayrı iş):
`cron: "0 6 10,20 2,5,8,11 *"` → `publish_veri_tbb_sube` + `publish_veri_cards` → yalnız değişiklik varsa
`web/public/data/veri/**` ve `web/public/veri-kart/**` commit. Not: `web/public/data/**` değişiklikleri web CI'ı tetiklemez;
kart PNG'si aynı commit'te değiştiği için (`web/public/veri-kart/**` filtre dışı değil) web CI ve deploy testleri çalışır.
Yeni çeyrek yoksa dosya değişmez (yalnız tarih değişikliği yazılmaz).

## 3. Diğer grafik fikirleri (resmî kamu istatistikleri)

Durum anahtarı: **serbest** = kaynak göstererek izinsiz; **koşullu** = kaynak göstererek, ticari kullanım yazılı izne tabi;
**izin** = yazılı izin gerekli; **belirsiz** = koşul bulunamadı. Koşullar 27.11.2026'da okunmuştur.

| # | Grafik | Kaynak | Koşul durumu | Sıklık | Tarafsız mı |
|---|---|---|---|---|---|
| 1 | Altı bankanın **çalışan sayısı** (aynı TBB dosyası, "Çalışan Sayısı" sütunu) | TBB | koşullu (yukarıdaki gibi) | çeyreklik | evet — sayım |
| 2 | Sektör toplamı: banka, şube, çalışan sayısı (Tablo 1 "Sektör Toplamı") | TBB | koşullu | çeyreklik | evet |
| 3 | İnternet/mobil bankacılık aktif müşteri sayısı | TBB "Dijital, İnternet ve Mobil Bankacılık İstatistikleri" | koşullu | çeyreklik | evet |
| 4 | Sektör toplam aktif / krediler / mevduat (TL) | BDDK Aylık Bülten (https://www.bddk.org.tr/BultenAylik) | koşullu ("kaynak gösterilmek suretiyle kısmen alıntı"; ticari kullanım yazılı izne tabi; SSS sayfası) — indirme biçimi doğrulanmadı | aylık, önceki ay revize edilebilir | evet — revizyon notuyla |
| 5 | TÜFE yıllık değişim, politika faizi, haftalık rezerv | TCMB EVDS | koşullu (EVDS koşulları: kaynak gösterilerek yayımlanabilir; kullanıcıdan ek ücret alınamaz; ticari kullanım yazılı izne tabi) — API anahtarı gerekir | haftalık/aylık | evet — gözlenen değer |
| 6 | Kart sayısı (kredi/banka kartı) | BKM kart sayıları (XLS) | koşullu/çelişkili: istatistik sayfası "kaynak gösterilmeksizin yayınlanamaz", yasal uyarı "kopya edilemez" → **önce yazılı teyit** | aylık | evet |
| 7 | Katılım bankaları şube/çalışan sayısı (TBB grafiğinin tamamlayıcısı) | TKBB Veri Peteği | koşullu ("kaynak gösterilmek suretiyle izinsiz yayımlanabilir"; ticari kullanım yazılı izin) — biçim doğrulanmadı | aylık/çeyreklik | evet |
| 8 | Bankacılık/finans ile ilgili TÜİK serileri (ör. işgücü, finans sektörü istihdamı) | TÜİK (https://www.tuik.gov.tr/Kurumsal/Yasal_Uyari) | **serbest** ("kaynak gösterilmek suretiyle herhangi bir izine gerek duymaksızın yeniden kullanımı mümkündür") — veri portalı erişimi doğrulanmadı | aylık/çeyreklik | evet |
| 9 | Aylık KAP bildirim sayısı, türüne göre (esham'ın kendi KAP taramasından sayım) | KAP | belirsiz (kullanım koşulları sayfası bulunamadı); esham zaten KAP verisi işliyor — sayım türetilmiş veridir | aylık | evet — yalnız sayım, şirket sıralaması yok |
| 10 | Yatırım fonu sayısı / halka arz sayısı | SPK aylık istatistik bülteni (XLS) | belirsiz (koşul sayfası bulunamadı) | aylık (2–3 ay gecikme) | evet |
| 11 | Pay piyasası işlem hacmi (aylık) | Borsa İstanbul (CSV) | **izin** (telif notu: yazılı izinsiz kopya edilemez; veri dağıtımı lisansa tabi) → yapılmamalı | günlük/aylık | — |
| 12 | Pay sahibi yatırımcı sayısı | MKK sistem istatistikleri (PDF) | **izin** ("önceden yazılı olarak izni alınmadan … kopya edilemez") → yapılmamalı | aylık | — |

Öneri sırası: 1–3 (aynı TBB koşulu, hazır ayrıştırıcıyla birkaç satır), 8 (TÜİK, en açık koşul), 9 (kendi türetilmiş
sayımımız), sonra 4/5/7 için kurumlardan "ücretsiz, reklamsız site" teyidi. 11 ve 12 izin alınmadan yapılmamalı.

Tarafsızlık kuralları her grafik için aynı: değerlere göre sıralama/renklendirme yok (sabit alfabetik seri sırası), "en
yüksek/en düşük", "geriledi/öne geçti" gibi ifade yok, tahmin/projeksiyon çizgisi yok, eksik nokta boş.
