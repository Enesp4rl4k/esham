// Cloudflare Pages benzeri yerel sunucu: /yol → yol.html → yol/index.html; bulunamazsa 404.html.
// Kullanım: node scripts/serve-export.mjs [out] [port]
import { createServer } from "node:http";
import { existsSync, readFileSync, statSync } from "node:fs";
import { extname, join, normalize, resolve, sep } from "node:path";

const root = resolve(process.argv[2] ?? "out");
const port = Number(process.argv[3] ?? 4173);
const types = {
  ".html": "text/html; charset=utf-8",
  ".txt": "text/plain; charset=utf-8",
  ".js": "text/javascript",
  ".css": "text/css",
  ".json": "application/json",
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".svg": "image/svg+xml",
  ".ico": "image/x-icon",
  ".woff2": "font/woff2",
  ".xml": "application/xml",
  ".webmanifest": "application/manifest+json",
};

const isFile = (p) => existsSync(p) && statSync(p).isFile();

function resolveFile(urlPath) {
  const clean = normalize(decodeURIComponent(urlPath)).replace(/^([/\\])+/, "");
  const base = join(root, clean);
  if (base !== root && !base.startsWith(root + sep)) return null; // dizin dışına çıkma
  for (const c of [base, base + ".html", join(base, "index.html")]) if (isFile(c)) return c;
  return null;
}

createServer((req, res) => {
  const url = new URL(req.url ?? "/", "http://x");
  const file = resolveFile(url.pathname);
  if (file) {
    res.writeHead(200, { "content-type": types[extname(file)] ?? "application/octet-stream" });
    res.end(readFileSync(file));
    return;
  }
  const nf = join(root, "404.html");
  res.writeHead(404, { "content-type": "text/html; charset=utf-8" });
  res.end(isFile(nf) ? readFileSync(nf) : "404");
}).listen(port, () => console.log(`Önizleme: http://localhost:${port}  (kök: ${root})`));
