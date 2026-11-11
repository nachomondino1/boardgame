// Helpers compartidos por ludoteca.html (Mi ludoteca), hoy.html y comprar.html.

// Google Analytics (GA4). Vive acá para cargarse una sola vez desde las 4 páginas;
// no mide en localhost para no ensuciar los datos con las pruebas.
(function () {
  const GA_ID = "G-6QMST63T71";
  if (["localhost", "127.0.0.1"].includes(location.hostname)) return;
  window.dataLayer = window.dataLayer || [];
  window.gtag = function () { window.dataLayer.push(arguments); };
  gtag("js", new Date());
  gtag("config", GA_ID);
  const s = document.createElement("script");
  s.async = true;
  s.src = `https://www.googletagmanager.com/gtag/js?id=${GA_ID}`;
  document.head.appendChild(s);
})();

function normalize(str) {
  return (str || "")
    .toString()
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase();
}

// Tramos de complejidad (peso de BGG, 1 a 5) y de duración (minutos): los comparten los filtros de
// ¿Cuál comprar? y el análisis de Mi ludoteca, para que digan lo mismo.
const BUCKETS_COMPLEJIDAD = [
  { id: "liviano", label: "Liviano", hint: "menos de 2", match: (c) => c < 2 },
  { id: "medio", label: "Medio", hint: "2 a 3", match: (c) => c >= 2 && c < 3 },
  { id: "pesado", label: "Pesado", hint: "3 o más", match: (c) => c >= 3 },
];

const BUCKETS_DURACION = [
  { id: "30", label: "Hasta 30 min", match: (d) => d <= 30 },
  { id: "60", label: "31 a 60 min", match: (d) => d > 30 && d <= 60 },
  { id: "120", label: "61 a 120 min", match: (d) => d > 60 && d <= 120 },
  { id: "mas", label: "Más de 2 horas", match: (d) => d > 120 },
];

// --- Búsqueda por nombre ---
// Se busca en el nombre principal y en los alternativos de BGG (traducciones, ediciones: "Caza Bombas"
// es "Bomb Busters"). Los alternativos vienen de names.json, que se pide recién cuando alguien busca.
// Además se compara ignorando espacios y signos: "cazabombas" encuentra "Caza Bombas".

function compactText(str) {
  return normalize(str).replace(/[^a-z0-9]/g, "");
}

function makeQuery(text) {
  return { norm: normalize(text.trim()), compact: compactText(text) };
}

function textKey(text) {
  return { text, norm: normalize(text), compact: compactText(text) };
}

function keyMatches(key, q) {
  return key.norm.includes(q.norm) || (q.compact.length >= 3 && key.compact.includes(q.compact));
}

// "Alt 1|Alt 2" (como viene en names.json) -> [{ text, norm, compact }]
function parseAlts(altString) {
  return altString ? altString.split("|").map(textKey) : [];
}

const altByGame = new Map(); // bgg_id -> [{ text, norm, compact }]
let altPromise = null;

function ensureAltNames() {
  if (!altPromise) {
    altPromise = fetch("data/names.json")
      .then((r) => {
        if (!r.ok) throw new Error(`names.json: HTTP ${r.status}`);
        return r.json();
      })
      .then(({ rows }) => {
        rows.forEach(([id, , alt]) => { if (alt) altByGame.set(id, parseAlts(alt)); });
      })
      .catch(() => { altPromise = null; }); // sin alternativos, se sigue buscando por el nombre principal
  }
  return altPromise;
}

let lastQuery = { text: null, q: null };

// ¿El juego (de index.json) coincide con lo escrito en el buscador?
function matchesNombre(g, text) {
  if (lastQuery.text !== text) lastQuery = { text, q: makeQuery(text) };
  const q = lastQuery.q;
  if (!g._nk) g._nk = textKey(g.nombre);
  if (keyMatches(g._nk, q)) return true;
  const alts = altByGame.get(g.bgg_id);
  return !!alts && alts.some((a) => keyMatches(a, q));
}

function jugBestRange(g) {
  if (g.jug_best_min == null && g.jug_best_max == null) return null;
  const lo = g.jug_best_min != null ? g.jug_best_min : g.jug_best_max;
  const hi = g.jug_best_max != null ? g.jug_best_max : g.jug_best_min;
  return [lo, hi];
}

function matchesJugBest(g, n) {
  if (n == null) return false;
  const range = jugBestRange(g);
  if (!range) return false;
  return n >= range[0] && n <= range[1];
}

