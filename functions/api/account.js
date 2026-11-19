// Cuenta con Google + colección guardada en Cloudflare KV. Ver MVP.md, sección 6b.
//
//   GET  /api/auth/google    -> redirige a Google (?next=/ruta para volver a la página)
//   GET  /api/auth/callback  -> vuelve de Google, crea la sesión
//   POST /api/auth/logout    -> borra la sesión
//   GET  /api/sync           -> { email, collection | null } de la cuenta
//   PUT  /api/sync           -> guarda { collection } en la cuenta
//
// Secretos (env): GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, SESSION_SECRET.
// KV: env.COLLECTIONS, una clave por usuario ("user:<sub de Google>").
// La sesión es una cookie HttpOnly firmada con HMAC (sin base de sesiones). Además
// se deja una cookie legible `mvp_user` (solo el email) para que la página sepa,
// sin pedir nada, si hay que sincronizar.

const GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth";
const GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token";
const SESSION_COOKIE = "mvp_session";
const HINT_COOKIE = "mvp_user";
const STATE_COOKIE = "mvp_oauth";
const SESSION_SECONDS = 180 * 24 * 3600;
const MAX_BODY_BYTES = 1024 * 1024;
const encoder = new TextEncoder();

function json(body, status = 200, headers = {}) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store", ...headers },
  });
}

function withCookies(response, cookies) {
  cookies.forEach((c) => response.headers.append("Set-Cookie", c));
  return response;
}

function cookie(name, value, { maxAge, httpOnly = false, secure }) {
  return `${name}=${value}; Path=/; SameSite=Lax; Max-Age=${maxAge}${httpOnly ? "; HttpOnly" : ""}${secure ? "; Secure" : ""}`;
}

function readCookies(request) {
  const out = {};
  (request.headers.get("Cookie") || "").split(/;\s*/).forEach((part) => {
    const i = part.indexOf("=");
    if (i > 0) out[part.slice(0, i)] = part.slice(i + 1);
  });
  return out;
}

const b64url = (bytes) => btoa(String.fromCharCode(...new Uint8Array(bytes))).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
const fromB64url = (s) => Uint8Array.from(atob(s.replace(/-/g, "+").replace(/_/g, "/")), (c) => c.charCodeAt(0));

function randomToken() {
  return Array.from(crypto.getRandomValues(new Uint8Array(16)), (b) => b.toString(16).padStart(2, "0")).join("");
}

function hmacKey(secret, usages) {
  return crypto.subtle.importKey("raw", encoder.encode(secret), { name: "HMAC", hash: "SHA-256" }, false, usages);
}

export async function signSession(payload, secret) {
  const body = b64url(encoder.encode(JSON.stringify(payload)));
  const sig = await crypto.subtle.sign("HMAC", await hmacKey(secret, ["sign"]), encoder.encode(body));
  return `${body}.${b64url(sig)}`;
}

async function verifySession(value, secret) {
  const [body, sig] = (value || "").split(".");
  if (!body || !sig) return null;
  try {
    const ok = await crypto.subtle.verify("HMAC", await hmacKey(secret, ["verify"]), fromB64url(sig), encoder.encode(body));
    if (!ok) return null;
    const payload = JSON.parse(new TextDecoder().decode(fromB64url(body)));
    return payload.exp > Date.now() / 1000 && payload.sub ? payload : null;
  } catch {
    return null;
  }
}

// Solo rutas del propio sitio ("/ludoteca.html"), nunca otra URL.
function safeNext(next) {
  return typeof next === "string" && /^\/(?![/\\])/.test(next) ? next : "/";
}

function authConfigured(env) {
  return Boolean(env && env.GOOGLE_CLIENT_ID && env.GOOGLE_CLIENT_SECRET && env.SESSION_SECRET);
}

const configError = () => json({ error: "server_config", message: "Falta configurar el inicio de sesión con Google en el servidor." }, 500);

function login(url, env) {
  if (!authConfigured(env)) return configError();
  const state = randomToken();
  const params = new URLSearchParams({
    client_id: env.GOOGLE_CLIENT_ID,
    redirect_uri: `${url.origin}/api/auth/callback`,
    response_type: "code",
    scope: "openid email",
    state,
    prompt: "select_account",
  });
  const response = new Response(null, { status: 302, headers: { Location: `${GOOGLE_AUTH_URL}?${params}` } });
  const value = `${state}.${encodeURIComponent(safeNext(url.searchParams.get("next")))}`;
  return withCookies(response, [cookie(STATE_COOKIE, value, { maxAge: 600, httpOnly: true, secure: url.protocol === "https:" })]);
}

