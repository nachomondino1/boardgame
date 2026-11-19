// Guardado de la colección entre dispositivos, sin cuentas. Ver MVP.md, sección 6b.
//
//   GET /api/sync  -> { collection | null }
//   PUT /api/sync  -> guarda { collection }
//
// Quien llama manda la "llave de sync" en el header X-Sync-Key: una cadena de 43
// caracteres al azar (256 bits) que genera su navegador. Esa llave ES la identidad:
// en KV (env.COLLECTIONS) se guarda bajo el hash de la llave, no la llave en sí.
// No hay sesiones, cookies ni secretos: lo único que necesita el servidor es el KV.

const KEY_RE = /^[A-Za-z0-9_-]{43}$/;
const MAX_BODY_BYTES = 1024 * 1024;
const encoder = new TextEncoder();

function json(body, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store" },
  });
}

async function storageKey(syncKey) {
  const digest = await crypto.subtle.digest("SHA-256", encoder.encode(syncKey));
  return `user:${Array.from(new Uint8Array(digest), (b) => b.toString(16).padStart(2, "0")).join("")}`;
}

// Se quedan solo los campos que usa el sitio, con su forma esperada: lo que llega
// del navegador no se guarda tal cual.
function sanitizeCollection(input) {
  if (!input || typeof input !== "object" || !input.games || typeof input.games !== "object") return null;
  const games = {};
  for (const [id, entry] of Object.entries(input.games)) {
    if (!/^\d{1,9}$/.test(id) || !entry || typeof entry !== "object") return null;
    const rating = Number(entry.rating);
    games[id] = {
      own: entry.own === true,
      prevowned: entry.prevowned === true,
      wanttobuy: entry.wanttobuy === true,
      rating: entry.rating != null && Number.isFinite(rating) && rating >= 0 && rating <= 10 ? rating : null,
    };
  }
  const savedAt = typeof input.savedAt === "string" && !Number.isNaN(Date.parse(input.savedAt)) ? input.savedAt : new Date().toISOString();
  return {
    source: input.source === "bgg" ? "bgg" : "manual",
    user: typeof input.user === "string" ? input.user.slice(0, 40) : null,
    savedAt,
    games,
  };
}

async function sync(request, env) {
  if (!env || !env.COLLECTIONS) return json({ error: "server_config", message: "Falta el almacenamiento (KV) en el servidor." }, 500);
  const syncKey = request.headers.get("X-Sync-Key") || "";
  if (!KEY_RE.test(syncKey)) return json({ error: "bad_key", message: "Llave de sincronización inválida." }, 400);
  const key = await storageKey(syncKey);

  if (request.method === "GET") {
    const record = await env.COLLECTIONS.get(key, "json");
    return json({ collection: record ? record.collection : null });
  }

  if (!(request.headers.get("Content-Type") || "").includes("application/json")) {
    return json({ error: "bad_request", message: "Falta Content-Type: application/json." }, 415);
  }
  const text = await request.text();
  if (text.length > MAX_BODY_BYTES) return json({ error: "too_large", message: "La colección es demasiado grande." }, 413);
  let collection;
  try {
    collection = sanitizeCollection(JSON.parse(text).collection);
  } catch {
    collection = null;
  }
  if (!collection) return json({ error: "bad_request", message: "Colección inválida." }, 400);
  await env.COLLECTIONS.put(key, JSON.stringify({ collection, updatedAt: new Date().toISOString() }));
  return json({ ok: true, savedAt: collection.savedAt });
}

// Devuelve una Response si la ruta es /api/sync, o null para que siga el resto.
export async function handleSync(request, env) {
  const { pathname } = new URL(request.url);
  if (pathname === "/api/sync" && (request.method === "GET" || request.method === "PUT")) return sync(request, env);
  return null;
}
