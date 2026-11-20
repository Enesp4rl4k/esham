// Statik çıktı (out/) için yardımcılar: dosya sayımı, budama, bütçe kontrolü.
// Cloudflare Pages bir dağıtımda en fazla 20.000 dosyaya izin verir; aşılırsa dağıtım başarısız olur.
import { readdirSync, rmSync, statSync } from "node:fs";
import { join } from "node:path";

export const FILE_LIMIT = 20000;
export const WARN_AT = 17000; // uyarı eşiği: ~3.000 dosya payı kalınca
export const FAIL_AT = 19000; // hata eşiği: son 1.000 dosya güvenlik payı

/** Bir klasördeki tüm dosyaların sayısı (özyinelemeli). */
export function countFiles(dir) {
  let n = 0;
  for (const e of readdirSync(dir, { withFileTypes: true })) {
    n += e.isDirectory() ? countFiles(join(dir, e.name)) : 1;
  }
  return n;
}

/** out/<bölüm>/ altındaki ilk seviye klasörlere göre dosya dökümü (en kalabalıktan başlayarak). */
export function breakdown(outDir) {
  const rows = [];
  for (const e of readdirSync(outDir, { withFileTypes: true })) {
    rows.push([e.name, e.isDirectory() ? countFiles(join(outDir, e.name)) : 1]);
  }
  const rootFiles = rows.filter(([name]) => statSync(join(outDir, name)).isFile()).length;
  const dirs = rows.filter(([name]) => statSync(join(outDir, name)).isDirectory()).sort((a, b) => b[1] - a[1]);
  return { dirs, rootFiles };
}

/** Yalnızca Next'in istemci tarafı prefetch parçalarını (`__next.*`) içeren klasör mü? */
function onlyNextSegments(dir) {
  const entries = readdirSync(dir, { withFileTypes: true });
  return entries.length > 0 && entries.every((e) => e.name.startsWith("__next"));
}

/**
 * `out/<bölüm>/<slug>/` klasörlerinden Next'in segment-prefetch dosyalarını (`__next.*`) siler.
 * Sayfa başına ~7 dosya eder; yalnızca <Link> ön-yüklemesi içindir. Yoksa istemci yönlendirici tam sayfa
 * yüklemesine geri düşer (içerik ve URL aynı), bu yüzden işlev kaybı olmaz. `slug.html` ve `slug.txt` kalır.
 */
export function pruneSegments(outDir, sections = ["rapor", "hisse", "kategori", "fon"]) {
  let removed = 0;
  for (const section of sections) {
    const base = join(outDir, section);
    let entries;
    try {
      entries = readdirSync(base, { withFileTypes: true });
    } catch {
      continue;
    }
    for (const e of entries) {
      if (!e.isDirectory()) continue;
      const dir = join(base, e.name);
      if (onlyNextSegments(dir)) {
        removed += countFiles(dir);
        rmSync(dir, { recursive: true, force: true });
      }
    }
  }
  return removed;
}