async function callback(request, url, env) {
  if (!authConfigured(env)) return configError();
  const secure = url.protocol === "https:";
  const stored = readCookies(request)[STATE_COOKIE] || "";
  const dot = stored.indexOf("."); // el state es hexadecimal; lo que sigue es la ruta de vuelta
  const state = dot > 0 ? stored.slice(0, dot) : "";
  const back = safeNext(dot > 0 ? decodeURIComponent(stored.slice(dot + 1)) : "/");
  const clearState = cookie(STATE_COOKIE, "", { maxAge: 0, httpOnly: true, secure });
  const redirect = (location, cookies = []) => withCookies(new Response(null, { status: 302, headers: { Location: location } }), [clearState, ...cookies]);

  const code = url.searchParams.get("code");
  if (!state || url.searchParams.get("state") !== state || !code) return redirect(back); // cancelado o expirado

  const tokenResponse = await fetch(GOOGLE_TOKEN_URL, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({
      code,
      client_id: env.GOOGLE_CLIENT_ID,
      client_secret: env.GOOGLE_CLIENT_SECRET,
      redirect_uri: `${url.origin}/api/auth/callback`,
      grant_type: "authorization_code",
    }),
  });
  if (!tokenResponse.ok) return json({ error: "google_token", message: "Google no aceptó el inicio de sesión. Probá de nuevo." }, 502);
  const { id_token: idToken } = await tokenResponse.json();
  // El id_token llega directo de Google por TLS en este intercambio, así que no hace falta verificar la firma.
  let claims;
  try {
    claims = JSON.parse(new TextDecoder().decode(fromB64url(idToken.split(".")[1])));
  } catch {
    return json({ error: "google_token", message: "Respuesta inválida de Google." }, 502);
  }
  if (claims.aud !== env.GOOGLE_CLIENT_ID || !claims.sub || !claims.email || claims.email_verified === false) {
    return json({ error: "google_token", message: "No pude verificar tu cuenta de Google." }, 502);
  }

  const session = await signSession({ sub: claims.sub, email: claims.email, exp: Math.floor(Date.now() / 1000) + SESSION_SECONDS }, env.SESSION_SECRET);
  return redirect(back, [
    cookie(SESSION_COOKIE, session, { maxAge: SESSION_SECONDS, httpOnly: true, secure }),
    cookie(HINT_COOKIE, encodeURIComponent(claims.email), { maxAge: SESSION_SECONDS, secure }),
  ]);
}

function logout(url) {
  const secure = url.protocol === "https:";
  return withCookies(json({ ok: true }), [
    cookie(SESSION_COOKIE, "", { maxAge: 0, httpOnly: true, secure }),
    cookie(HINT_COOKIE, "", { maxAge: 0, secure }),
  ]);
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
  if (!authConfigured(env)) return configError();
  if (!env.COLLECTIONS) return json({ error: "server_config", message: "Falta el almacenamiento (KV) en el servidor." }, 500);
  const session = await verifySession(readCookies(request)[SESSION_COOKIE], env.SESSION_SECRET);
  if (!session) return json({ error: "unauthorized", message: "Iniciá sesión para sincronizar." }, 401);
  const key = `user:${session.sub}`;

  if (request.method === "GET") {
    const record = await env.COLLECTIONS.get(key, "json");
    return json({ email: session.email, collection: record ? record.collection : null });
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
  await env.COLLECTIONS.put(key, JSON.stringify({ email: session.email, collection, updatedAt: new Date().toISOString() }));
  return json({ ok: true, savedAt: collection.savedAt });
}

// Devuelve una Response si la ruta es de cuentas, o null para que siga el resto.
export async function handleAccount(request, env) {
  const url = new URL(request.url);
  const { pathname } = url;
  const { method } = request;
  if (pathname === "/api/auth/google" && method === "GET") return login(url, env);
  if (pathname === "/api/auth/callback" && method === "GET") return callback(request, url, env);
  if (pathname === "/api/auth/logout" && method === "POST") return logout(url);
  if (pathname === "/api/sync" && (method === "GET" || method === "PUT")) return sync(request, env);
  return null;
}