function estadoBadgeClass(estado) {
  switch (estado) {
    case "Own": return "badge-own";
    case "Watchlist": return "badge-watch";
    case "Want to buy": return "badge-buy";
    case "Descartado": return "badge-descartado";
    default: return "badge-other";
  }
}

function complexityColor(c) {
  if (c == null) return "#9a9a9a";
  const clamped = Math.max(0, Math.min(5, c));
  const hue = 120 - (clamped / 5) * 120;
  return `hsl(${hue}, 62%, 42%)`;
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str || "";
  return div.innerHTML;
}

// --- Datos del MVP (ver MVP.md) ---
// El índice trae lo necesario para filtrar y ordenar los ~28.000 juegos; la
// ficha completa (imagen, editorial, links, mecánicas...) vive en
// games/NNN.json y se pide solo para lo que se muestra (hydrate).
// `estado` y `mi_puntaje` no vienen en los datos: salen de la colección del
// visitante, guardada en el navegador.

const COLLECTION_KEY = "mvp.collection";

function emptyCollection() {
  return { source: null, user: null, savedAt: null, games: {} };
}

// localStorage puede fallar (ventana privada, datos bloqueados): la página
// tiene que seguir funcionando, solo que sin recordar la colección.
function loadCollection() {
  try {
    const stored = JSON.parse(localStorage.getItem(COLLECTION_KEY));
    if (stored && stored.games) return stored;
  } catch (e) { /* sin colección guardada */ }
  return emptyCollection();
}

// Devuelve false si no se pudo guardar (queda solo en memoria de esta página).
function saveCollection(collection) {
  collection.savedAt = new Date().toISOString();
  try {
    localStorage.setItem(COLLECTION_KEY, JSON.stringify(collection));
    return true;
  } catch (e) {
    return false;
  }
}

// Misma regla que estado_de() en construct_data.py: Own > Prev. owned >
// Want to buy, y Watchlist para todo lo que no está marcado.
function estadoDe(entry) {
  if (entry && entry.own) return "Own";
  if (entry && entry.prevowned) return "Prev. owned";
  if (entry && entry.wanttobuy) return "Want to buy";
  return "Watchlist";
}

function loadGames() {
  const collection = loadCollection().games;
  return fetch("data/index.json")
    .then((r) => {
      if (!r.ok) throw new Error(`index.json: HTTP ${r.status}`);
      return r.json();
    })
    .then(({ cols, rows }) =>
      rows.map((row) => {
        const g = {};
        cols.forEach((c, i) => { g[c] = row[i]; });
        g._tramo = g.tramo;
        delete g.tramo;
        g.bgg_url = `https://boardgamegeek.com/boardgame/${g.bgg_id}`;
        const entry = collection[g.bgg_id];
        g.estado = estadoDe(entry);
        g.mi_puntaje = entry && entry.rating != null ? entry.rating : null;
        return g;
      })
    );
}

// Vuelve a calcular estado y mi_puntaje de los juegos ya cargados (después de
// que el visitante cambió su colección), sin volver a pedir datos.
function applyCollection(games) {
  const collection = loadCollection().games;
  games.forEach((g) => {
    const entry = collection[g.bgg_id];
    g.estado = estadoDe(entry);
    g.mi_puntaje = entry && entry.rating != null ? entry.rating : null;
  });
}

const shardCache = new Map();

function loadShard(tramo) {
  if (!shardCache.has(tramo)) {
    shardCache.set(
      tramo,
      fetch(`data/games/${String(tramo).padStart(3, "0")}.json`).then((r) => {
        if (!r.ok) throw new Error(`tramo ${tramo}: HTTP ${r.status}`);
        return r.json();
      })
    );
  }
  return shardCache.get(tramo);
}

// Completa con la ficha (imagen, editorial, links...) los juegos de la lista que
// todavía no la tienen. Devuelve cuántos completó, para que la página vuelva a
// dibujarse solo si hubo algo nuevo. Si un tramo falla, esos juegos quedan sin
// ficha (tarjeta sin imagen) y no se reintenta en bucle.
function hydrate(list) {
  const pending = list.filter((g) => !g._hydrated);
  const tramos = [...new Set(pending.map((g) => g._tramo))];
  return Promise.all(tramos.map((t) => loadShard(t).catch(() => null))).then((shards) => {
    const byTramo = new Map(tramos.map((t, i) => [t, shards[i]]));
    pending.forEach((g) => {
      const ficha = byTramo.get(g._tramo) && byTramo.get(g._tramo)[g.bgg_id];
      if (ficha) Object.assign(g, ficha);
      g._hydrated = true;
    });
    return pending.length;
  });
}

