/**
 * Tarafsız dil katmanı (web tarafı) — bot/esham/neutral.py ile AYNI davranış.
 *
 * Tek kaynak: normalizasyon kuralları, yasaklı kalıplar ve not metinleri `neutral-rules.json`
 * dosyasındadır; Python da aynı dosyayı okur. Davranış eşitliği `neutral-vectors.json` ortak test
 * vektörleriyle iki tarafta da doğrulanır (neutral.test.mjs, bot/tests/test_neutral_language.py).
 *
 * Süzgeç YALNIZ üretilmiş yoruma uygulanır; KAP başlığı ve bildirimden alıntı süzülmez. Eski (şema
 * sürümü taşımayan) raporların yorum gövdesi hiç gösterilmez — bkz. `legacyView`.
 */
import rules from "./neutral-rules.json" with { type: "json" };

export const NOTE_KAP: string = rules.notes.kap;
export const NOTE_GENERIC: string = rules.notes.generic;
export const NOTE_LEGACY: string = rules.notes.legacy;
export const NOTE_AMOUNT_MISSING: string = rules.notes.amount_missing;
export const REPORT_SCHEMA_VERSION = 2;
export const BANNED_PATTERNS: readonly string[] = rules.patterns;

const esc = (s: string) => s.replace(/[\\\]^\-[]/g, "\\$&");
const charClass = (chars: string) => new RegExp(`[${Array.from(chars).map(esc).join("")}]`, "gu");

const N = rules.normalization;
const REMOVE_RE = charClass(N.remove);
const SPACE_RE = charClass(N.space);
const DASH_RE = charClass(N.dash);
const CONFUSABLES: Record<string, string> = N.confusables;
const LEET: Record<string, string> = N.leet;
const MIXED_SCRIPT_RE =
  /[^ ]*(?:[A-Za-z][^ ]*[Ͱ-ϿЀ-ӿ]|[Ͱ-ϿЀ-ӿ][^ ]*[A-Za-z])[^ ]*/g;
const ALNUM_TOKEN_RE = /(?<![a-z0-9])(?=[a-z0-9]*[a-z])(?=[a-z0-9]*[0-9])[a-z0-9]+(?![a-z0-9])/g;
const LETTER_SPACING_RE = new RegExp(`(?<![a-z0-9])(?:[a-z] ){${N.letter_spacing_min - 1},}[a-z](?![a-z0-9])`, "g");
const BANNED_RE = new RegExp(BANNED_PATTERNS.map((p) => `(?:${p})`).join("|"), "gu");

/** Python `normalize` ile birebir aynı adımlar. */
export function normalize(text: string): string {
  let s = (text || "").normalize("NFKC");
  s = s.replace(REMOVE_RE, "").replace(SPACE_RE, " ").replace(DASH_RE, " ");
  s = s.replace(MIXED_SCRIPT_RE, "karisik alfabe yazim");
  s = s.replace(/İ/g, "i").replace(/I/g, "i").replace(/ı/g, "i").toLowerCase();
  s = Array.from(s, (ch) => CONFUSABLES[ch] ?? ch).join("");
  s = s.normalize("NFD").replace(/[̀-ͯ]/g, "");
  s = s.replace(ALNUM_TOKEN_RE, (t) => Array.from(t, (c) => LEET[c] ?? c).join(""));
  s = s.replace(/ {2,}/g, " ").trim();
  return s.replace(LETTER_SPACING_RE, "harf aralikli yazim");
}

export function findBanned(text: string): string[] {
  const out: string[] = [];
  for (const line of (text || "").split(/\r?\n/)) {
    for (const m of normalize(line).matchAll(BANNED_RE)) out.push(m[0]);
  }
  return out;
}

export function hasBanned(text: string): boolean {
  return findBanned(text).length > 0;
}

const HEADING_RE = /^(#{1,6}) /;
const SENTENCE_SPLIT_RE = /(?<=[.!?…]) +/;
const TABLE_SEP_RE = /^\|? *:?-{2,}/;
const STRUCTURAL_RE = /^(?:[|\-*+>]|\d+[.)] )/;

