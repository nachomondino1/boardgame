// GET /api/collection?user=<usuario de BGG>
// Trae la colección pública de ese usuario desde la API oficial de BGG (con el
// token de la aplicación, que vive solo en el servidor: env.BGG_TOKEN) y la
// devuelve ya reducida a lo que usa el sitio. Ver MVP.md, sección 5.

const BGG_COLLECTION_URL = "https://boardgamegeek.com/xmlapi2/collection";
const USER_AGENT = "boardgame-mvp/1.0 (+https://github.com/nachomondino1/boardgame)";
const USERNAME_RE = /^[A-Za-z0-9_. -]{1,40}$/;
const RETRIES_ON_202 = 3; // BGG responde 202 mientras arma la lista
const RETRY_DELAY_MS = 3000;
const CACHE_SECONDS = 6 * 60 * 60; // para no gastar la cuota del token compartido

function json(body, status = 200, extraHeaders = {}) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json; charset=utf-8", ...extraHeaders },
  });
}

function attr(attrs, name) {
  const m = new RegExp(`\\b${name}="([^"]*)"`).exec(attrs);
  return m ? m[1] : null;
}

// xmlapi2/collection (stats=1) -> [{ id, own, prevowned, wanttobuy, rating }].
// El XML es simple y regular, así que no hace falta un parser (en Workers no hay DOMParser).
// Solo quedan los juegos con alguno de own/prevowned/wanttobuy o con puntaje.
export function parseCollection(xml) {
  const games = [];
  for (const m of xml.matchAll(/<item\b([^>]*)>([\s\S]*?)<\/item>/g)) {
    const id = attr(m[1], "objectid");
    const status = /<status\b([^>]*?)\/?>/.exec(m[2]);
    const ratingMatch = /<rating\b[^>]*\bvalue="([^"]*)"/.exec(m[2]);
    if (!id || !status) continue;
    const rating = ratingMatch && Number.isFinite(Number(ratingMatch[1])) && ratingMatch[1] !== "" ? Number(ratingMatch[1]) : null;
    const game = {
      id,
      own: attr(status[1], "own") === "1",
      prevowned: attr(status[1], "prevowned") === "1",
      wanttobuy: attr(status[1], "wanttobuy") === "1",
      rating,
    };
    if (game.own || game.prevowned || game.wanttobuy || game.rating != null) games.push(game);
  }
  return games;
}

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

export async function onRequestGet({ request, env }) {
  const url = new URL(request.url);
  const user = (url.searchParams.get("user") || "").trim();
  if (!USERNAME_RE.test(user)) {
    return json({ error: "invalid_user", message: "Usuario de BGG inválido." }, 400);
  }
  if (!env || !env.BGG_TOKEN) {
    return json({ error: "server_config", message: "Falta configurar el acceso a BGG en el servidor." }, 500);
  }

  const cache = typeof caches !== "undefined" ? caches.default : null;
  const cacheKey = new Request(`${url.origin}/api/collection?user=${encodeURIComponent(user.toLowerCase())}`);
  if (cache) {
    const hit = await cache.match(cacheKey);
    if (hit) return hit;
  }

  const query = new URLSearchParams({ username: user, stats: "1", subtype: "boardgame", excludesubtype: "boardgameexpansion" });
  let bgg;
  for (let attempt = 0; attempt <= RETRIES_ON_202; attempt++) {
    try {
      bgg = await fetch(`${BGG_COLLECTION_URL}?${query}`, {
        headers: { "User-Agent": USER_AGENT, Authorization: `Bearer ${env.BGG_TOKEN}` },
      });
    } catch (e) {
      return json({ error: "bgg_unreachable", message: "No pude conectar con BGG. Probá de nuevo en un rato." }, 502);
    }
    if (bgg.status !== 202) break;
    if (attempt < RETRIES_ON_202) await sleep(RETRY_DELAY_MS);
  }

  if (bgg.status === 202) return json({ status: "pending" }, 202, { "Retry-After": "5" });
  if (bgg.status === 401 || bgg.status === 403) {
    return json({ error: "bgg_auth", message: "BGG rechazó el acceso de la aplicación." }, 502);
  }
  if (bgg.status === 429 || bgg.status === 503) {
    return json({ error: "rate_limited", message: "BGG está limitando los pedidos. Probá de nuevo en un minuto." }, 429, { "Retry-After": "60" });
  }
  const body = await bgg.text();
  if (bgg.status === 400 || bgg.status === 404 || /<errors?>/.test(body)) {
    return json({ error: "user_not_found", message: `No encontré al usuario "${user}" en BGG.` }, 404);
  }
  if (bgg.status !== 200) {
    return json({ error: "bgg_error", message: `BGG respondió con un error (${bgg.status}).` }, 502);
  }

  const games = parseCollection(body);
  const response = json(
    { user, fetchedAt: new Date().toISOString(), count: games.length, games },
    200,
    { "Cache-Control": `public, max-age=300, s-maxage=${CACHE_SECONDS}` }
  );
  if (cache) await cache.put(cacheKey, response.clone());
  return response;
}
