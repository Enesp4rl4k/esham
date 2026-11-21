import test from "node:test";
import assert from "node:assert/strict";
import { readdirSync, readFileSync, statSync } from "node:fs";
import { dirname, join, relative } from "node:path";
import { fileURLToPath } from "node:url";

// web/src altında ziyaretçiye gösterilebilecek kişisel mutlak yol (Windows kullanıcı adı, /home/<ad> vb.) olmamalı.
const SRC = join(dirname(fileURLToPath(import.meta.url)), "..");
const SELF = fileURLToPath(import.meta.url);
const PATTERNS = [
  /\b[A-Za-z]:[\\/]+Users[\\/]+[^\s"'<>*]/i, // C:\Users\ad, C:/Users/ad
  /(^|[^A-Za-z0-9_.-])\/Users\/[A-Za-z0-9._-]+\//, // macOS
  /(^|[^A-Za-z0-9_.-])\/home\/(?!user\b|runner\b)[a-z][a-z0-9_-]*\//, // Linux ev dizini
];

function* walk(dir) {
  for (const name of readdirSync(dir)) {
    const full = join(dir, name);
    if (statSync(full).isDirectory()) yield* walk(full);
    else if (/\.(tsx?|jsx?|mjs|cjs|json|mdx?|css)$/.test(name)) yield full;
  }
}

test("web/src içinde kişisel mutlak yol yok", () => {
  const hits = [];
  for (const file of walk(SRC)) {
    if (file === SELF) continue;
    readFileSync(file, "utf8").split(/\r?\n/).forEach((line, i) => {
      if (PATTERNS.some((re) => re.test(line))) hits.push(`${relative(SRC, file)}:${i + 1}`);
    });
  }
  assert.deepEqual(hits, [], `Kişisel yol bulundu: ${hits.join(", ")}`);
});

test("kişisel yol deseni gerçekten yakalar", () => {
  assert.ok(PATTERNS.some((re) => re.test('"cwd": "C:\\Users\\biri\\proje"')));
  assert.ok(PATTERNS.some((re) => re.test("C:/Users/biri/proje")));
  assert.ok(PATTERNS.some((re) => re.test("cd /home/biri/proje")));
  assert.ok(!PATTERNS.some((re) => re.test('"cwd": "<proje-klasörü>/bot"')));
});
