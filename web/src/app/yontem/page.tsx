import type { Metadata } from "next";
import Link from "next/link";
import { SITE_URL } from "@/lib/config";
import { DEFAULT_OG_IMAGE } from "@/lib/seo";

const title = "Yöntem ve Kaynaklar: Oranlar Nasıl Hesaplanıyor?";
const description = "Esham oranları hangi veriden, hangi formülle ve ne sıklıkla hesaplar; hangi sınırlar var, hatalar nasıl düzeltilir.";

export const metadata: Metadata = {
  title,
  description,
  alternates: { canonical: `${SITE_URL}/yontem` },
  openGraph: { title, description, url: `${SITE_URL}/yontem`, siteName: "Esham", locale: "tr_TR", type: "website", images: [DEFAULT_OG_IMAGE] },
};

const FORMULAS: [string, string][] = [
  ["F/K", "Piyasa değeri ÷ son 12 aylık (TTM) net kâr. Zarar eden şirkette gösterilmez."],
  ["PD/DD", "Piyasa değeri ÷ özkaynak (defter değeri)."],
  ["FD/FAVÖK", "(Piyasa değeri + net borç) ÷ son 12 aylık FAVÖK. Bankalar ve finansal kuruluşlarda hesaplanmaz."],
  ["ROE", "Son 12 aylık net kâr ÷ özkaynak."],
  ["Net marj", "Son 12 aylık net kâr ÷ son 12 aylık satış geliri."],
  ["Temettü verimi", "Son 12 ayda ödenen nakit kâr payı ÷ güncel fiyat."],
  ["Net borç/FAVÖK", "Net borç ÷ son 12 aylık FAVÖK. Bankalarda anlamlı olmadığı için hesaplanmaz."],
];

export default function MethodPage() {
  return (
    <div className="container mx-auto px-6 py-10 max-w-3xl">
      <h1 className="text-3xl md:text-4xl font-display font-bold mb-4">Yöntem ve Kaynaklar</h1>
      <p className="text-base text-zinc-300 leading-relaxed mb-8">
        Esham, Borsa İstanbul hisselerinin oranlarını bilançolardan kendisi hesaplar ve kaynağını gösterir. Bu sayfa, sitedeki sayıların nereden geldiğini, nasıl işlendiğini ve nerede yanıltabileceğini anlatır.
      </p>

      <h2 className="text-xl font-display font-semibold mb-3">Veri kaynakları</h2>
      <ul className="list-disc pl-5 space-y-2 text-base text-zinc-300 leading-relaxed mb-8">
        <li><strong className="text-white">Finansal tablolar:</strong> öncelik KAP finansal raporlarıdır (resmî IFRS/XBRL); KAP verisi eksik, eski ya da şüpheli eşlemeli olduğunda Yahoo Finance kullanılır ve hisse sayfasında kaynak yazılır. <strong className="text-white">Fiyatlar, piyasa değeri ve temettü:</strong> Yahoo Finance. Bilançolar çeyreklik alınır, son dört çeyrek toplanarak son 12 aylık (TTM) değerler oluşturulur.</li>
        <li><strong className="text-white">Bildirimler ve haberler:</strong> KAP (Kamuyu Aydınlatma Platformu) bildirimleri. İştirak oranları (NAV hesabı) KAP şirket sayfalarındaki doğrudan paylardan okunur.</li>
        <li><strong className="text-white">Tarımsal emtia:</strong> TÜRİB, TMO ve TÜİK yayınları.</li>
      </ul>

      <h2 className="text-xl font-display font-semibold mb-3">Formüller</h2>
      <dl className="mb-8 divide-y divide-zinc-800/60 rounded-xl border border-zinc-800">
        {FORMULAS.map(([k, v]) => (
          <div key={k} className="px-4 py-3 sm:grid sm:grid-cols-[10rem_1fr] sm:gap-4">
            <dt className="font-semibold text-white">{k}</dt>
            <dd className="text-zinc-300">{v}</dd>
          </div>
        ))}
      </dl>

      <h2 className="text-xl font-display font-semibold mb-3">Veri kalitesi ve sınırlar</h2>
      <ul className="list-disc pl-5 space-y-2 text-base text-zinc-300 leading-relaxed mb-8">
        <li><strong className="text-white">Döviz cinsinden tablolar:</strong> Bazı şirketler USD veya EUR raporlar. Piyasa değeri TL olduğundan çarpanlar hesaplanırken tablo, kurla TL&apos;ye çevrilir.</li>
        <li><strong className="text-white">Enflasyon muhasebesi (TMS 29):</strong> Yüksek enflasyon döneminde kâr ve özkaynak rakamları dönemler arasında doğrudan karşılaştırılamayabilir.</li>
        <li><strong className="text-white">Uç değer bayrağı:</strong> Mutlak olarak anlamsız çarpanlar ve Yahoo&apos;nun kendi F/K değeriyle büyük fark gösteren satırlar &quot;şüpheli&quot; işaretlenir; sektör medyanlarına, liderlik tablolarına ve hazır taramalara katılmaz.</li>
        <li><strong className="text-white">KAP kapsamı:</strong> KAP hattı şimdilik finansal olmayan (banka/sigorta dışı) şirketlerde çalışır; bu şirketlerin hepsi henüz kapsanmıyor. Kapsam dışındakiler Yahoo Finance verisiyle hesaplanır ve KAP ile teyit edilmemiştir. Karar vermeden önce resmî bildirimlere bakın.</li>
        <li><strong className="text-white">Sektör medyanı:</strong> Yalnızca en az 3 geçerli değeri olan sektörlerde hesaplanır.</li>
      </ul>

      <h2 className="text-xl font-display font-semibold mb-3">Güncelleme sıklığı</h2>
      <p className="text-base text-zinc-300 leading-relaxed mb-8">
        Haber ve piyasa raporları hafta içi seans boyunca otomatik üretilir. Hisse oranları her iş günü kapanıştan sonra yeniden hesaplanır; her sayfada verinin tarihi gösterilir.
      </p>

      <h2 className="text-xl font-display font-semibold mb-3">Değerleme araçları</h2>
      <p className="text-base text-zinc-300 leading-relaxed mb-8">
        Hisse sayfalarındaki DCF (indirgenmiş nakit akışı) ve NAV (net aktif değer) hesaplayıcıları varsayımları sizin ayarlamanız için tasarlanmış etkileşimli araçlardır; sonuçlar bir hedef fiyat önerisi değil, varsayımlarınızın matematiksel çıktısıdır.
      </p>

      <h2 className="text-xl font-display font-semibold mb-3">Hata bildirimi ve düzeltme</h2>
      <p className="text-base text-zinc-300 leading-relaxed mb-8">
        Yanlış bir rakam gördüyseniz hisse kodunu ve oranı <a href="https://x.com/eshamcomtr" className="underline" rel="noopener noreferrer">@eshamcomtr</a> hesabına bildirin. Doğrulanan hatalar düzeltilir ve ilgili hesaplama kuralı güncellenir.
      </p>

      <p className="text-sm text-zinc-400 leading-relaxed border-t border-zinc-800 pt-4">
        Esham&apos;deki içerik yalnızca bilgilendirme amaçlıdır; yatırım tavsiyesi değildir. Yatırım kararlarınızı kendi araştırmanıza ve lisanslı bir danışmana dayandırın.{" "}
        <Link href="/hisseler" className="underline">Hisse tarayıcıya git</Link>.
      </p>
    </div>
  );
}