// Colapsa una lista ya filtrada/ordenada: la primera aparición de cada
// grupo (la de mejor orden, porque la lista ya viene ordenada) se queda
// como representante de la tarjeta; el resto de sus variantes se cuelgan
// adentro en vez de ocupar su propia fila en la grilla. `g.grupo` ya viene
// calculado en data.json (ver construct_data.py / data/grupos.json).
function collapseGrupos(list) {
  const representantes = new Map(); // nombre del grupo -> entry
  const result = [];
  list.forEach((g) => {
    const grupoNombre = g.grupo;
    if (!grupoNombre) {
      result.push({ game: g, variantes: [], grupoNombre: null });
      return;
    }
    if (representantes.has(grupoNombre)) {
      representantes.get(grupoNombre).variantes.push(g);
    } else {
      const entry = { game: g, variantes: [], grupoNombre };
      representantes.set(grupoNombre, entry);
      result.push(entry);
    }
  });
  return result;
}


function cardTemplate(g, opts) {
  opts = opts || {};
  const esBest = opts.jugadores != null && matchesJugBest(g, opts.jugadores);
  const jugRange = g.jug_min != null && g.jug_max != null
    ? (g.jug_min === g.jug_max ? `${g.jug_min}` : `${g.jug_min}–${g.jug_max}`)
    : "?";
  const jugBest = jugBestRange(g);
  const jugBestLabel = jugBest ? (jugBest[0] === jugBest[1] ? `${jugBest[0]}` : `${jugBest[0]}–${jugBest[1]}`) : null;
  const complejidadHtml = g.complejidad != null
    ? `<span class="complexity-pill" style="background:${complexityColor(g.complejidad)}">${g.complejidad.toFixed(1)}</span>`
    : `<span class="tag">complejidad ?</span>`;

  const variantes = opts.variantes || [];
  const variantesHtml = variantes.length
    ? `<details class="variantes">
        <summary>${variantes.length} variante${variantes.length === 1 ? "" : "s"} más de ${escapeHtml(opts.grupoNombre)}</summary>
        <ul>${variantes
          .map((v) => `<li>${v.bgg_url
            ? `<a href="${escapeHtml(v.bgg_url)}" target="_blank" rel="noopener">${escapeHtml(v.nombre)}</a>`
            : escapeHtml(v.nombre)}</li>`)
          .join("")}</ul>
      </details>`
    : "";

  const nombreHtml = g.bgg_url
    ? `<a class="card-title-link" href="${escapeHtml(g.bgg_url)}" target="_blank" rel="noopener">${escapeHtml(g.nombre)}</a>`
    : escapeHtml(g.nombre);

  const bestBadge = esBest
    ? `<span class="badge badge-best">👥 Best con ${opts.jugadores}</span>`
    : "";

  // link_cazagangas/cazagangas_status ya vienen resueltos desde
  // check_cazagangas_links.py + integrate_data.py: solo se muestra cuando
  // sabemos que el link responde 200 (no uno armado a ciegas que puede
  // dar 404 — ver DATA_PLAYBOOK.md).
  const cazagangasHtml = opts.showCazagangas && g.cazagangas_status === "200"
    ? `<a class="stat stat-link" href="${escapeHtml(g.link_cazagangas)}" target="_blank" rel="noopener">💰 Cazagangas ↗</a>`
    : "";

  // precio_ref_usd: mediana de publicaciones recientes del marketplace de BGG
  // (en USD, nuevos o como nuevos) — referencia del exterior, no un precio local.
  const precioRefHtml = opts.showPrecioRef && g.precio_ref_usd != null
    ? `<span class="stat" title="Mediana de publicaciones recientes en el marketplace de BGG (USD)">💵 Ref. USD ~$${Math.round(g.precio_ref_usd).toLocaleString("es-AR")}</span>`
    : "";

  const compraHtml = (g.costo != null || g.precio_calidad != null || g.link_tienda || cazagangasHtml || precioRefHtml)
    ? `
      <div class="stat-row">
        ${g.costo != null ? `<span class="stat">💰 $${g.costo.toLocaleString("es-AR")}</span>` : ""}
        ${g.precio_calidad != null ? `<span class="stat">Precio/calidad: ${g.precio_calidad.toFixed(2)}</span>` : ""}
        ${g.link_tienda ? `<a class="stat stat-link" href="${escapeHtml(g.link_tienda)}" target="_blank" rel="noopener">Tienda ↗</a>` : ""}
        ${precioRefHtml}
        ${cazagangasHtml}
      </div>`
    : "";

  const imagenHtml = g.imagen
    ? `<img class="card-thumb" src="${escapeHtml(g.imagen)}" alt="" loading="lazy" width="56" height="56" onerror="this.remove()">`
    : "";

  return `
    <div class="card">
      <div class="card-title-row">
        ${imagenHtml}
        <div class="card-title-text">
          <div class="card-title">${nombreHtml}</div>
          <div class="card-sub">${escapeHtml(g.modo || "")}${g.anio ? " · " + g.anio : ""}</div>
          ${g.publisher_principal ? `<div class="card-publisher">${escapeHtml(g.publisher_principal)}</div>` : ""}
        </div>
        <span class="badge ${estadoBadgeClass(g.estado)}">${escapeHtml(g.estado || "?")}</span>
      </div>
      <div class="stat-row">
        <span class="stat">👥 ${jugRange}${jugBestLabel ? ` (mejor: ${jugBestLabel})` : ""}</span>
        <span class="stat">⏱ ${g.duracion != null ? g.duracion + " min" : "?"}</span>
        <span class="stat">⚙️ ${complejidadHtml}</span>
      </div>
      <div class="stat-row">
        <span class="stat">BGG: ${g.puntaje_bgg != null ? g.puntaje_bgg.toFixed(2) : "?"}${g.reviews_bgg != null ? ` (${Number(g.reviews_bgg).toLocaleString("es-AR")} reviews)` : ""}</span>
        <span class="stat">Ranking BGG: ${g.ranking_bgg != null ? "#" + Number(g.ranking_bgg).toLocaleString("es-AR") : "?"}</span>
        ${g.mi_puntaje != null ? `<span class="stat">Mi puntaje: ${g.mi_puntaje}/10</span>` : ""}
      </div>
      ${bestBadge ? `<div class="stat-row">${bestBadge}</div>` : ""}
      ${compraHtml}
      ${variantesHtml}
    </div>
  `;
}

