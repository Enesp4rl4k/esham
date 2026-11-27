/**
 * Görüntüleme anında tarafsız dil süzgeci.
 *
 * Bot artık rapor/kart/gönderide piyasa yargısı üretmiyor (bkz. bot/esham/neutral.py), ancak daha önce
 * üretilmiş raporlar (web/content/reports/*.json) "Finansal Sinyal: Pozitif", destek/direnç/pivot
 * tabloları, "İlk Kâr Satışı Bölgesi", "MEGA SÖZLEŞME" gibi içerikler barındırıyor. Bu dosyalar toplu
 * olarak yeniden yazılmadan, okunurken aynı kalıp listesiyle temizlenir:
 *   - yasaklı kalıp içeren başlığın bölümü (alt başlıklarıyla) gizlenir,
 *   - madde/tablo satırları bütünüyle, düz paragraflarda yalnızca ilgili cümle gizlenir,
 *   - gövde satırı kalmayan tablolar kaldırılır,
 *   - özetteki "MEGA SÖZLEŞME | ..." gibi etiket parçaları ve "Mega Sözleşme" etiketi düşer.
 * Mantık Python `strip_banned` ile aynıdır. Dosya, `node --test` ile doğrudan yüklenebilmesi için
 * göreli import içermez.
 */

/**
 * Yasaklı piyasa yargısı / yatırım tavsiyesi kalıpları. Tek kaynak: bot/esham/neutral.py
 * `BANNED_PATTERNS` — bot/tests/test_neutral_language.py bu dizinin Python listesiyle birebir aynı
 * olduğunu doğrular (değiştirirken ikisini birlikte güncelleyin). Kalıplar `foldTr` edilmiş
 * (küçük harf, aksansız, ı→i) metne uygulanır.
 */
export const BANNED_PATTERNS: readonly string[] = [
  "\\bsinyal",
  "\\bpozitif\\s*\\(",
  "\\bnegatif\\s*\\(",
  "\\bnotr\\s*[-/]\\s*pozitif",
  "\\bpozitif haber",
  "haber akisi etkisi",
  "\\bpozitif fiyatlama",
  "fiyatlama egilimi",
  "\\b(pozitif|negatif) (etki|yansima|algi)",
  "\\b(olumlu|olumsuz) (algi|senaryo)",
  "etkisi yaratmasi beklenir",
  "\\bbeklenir\\b",
  "fiyatlama etkisi",
  "\\bfiyat etkisi",
  "\\bfiyat algisi",
  "\\bhisse uzerinde\\b",
  "\\bhisse fiyatlamasi",
  "\\bhisse yansimasi",
  "\\bpiyasa yansimasi",
  "\\bkatalizor",
  "(yukselis|dusus|getiri|prim) potansiyeli",
  "\\bpotansiyel:",
  "\\bdirenc",
  "\\bkritik destek",
  "\\bdestek seviye",
  "\\bdestek bolgesi",
  "\\btaban destegi",
  "\\btepki alim",
  "\\b(alim|satis) bolgesi",
  "\\bkar satisi",
  "\\bkar realizasyonu",
  "\\bpivot",
  "\\bfibonacci",
  "\\bkey level",
  "\\bteknik esik",
  "\\basiri (alim|satim)",
  "\\brsi\\b",
  "\\bhareketli ortalama",
  "\\bhedef fiyat",
  "\\bfiyat hedefi",
  "\\badil deger",
  "\\bguclu iskonto",
  "\\byuksek primli",
  "\\bcazip\\b",
  "\\bboga\\b",
  "\\bayi (senaryo|piyasa)",
  "\\bbull(ish)?\\b",
  "\\bbear(ish)?\\b",
  "\\bal\\s*/\\s*sat\\b",
  "\\b(alim|yatirim) firsati",
  "\\b(alim|satim) tavsiyesi",
  "tavsiye ederim",
  "\\boneririm",
  "portfoyunuze ekleyin",
  "\\bkesinlikle (al|sat)",
  "\\bmutlaka al",
  "\\bsimdi al\\b",
  "\\bgaranti (getiri|kazanc|kar)",
  "\\bkesin kazanc",
  "\\bmega (is|sozlesme|anlasma)",
  "\\btier-?\\s?[12]\\b",
  "\\bdev (anlasma|sozlesme|ihale)",
  "\\bstratejik sinif",
  "\\btemel finansal carpanlar",
  "\\bciro etki carpani",
  "\\bucuz buldugu",
  "\\brisk ve firsatlar",
  "\\bhisseye (olan )?talep",
  "\\byatirimci ilgisini",
  "\\bpara (girisi|cikisi)",
  "\\binsider trading"
];

