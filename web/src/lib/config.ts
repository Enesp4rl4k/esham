/**
 * Site genelinde kullanılan uç nokta ayarları.
 *
 * Statik export (`output: "export") olduğu için build zamanında gömülür.
 * `NEXT_PUBLIC_ESHAM_BOT_URL` — bot'un Flask uç noktası (Render vb.):
 *   `/subscribe` (abone ekleme) ve `/unsubscribe` (imzalı çıkış) buradadır.
 *
 * Boş bırakılırsa abonelik formu mevcut Formspree yedeğine düşer ve çıkış
 * sayfası talimat gösterir — site yine çalışır (zarif bozulma).
 */
export const BOT_API_URL = (process.env.NEXT_PUBLIC_ESHAM_BOT_URL ?? "").replace(
  /\/+$/,
  "",
);

/** Formspree yedeği — bot uç noktası henüz bağlanmamışsa kullanılır. */
export const FORMSPREE_FALLBACK = "https://formspree.io/f/xnjkwdkr";
