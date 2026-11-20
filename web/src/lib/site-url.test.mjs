import { test } from "node:test";
import assert from "node:assert/strict";
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative, sep } from "node:path";
import { fileURLToPath } from "node:url";

// Site adresi tek kaynaktan (src/lib/config.ts → SITE_URL) gelmeli.
// Burada "esham.pages.dev" sabit yazılırsa özel alan adına geçişte unutulur.
const SRC = fileURLToPath(new URL("..", import.meta.url));
const ALLOWED = new Set([
  join("lib", "config.ts"), // varsayılan değerin tek yeri
  join("lib", "site-url.test.mjs"),
]);
// TODO: tarim-emtia henüz SITE_URL'e taşınmadı (üzerinde devam eden iş var).
const ALLOWED_PREFIX = [join("app", "tarim-emtia") + sep];

function walk(dir) {
  return readdirSync(dir).flatMap((n) => {
    const p = join(dir, n);
    return statSync(p).isDirectory() ? walk(p) : [p];
  });
}

test("web/src içinde sabit esham.pages.dev yok (config.ts hariç)", () => {
  const offenders = walk(SRC)
    .map((f) => relative(SRC, f))
    .filter((f) => !ALLOWED.has(f) && !ALLOWED_PREFIX.some((p) => f.startsWith(p)))
    .filter((f) => /\.(tsx?|mjs|js|json|css)$/.test(f))
    .filter((f) => readFileSync(join(SRC, f), "utf8").includes("esham.pages.dev"));
  assert.deepEqual(offenders, []);
});
