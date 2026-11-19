// Servidor local sin dependencias: sirve docs/ y atiende /api/collection con la
// misma función que corre en Cloudflare Pages (functions/api/collection.js).
// Uso: node --env-file=<ruta al .env con BGG_TOKEN> dev-server.mjs [puerto]
import { createServer } from "node:http";
import { readFile, writeFile } from "node:fs/promises";
import { extname, join, normalize } from "node:path";
import { fileURLToPath } from "node:url";
import { onRequestGet } from "./functions/api/collection.js";
import { handleSync } from "./functions/api/sync.js";

const ROOT = join(fileURLToPath(new URL(".", import.meta.url)), "docs");
const PORT = Number(process.argv[2]) || 8766;
const TYPES = {
  ".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".css": "text/css; charset=utf-8",
  ".json": "application/json; charset=utf-8", ".jpg": "image/jpeg", ".webp": "image/webp", ".svg": "image/svg+xml",
};

// KV de juguete para probar las cuentas en local: un archivo JSON (gitignored).
const KV_FILE = join(fileURLToPath(new URL(".", import.meta.url)), ".dev-kv.json");
const devKv = {
  async get(key) {
    try { const all = JSON.parse(await readFile(KV_FILE, "utf8")); return key in all ? all[key] : null; } catch { return null; }
  },
  async put(key, value) {
    let all = {};
    try { all = JSON.parse(await readFile(KV_FILE, "utf8")); } catch { /* primer guardado */ }
    all[key] = JSON.parse(value);
    await writeFile(KV_FILE, JSON.stringify(all, null, 2));
  },
};
const env = { ...process.env, COLLECTIONS: devKv };

function send(res, response, body) {
  res.writeHead(response.status, Object.fromEntries(response.headers));
  res.end(body);
}

async function readBody(req) {
  const chunks = [];
  for await (const chunk of req) chunks.push(chunk);
  return Buffer.concat(chunks);
}

createServer(async (req, res) => {
  const url = new URL(req.url, `http://localhost:${PORT}`);
  if (url.pathname === "/api/collection") {
    const response = await onRequestGet({ request: new Request(url, { method: "GET" }), env: process.env });
    res.writeHead(response.status, Object.fromEntries(response.headers));
    res.end(Buffer.from(await response.arrayBuffer()));
    return;
  }
  if (url.pathname === "/api/sync") {
    const hasBody = req.method !== "GET" && req.method !== "HEAD";
    const request = new Request(url, { method: req.method, headers: req.headers, body: hasBody ? await readBody(req) : undefined });
    const response = await handleSync(request, env);
    if (response) { send(res, response, Buffer.from(await response.arrayBuffer())); return; }
  }
  const path = normalize(url.pathname === "/" ? "/index.html" : url.pathname);
  if (path.includes("..")) { res.writeHead(403).end(); return; }
  try {
    const data = await readFile(join(ROOT, path));
    res.writeHead(200, { "Content-Type": TYPES[extname(path)] || "application/octet-stream" });
    res.end(data);
  } catch {
    res.writeHead(404).end("No encontrado");
  }
}).listen(PORT, () => console.log(`http://localhost:${PORT}`));
