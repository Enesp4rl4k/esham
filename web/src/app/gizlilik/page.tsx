import type { Metadata } from "next";
import { SITE_URL } from "@/lib/config";
import { LegalPage } from "@/components/LegalPage";

export const metadata: Metadata = {
  title: "Gizlilik ve KVKK Aydınlatma Metni",
  description: "Esham hangi verileri topluyor, ne için kullanıyor ve haklarınız neler.",
  alternates: { canonical: `${SITE_URL}/gizlilik` },
};

export default function PrivacyPage() {
  return (
    <LegalPage title="Gizlilik ve KVKK Aydınlatma Metni" updated="21 Kasım 2026">
      <p>
        Bu metin, 6698 sayılı Kişisel Verilerin Korunması Kanunu (KVKK) kapsamında Esham sitesinde hangi verilerin işlendiğini açıklar. Siteyi kullanmak için hesap oluşturmanız ya da kişisel veri girmeniz gerekmez.
      </p>

      <h2>İşlenen veriler</h2>
      <ul>
        <li>
          <strong>E-posta adresi:</strong> yalnızca bülten formunu doldurursanız. Amaç, günlük bülteni göndermektir. Hukuki sebep açık rızanızdır; dilediğiniz zaman bülten içindeki bağlantıdan abonelikten çıkabilirsiniz.
        </li>
        <li>
          <strong>Tarayıcıda saklanan tercihler:</strong> izleme listeniz, ana sayfa düzeniniz ve tema seçiminiz yalnızca kendi tarayıcınızda (localStorage) tutulur; sunucularımıza gönderilmez.
        </li>
        <li>
          <strong>Ziyaret istatistikleri:</strong> sayfa görüntüleme sayıları, ülke ve cihaz türü gibi toplu veriler çerez kullanmayan bir ölçüm hizmetiyle (Cloudflare Web Analytics) toplanır. Bu veriler sizi kimliğinizle ilişkilendirmez.
        </li>
        <li>
          <strong>Sunucu kayıtları:</strong> sitenin barındırıldığı Cloudflare, güvenlik ve performans için IP adresi gibi teknik kayıtları kendi politikasına göre işleyebilir.
        </li>
      </ul>

      <h2>Çerezler</h2>
      <p>Esham kendi çerezlerini kullanmaz ve reklam ya da takip çerezi yerleştirmez.</p>

      <h2>Verilerin aktarılması</h2>
      <p>
        E-posta adresiniz bülten gönderimi için altyapı sağlayıcılarımıza (form ve e-posta hizmetleri) aktarılabilir. Verileriniz satılmaz ve reklam amacıyla paylaşılmaz. Hizmet sağlayıcıların bir kısmı yurt dışında olabilir.
      </p>

      <h2>Saklama süresi</h2>
      <p>E-posta adresiniz abonelikten çıkana kadar saklanır; çıkış talebinden sonra silinir.</p>

      <h2>Haklarınız</h2>
      <p>
        KVKK madde 11 uyarınca verilerinizin işlenip işlenmediğini öğrenme, düzeltme, silme ve işlenmesine itiraz etme haklarına sahipsiniz. Taleplerinizi <a href="/iletisim">iletişim</a> sayfasındaki kanaldan iletebilirsiniz.
      </p>
    </LegalPage>
  );
}
