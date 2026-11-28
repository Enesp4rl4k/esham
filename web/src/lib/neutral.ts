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
const SENTENCE_SPLIT_RE = /(?:(?<=[.!?…])|(?<=[.!?…][)"”’»])) +/;
const ABBREVIATIONS = new Set<string>(rules.sentences.abbreviations);
// Çalışma anında kurulur (tsconfig hedefi ES2017; \p{..} literal'i tip denetiminde hedef uyarısı verebilir).
const INITIALS_RE = new RegExp("^(?:\\p{Lu}\\.)+$", "u");
const LOWER_START_RE = new RegExp("^\\p{Ll}", "u");

const APOSTROPHE_SUFFIXES = new Set<string>(rules.apostrophe.suffixes);
const LETTER_RE = new RegExp("^\\p{L}$", "u");
const UPPER_RE = new RegExp("^\\p{Lu}$", "u");
const LOST_APOSTROPHE_RE = new RegExp("(?<=[\\p{L}\\p{N}.])\\?(\\p{L}{1,6})(?![\\p{L}\\p{N}=&/])", "gu");

/**
 * Görüntüleme katmanı: KAP verisindeki kayıp kesme işaretini onarır ("Bulgaristan?da" → "Bulgaristan'da").
 * bot/esham/turkish.py `repair_lost_apostrophes` ile aynı kural (ortak vektörler: neutral-vectors.json →
 * apostrophe). Ham başlık/anahtar/slug DEĞİŞMEZ; yalnız gösterilen metne uygulanır.
 */
export function repairLostApostrophes(text: string): string {
  const s = text || "";
  return s.replace(LOST_APOSTROPHE_RE, (whole: string, suffix: string, offset: number) => {
    const start = s.lastIndexOf(" ", offset) + 1;
    const endIdx = s.indexOf(" ", offset + whole.length);
    const token = s.slice(start, endIdx >= 0 ? endIdx : s.length);
    if (!APOSTROPHE_SUFFIXES.has(suffix) || token.includes("://") || token.includes("=") || token.startsWith("www.")) return whole;
    if (suffix.length === 1) {
      // "x?a", "Ne?e": tek harfli ek yalnız özel ad sonrası ("İstanbul?a"); Python _proper_noun_before ile aynı.
      let i = offset;
      while (i > 0 && LETTER_RE.test(s[i - 1])) i--;
      const word = s.slice(i, offset);
      if (!(word.length >= 3 && UPPER_RE.test(word[0]))) return whole;
    }
    return "'" + suffix;
  });
}

/** bot/esham/sentences.py `split_sentences` ile aynı kural (bkz. neutral-rules.json → sentences._doc). */
export function splitSentences(text: string): string[] {
  const out: string[] = [];
  for (const piece of (text || "").split(SENTENCE_SPLIT_RE)) {
    if (!piece) continue;
    const prev = out[out.length - 1];
    if (prev !== undefined) {
      const words = prev.trimEnd().split(/\s+/);
      const tok = (words[words.length - 1] || "").replace(/^[("'“‘«[]+/, "");
      const initials = tok.length >= 2 && tok.length % 2 === 0 && INITIALS_RE.test(tok);
      const openParen = (prev.match(/\(/g) || []).length > (prev.match(/\)/g) || []).length;
      const ordinal = /^\d{1,3}\.$/.test(prev.trim());
      if (LOWER_START_RE.test(piece) || ABBREVIATIONS.has(tok) || initials || openParen || ordinal) {
        out[out.length - 1] = `${prev} ${piece}`;
        continue;
      }
    }
    out.push(piece);
  }
  return out;
}
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
    const rest = splitSentences(line).filter((s) => !hasBanned(s)).join(" ").trim();
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

/** Eski kayıtlarda hisse kodu biçimli etiketler doğrulanamaz; yalın görünümde atılır (kaynak etiketleri hariç). */
const TICKER_LIKE_RE = /^[A-Z][A-Z0-9]{2,5}$/;
const KEEP_TAGS = ["KAP", "BIST"];

export const isKapReport = (r: Pick<ViewableReport, "sources">) => r.sources.some((s) => s.toUpperCase() === "KAP");
export const isLegacy = (r: Pick<ViewableReport, "schemaVersion">) => !(typeof r.schemaVersion === "number" && r.schemaVersion >= REPORT_SCHEMA_VERSION);

/**
 * Kartta/sayfada başlığın altında gösterilecek özet. Yalın KAP raporunda (şablon yolu: "başlık + olgu bloğu")
 * özet resmî KAP başlığına eşittir (boş kalmasın diye başlığa düşer; hiçbir şey uydurulmaz). Başlığı aynen
 * tekrarlayan satır gösterilmez: boş döner.
 */
export function distinctSummary(r: { title: string; summary?: string | null }): string {
  // normalize(): Türkçe katlama (İ/I/ı → i), boşluk; sondaki noktalama yok sayılır. Python: neutral.distinct_summary.
  const key = (t: string) => {
    const s = normalize(t);
    let end = s.length;
    while (end > 0 && " \t.…!?;:,".includes(s[end - 1])) end--;
    return s.slice(0, end);
  };
  const summary = (r.summary ?? "").trim();
  return summary && key(summary) !== key(r.title) ? summary : "";
}

/** KAP başlığı "ŞİRKET: konu" biçimindedir; şirket kısmı (başlık AYNEN korunur, yalnız ayrıştırılır). */
export function companyFromTitle(title: string): string {
  const i = title.indexOf(": ");
  return i > 0 ? title.slice(0, i).trim() : "";
}

const KAP_QUERY_URL = "https://www.kap.org.tr/tr/bildirim-sorgu";

const LEGACY = rules.legacy;
const OWN_TEMPLATES: [RegExp, string][] = LEGACY.own_templates.map(([p, t]: string[]) => [new RegExp(p), t]);
export const NOTE_LEGACY_SUMMARY_KAP: string = rules.notes.legacy_summary_kap;
export const NOTE_LEGACY_SUMMARY: string = rules.notes.legacy_summary;

function ownTemplateType(title: string): string | null {
  const n = normalize(title);
  for (const [rx, typ] of OWN_TEMPLATES) if (rx.test(n)) return typ;
  return null;
}

/** Eski kaydın başlığı KAP'ın kendi metni mi? KAP kaynaklı ve bizim şablon başlıklarımızdan biri değilse. */
export function isOfficialKapTitle(r: Pick<ViewableReport, "title" | "sources">): boolean {
  return isKapReport(r) && ownTemplateType(r.title) === null;
}

/** Python `_tr_date` ile aynı: İstanbul saatiyle "12 Eylül 2026". */
function trDate(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  const ist = new Date(d.getTime() + 3 * 3600 * 1000);
  return `${ist.getUTCDate()} ${LEGACY.months[ist.getUTCMonth()]} ${ist.getUTCFullYear()}`;
}

/** Sürümsüz kaydın görünen başlığı: resmî KAP başlığı aynen; diğerleri "<tür> — <tarih>" (Python `legacy_title`). Hisse kodu eklenmez: eski kayıtlardaki kodlar doğrulanamaz. */
export function legacyTitle(r: Pick<ViewableReport, "title" | "sources" | "category" | "publishedAt">): string {
  if (isOfficialKapTitle(r)) return r.title;
  const categoryTypes = LEGACY.category_types as Record<string, string>;
  const typ = ownTemplateType(r.title) ?? categoryTypes[r.category] ?? "Piyasa notu";
  const date = trDate(r.publishedAt);
  return date ? `${typ} — ${date}` : typ;
}

/** Yayın zamanı ayırıcıları (İstanbul): dakika "13:45"; ISO metni saniye de taşıyorsa saniye "13:45:07". Saat alanı yoksa null. */
function trClock(iso: string): { hm: string; hms: string | null } | null {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime()) || !/T\d\d:\d\d/.test(iso)) return null;
  const ist = new Date(d.getTime() + 3 * 3600 * 1000);
  const p = (n: number) => String(n).padStart(2, "0");
  const hm = `${p(ist.getUTCHours())}:${p(ist.getUTCMinutes())}`;
  return { hm, hms: /T\d\d:\d\d:\d\d/.test(iso) ? `${hm}:${p(ist.getUTCSeconds())}` : null };
}

/**
 * Yalın görünümde BİZİM türetmiş olduğumuz başlıklardan (`legacyTitleDerived`, `legacyView` işaretler; KAP kaynaklı
 * olsa da) aynı olanlara raporun kendi yayın saatini ekler ("… — 7 Temmuz 2026 · 13:45"). Aynı dakikada
 * yayınlananlarda saniye de eklenir; hâlâ aynıysa çakışma kabul edilir. Resmî KAP başlıkları aynen kalır;
 * saat alanı yoksa ayırıcı eklenmez. Python `disambiguate_legacy_titles` ile aynı (ortak vektörler).
 */
export function disambiguateLegacyTitles<T extends Pick<ViewableReport, "title" | "publishedAt"> & { legacyTitleDerived?: boolean }>(
  reports: T[],
): T[] {
  const group = (rs: T[]) => {
    const m = new Map<string, number>();
    for (const r of rs) if (r.legacyTitleDerived === true) m.set(r.title, (m.get(r.title) ?? 0) + 1);
    return m;
  };
  const first = group(reports);
  const step1 = reports.map((r) => {
    if (r.legacyTitleDerived !== true || (first.get(r.title) ?? 0) < 2) return r;
    const c = trClock(r.publishedAt);
    return c ? { ...r, title: `${r.title} · ${c.hm}` } : r;
  });
  const second = group(step1);
  return step1.map((r, k) => {
    if (r.legacyTitleDerived !== true || (second.get(r.title) ?? 0) < 2 || r === reports[k]) return r;
    const c = trClock(r.publishedAt);
    return c?.hms ? { ...r, title: `${reports[k].title} · ${c.hms}` } : r;
  });
}

export function legacySummary(r: Pick<ViewableReport, "title" | "sources">): string {
  return isOfficialKapTitle(r) ? NOTE_LEGACY_SUMMARY_KAP : NOTE_LEGACY_SUMMARY;
}

/**
 * Eski kayıt kararı YALNIZ `schemaVersion` alanına dayanır (kaynakta "KAP" geçmesi, AI kullanımı veya
 * kalıp listesi gibi sezgiler kullanılmaz): bu alanı taşımayan her rapor bu tarafsız dil sürümünden önce
 * üretilmiştir ve gövdesi HİÇ render edilmez.
 * Yalın görünüm: görünen başlık (resmî KAP başlığı aynen; bizim eski başlıklarımız yorum taşıyabildiği için
 * "<tür> — <tarih>"), (KAP ise) şirket, tarih, kaynak/KAP bağlantısı ve not. Eski kart görselleri ve eski
 * halka arz "değerlendirme" metni kullanılmaz. Yalın görünüm noindex'tir (bkz. content.ts isIndexableReport).
 * Sürüm 2+ raporlara dokunulmaz.
 */
export function legacyView<T extends ViewableReport & { ipo?: object }>(
  report: T,
): { report: T; minimal: boolean; titleDerived: boolean } {
  if (!isLegacy(report)) return { report, minimal: false, titleDerived: false };
  const official = isOfficialKapTitle(report);
  const title = legacyTitle(report);
  // Şirket: başlıktaki ön ek, yoksa raporun yapılandırılmış `kap.company` alanı; ikisi de yoksa şirket satırı
  // yoktur (tahmin yok). Eski kayıtlardaki hisse kodları (etiket/`ipo.ticker`) güvenilir değildir; gösterilmez.
  const company = official ? companyFromTitle(report.title) || (report.kap?.company ?? "").trim() : "";
  const lines = official
    ? [
        "### Bildirim Bilgileri",
        `- **Başlık (KAP):** ${report.title}`,
        ...(company ? [`- **Şirket:** ${company}`] : []),
        `- **Yayın tarihi:** ${trDate(report.publishedAt)}`,
        "- **Bildirim türü:** Bu eski kayıtta saklanmamış.",
        `- **Kaynak:** [KAP bildirim sorgulama](${KAP_QUERY_URL})`,
        "",
        `> ${NOTE_LEGACY}`,
      ]
    : [
        "### Kayıt Bilgileri",
        `- **Yayın tarihi:** ${trDate(report.publishedAt)}`,
        `- **Kaynaklar:** ${report.sources.join(", ") || "Belirtilmemiş"}`,
        "",
        "> Bu sayfa eski bir kayıttır; içeriği güncel yayın ilkelerimize göre gösterilmemektedir.",
      ];
  // Eski `ipo` bloğu (kod, değerlendirme) kullanılmaz.
  const ipo = undefined as T["ipo"];
  return {
    report: {
      ...report,
      title,
      body: lines.join("\n"),
      summary: legacySummary(report),
      tags: report.tags.filter((t) => !hasBanned(t) && !(TICKER_LIKE_RE.test(t) && !KEEP_TAGS.includes(t))),
      image: undefined,
      ipo,
    },
    minimal: true,
    titleDerived: !official, // başlığı biz türettik (KAP kaynaklı olsa da)
  };
}