function dropOrphanTables(lines: string[]): string[] {
  const out: string[] = [];
  let i = 0;
  while (i < lines.length) {
    if (lines[i].trimStart().startsWith("|")) {
      let j = i;
      while (j < lines.length && lines[j].trimStart().startsWith("|")) j++;
      const block = lines.slice(i, j);
      if (block.slice(1).some((b) => !TABLE_SEP_RE.test(b.trim()))) out.push(...block);
      i = j;
      continue;
    }
    out.push(lines[i]);
    i++;
  }
  return out;
}

/** Üretilmiş markdown'dan yasaklı içeriği ayıklar (Python `strip_banned` ile aynı). */
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
    if (m || STRUCTURAL_RE.test(line.trimStart())) continue;
    const rest = line.split(SENTENCE_SPLIT_RE).filter((s) => !hasBanned(s)).join(" ").trim();
    if (rest) out.push(rest);
  }
  return dropOrphanTables(out).join("\n").replace(/\n{3,}/g, "\n\n").trim();
}

// ---- eski raporlar: yalın görünüm ---------------------------------------------------------------

export interface ViewableReport {
  slug: string;
  title: string;
  category: string;
  summary: string;
  body: string;
  publishedAt: string;
  aiGenerated: boolean;
  tags: string[];
  sources: string[];
  image?: string;
  schemaVersion?: number;
  kap?: { url?: string; company?: string; type?: string; index?: string };
}

export const isKapReport = (r: Pick<ViewableReport, "sources">) => r.sources.some((s) => s.toUpperCase() === "KAP");
export const isLegacy = (r: Pick<ViewableReport, "schemaVersion">) => !(typeof r.schemaVersion === "number" && r.schemaVersion >= REPORT_SCHEMA_VERSION);

/** KAP başlığı "ŞİRKET: konu" biçimindedir; şirket kısmı (başlık AYNEN korunur, yalnız ayrıştırılır). */
export function companyFromTitle(title: string): string {
  const i = title.indexOf(": ");
  return i > 0 ? title.slice(0, i).trim() : "";
}

const KAP_QUERY_URL = "https://www.kap.org.tr/tr/bildirim-sorgu";

function trDate(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString("tr-TR", { day: "2-digit", month: "long", year: "numeric", timeZone: "Europe/Istanbul" });
}

/**
 * Eski kayıt kararı YALNIZ `schemaVersion` alanına dayanır (kaynakta "KAP" geçmesi, AI kullanımı veya
 * kalıp listesi gibi sezgiler kullanılmaz): bu alanı taşımayan her rapor bu tarafsız dil sürümünden önce
 * üretilmiştir ve gövdesi HİÇ render edilmez. Eski şablon metinleri de ("izlenmeye değer", "En ucuz",
 * "açılış beklentilerini şekillendirecek", "risk iştahı") yorum içerdiği ve listeyle güvenilir biçimde
 * ayıklanamadığı için KAP dışı eski raporlar da yalın görünüme düşer.
 * Yalın görünüm: başlık (aynen), (KAP ise) şirket, tarih, kaynak/KAP bağlantısı ve not. Eski kart
 * görselleri kullanılmaz (kategori varsayılan görseli). Sürüm 2+ raporlara dokunulmaz.
 */
export function legacyView<T extends ViewableReport>(report: T): { report: T; minimal: boolean } {
  if (!isLegacy(report)) return { report, minimal: false };
  const kap = isKapReport(report);

  const company = kap ? companyFromTitle(report.title) : "";
  const lines = [
    "### Bildirim Bilgileri",
    `- **Başlık:** ${report.title}`,
    ...(company ? [`- **Şirket:** ${company}`] : []),
    `- **Yayın tarihi:** ${trDate(report.publishedAt)}`,
    ...(kap
      ? [
          "- **Bildirim türü:** Bu eski kayıtta saklanmamış.",
          `- **Kaynak:** [KAP bildirim sorgulama](${KAP_QUERY_URL})`,
          "",
          `> ${NOTE_LEGACY}`,
        ]
      : [
          `- **Kaynaklar:** ${report.sources.join(", ") || "Belirtilmemiş"}`,
          "",
          "> Bu sayfa eski bir kayıttır; içeriği güncel yayın ilkelerimize göre gösterilmemektedir.",
        ]),
  ];
  return {
    report: {
      ...report,
      body: lines.join("\n"),
      summary: kap ? report.title : `${report.title} (eski kayıt)`,
      tags: report.tags.filter((t) => !hasBanned(t)),
      image: undefined,
    },
    minimal: true,
  };
}