function navTemplate(active) {
  // "Inicio" solo se ve en mobile (en desktop el logo ya lleva a la landing).
  const links = [
    { href: "index.html", emoji: "🏠", label: "Inicio", cls: "nav-home" },
    { href: "ludoteca.html", emoji: "📚", label: "Mi ludoteca" },
    { href: "hoy.html", emoji: "🎲", label: "¿Qué jugamos hoy?" },
    { href: "comprar.html", emoji: "🛒", label: "¿Cuál comprar?" },
  ];
  const linksHtml = links
    .map((l) => `<a href="${l.href}" class="${[l.cls, l.href === active ? "active" : ""].filter(Boolean).join(" ")}">${l.emoji} ${l.label}</a>`)
    .join("");
  return `
    <div class="top-nav">
      <a href="index.html" class="nav-brand">🎲 Juegos de mesa</a>
      <div class="nav-links">${linksHtml}</div>
    </div>
  `;
}

// Fecha de la última actualización de los datos de BGG, en el pie de cada página (data/meta.json,
// que genera build_catalog.py). Si no se puede leer, el pie queda como estaba.
function showDataStamp() {
  const footers = document.querySelectorAll(".site-footer");
  if (!footers.length) return;
  fetch("data/meta.json")
    .then((r) => (r.ok ? r.json() : null))
    .then((meta) => {
      if (!meta || !meta.actualizado) return;
      const [y, m, d] = meta.actualizado.split("-").map(Number);
      const fecha = new Date(y, m - 1, d).toLocaleDateString("es-AR", { day: "numeric", month: "long", year: "numeric" });
      const cobertura = meta.juegos_actualizados < meta.juegos_total
        ? `${meta.juegos_actualizados.toLocaleString("es-AR")} de ${meta.juegos_total.toLocaleString("es-AR")} juegos al día; el resto viene de una copia de BGG de 2025. `
        : "";
      const html = `<p class="data-stamp"><strong>Datos de BGG actualizados el ${fecha}.</strong><br>${cobertura}El ranking y los puntajes cambian en cada actualización.</p>`;
      footers.forEach((f) => f.insertAdjacentHTML("afterbegin", html));
    })
    .catch(() => {});
}

showDataStamp();