/** Türkçe-duyarsız katlama (fold.ts ile aynı; bağımsız yüklenebilmek için burada da tanımlı). */
export function foldTr(s: string): string {
  return s
    .replace(/İ/g, "i")
    .replace(/I/g, "i")
    .toLowerCase()
    .replace(/ı/g, "i")
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "");
}

const BANNED_RE = new RegExp(BANNED_PATTERNS.map((p) => `(?:${p})`).join("|"), "g");

export function findBanned(text: string): string[] {
  return Array.from(foldTr(text || "").matchAll(BANNED_RE), (m) => m[0]);
}

export function hasBanned(text: string): boolean {
  return findBanned(text).length > 0;
}

const HEADING_RE = /^(#{1,6})\s/;
const SENTENCE_SPLIT_RE = /(?<=[.!?…])\s+/;
const TABLE_SEP_RE = /^\|?\s*:?-{2,}/;

function stripSentences(line: string): string {
  return line
    .split(SENTENCE_SPLIT_RE)
    .filter((s) => !hasBanned(s))
    .join(" ")
    .trim();
}

function dropOrphanTables(lines: string[]): string[] {
  const out: string[] = [];
  let i = 0;
  while (i < lines.length) {
    if (lines[i].trimStart().startsWith("|")) {
      let j = i;
      while (j < lines.length && lines[j].trimStart().startsWith("|")) j++;
      const block = lines.slice(i, j);
      const bodyRows = block.slice(1).filter((b) => !TABLE_SEP_RE.test(b.trim()));
      if (bodyRows.length) out.push(...block);
      i = j;
      continue;
    }
    out.push(lines[i]);
    i++;
  }
  return out;
}

export function stripBanned(markdown: string): string {
  if (!markdown) return "";
  const out: string[] = [];
  let skipLevel: number | null = null;
  for (const line of markdown.split(/\r?\n/)) {
    const m = HEADING_RE.exec(line);
    if (m) {
      const level = m[1].length;
      if (skipLevel !== null && level <= skipLevel) skipLevel = null;
      if (skipLevel === null && hasBanned(line)) {
        skipLevel = level;
        continue;
      }
    }
    if (skipLevel !== null) continue;
    if (!hasBanned(line)) {
      out.push(line);
      continue;
    }
    const stripped = line.trimStart();
    if (m || /^[|\-*+>]/.test(stripped) || /^\d+[.)]\s/.test(stripped)) continue;
    const rest = stripSentences(line);
    if (rest) out.push(rest);
  }
  return dropOrphanTables(out).join("\n").replace(/\n{3,}/g, "\n\n").trim();
}

/** Özetteki " | " ile ayrılmış etiket parçalarından yasaklı olanları atar, kalanı süzer. */
export function sanitizeSummary(summary: string, fallback: string): string {
  if (!hasBanned(summary)) return summary;
  const parts = summary.split(" | ").filter((p) => !hasBanned(p));
  return stripBanned(parts.join(" | ")) || fallback;
}

export interface SanitizableReport {
  title: string;
  summary: string;
  body: string;
  tags: string[];
  sources: string[];
  image?: string;
}

/**
 * Raporu süzer; temiz raporlara dokunmaz. Bir şey ayıklandıysa ve rapor bir KAP bildirimi özetiyse
 * eski kart görseli de gösterilmez (hisse fiyatı/RSI/destek çipleri veya "MEGA İŞ ANLAŞMASI" etiketi
 * taşıyabilir); sayfa kategori varsayılan görselini kullanır.
 */
export function sanitizeReport<T extends SanitizableReport>(report: T): { report: T; changed: boolean } {
  const bodyDirty = hasBanned(report.body);
  const summaryDirty = hasBanned(report.summary);
  const tags = report.tags.filter((t) => !hasBanned(t));
  if (!bodyDirty && !summaryDirty && tags.length === report.tags.length) {
    return { report, changed: false };
  }
  const isKap = report.sources.some((s) => s.toUpperCase() === "KAP");
  return {
    report: {
      ...report,
      body: bodyDirty ? stripBanned(report.body) : report.body,
      summary: summaryDirty ? sanitizeSummary(report.summary, report.title) : report.summary,
      tags,
      image: isKap ? undefined : report.image,
    },
    changed: true,
  };
}
