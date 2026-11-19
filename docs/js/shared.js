// Helpers compartidos por ludoteca.html (Mi ludoteca), hoy.html y comprar.html.

// GoatCounter (sin cookies). Vive acá para cargarse una sola vez desde las 4 páginas;
// no mide en localhost para no ensuciar los datos con las pruebas.
(function () {
  if (["localhost", "127.0.0.1"].includes(location.hostname)) return;
  const s = document.createElement("script");
  s.async = true;
  s.dataset.goatcounter = "https://boardgames.goatcounter.com/count";
  s.src = "https://gc.zgo.at/count.js";
  document.head.appendChild(s);
})();

function normalize(str) {
  return (str || "")
    .toString()
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase();
}

// Búsqueda en Mercado Libre Argentina: "<nombre> juego de mesa". Va en lugar del link a Cazagangas cuando ese no existe.
function mercadoLibreUrl(nombre) {
  const slug = normalize(`${nombre} juego de mesa`).replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "");
  return `https://listado.mercadolibre.com.ar/${slug}`;
}

// Tramos de complejidad (peso de BGG, 1 a 5) y de duración (minutos): los comparten los filtros de
// ¿Cuál comprar? y el análisis de Mi ludoteca, para que digan lo mismo.
// Los cinco niveles de peso que usa BGG (Light, Medium Light, Medium, Medium Heavy, Heavy).
const BUCKETS_COMPLEJIDAD = [
  { id: "liviano", label: "Liviano", hint: "menos de 1,8", match: (c) => c < 1.8 },
  { id: "medio-liviano", label: "Medio liviano", hint: "1,8 a 2,6", match: (c) => c >= 1.8 && c < 2.6 },
  { id: "medio", label: "Medio", hint: "2,6 a 3,4", match: (c) => c >= 2.6 && c < 3.4 },
  { id: "medio-pesado", label: "Medio pesado", hint: "3,4 a 4,2", match: (c) => c >= 3.4 && c < 4.2 },
  { id: "pesado", label: "Pesado", hint: "4,2 o más", match: (c) => c >= 4.2 },
];

const BUCKETS_DURACION = [
  { id: "30", label: "Hasta 30 min", match: (d) => d <= 30 },
  { id: "60", label: "31 a 60 min", match: (d) => d > 30 && d <= 60 },
  { id: "120", label: "61 a 120 min", match: (d) => d > 60 && d <= 120 },
  { id: "mas", label: "Más de 2 horas", match: (d) => d > 120 },
];

// Precio estimado en pesos: mediana de publicaciones del marketplace de BGG (USD, solo ~1 de cada 5 juegos)
// × dólar oficial del día × PRECIO_MULT. El multiplicador sale de comparar 16 juegos con su precio más barato en
// Cazagangas (nov 2026, dólar oficial $1.580): mediana 2,56; la mitad central va de 1,5 a 3,2. Es una estimación
// gruesa (error típico ~25%, a veces más del doble): sirve para ubicarse, no para presupuestar. Ver DATA_PLAYBOOK.md.
const PRECIO_MULT = 2.5;
const DOLAR_FALLBACK = 1580; // si la API del dólar no responde y no hay uno guardado
const DOLAR_KEY = "dolar.oficial";
const DOLAR_TTL_MS = 60 * 60 * 1000;
let dolarHoy = DOLAR_FALLBACK;
let dolarFecha = null; // "AAAA-MM-DD" de la última actualización del dólar, si se sabe

// Dólar oficial (venta) de dolarapi.com, guardado 1 hora en el navegador. Devuelve true si el valor cambió.
function loadDolar() {
  let guardado = null;
  try { guardado = JSON.parse(localStorage.getItem(DOLAR_KEY)); } catch (e) { /* sin storage */ }
  if (guardado && guardado.valor > 0) { dolarHoy = guardado.valor; dolarFecha = guardado.fecha || null; }
  if (guardado && Date.now() - guardado.at < DOLAR_TTL_MS) return Promise.resolve(false);
  return fetch("https://dolarapi.com/v1/dolares/oficial")
    .then((r) => (r.ok ? r.json() : null))
    .then((d) => {
      if (!d || !(d.venta > 0)) return false;
      const fecha = d.fechaActualizacion ? String(d.fechaActualizacion).slice(0, 10) : null;
      const cambio = d.venta !== dolarHoy || fecha !== dolarFecha;
      dolarHoy = d.venta;
      dolarFecha = fecha;
      try { localStorage.setItem(DOLAR_KEY, JSON.stringify({ valor: d.venta, at: Date.now(), fecha })); } catch (e) { /* sin storage */ }
      return cambio;
    })
    .catch(() => false);
}

// Pesos estimados, redondeados a los 5 mil más cercanos.
function precioArsEstimado(usd) {
  return Math.max(5000, Math.round((usd * dolarHoy * PRECIO_MULT) / 5000) * 5000);
}

function formatArsEstimado(usd) {
  return `~$${Math.round(precioArsEstimado(usd) / 1000).toLocaleString("es-AR")} mil`;
}

// Día del precio de Cazagangas más reciente (data/meta.json, la pone cada página que lo muestra).
let fechaPreciosCazagangas = null;

// Precio en pesos de un juego: el real (el más barato hoy en Cazagangas, `precio_ars`) si lo tiene; si no, el
// estimado a partir del marketplace de BGG. null si no hay ninguno. `real` distingue uno del otro.
function precioDe(g) {
  if (g.precio_ars != null) return { valor: g.precio_ars, real: true };
  if (g.precio_ref_usd != null) return { valor: precioArsEstimado(g.precio_ref_usd), real: false };
  return null;
}

function fechaLargaCorta(iso) {
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(y, m - 1, d).toLocaleDateString("es-AR", { day: "numeric", month: "long" });
}

// Redondeado a miles, sin falsa precisión. Real: "$159 mil". Estimado: "~$295 mil" (el ~ avisa que no es un precio de tienda).
function formatPrecio(p) {
  return `${p.real ? "" : "~"}$${Math.round(p.valor / 1000).toLocaleString("es-AR")} mil`;
}

// Tramos del filtro de Precio, sobre el precio estimado en pesos (solo los juegos con precio de referencia).
const BUCKETS_PRECIO = [
  { id: "50", label: "Hasta $50 mil", match: (ars) => ars <= 50000 },
  { id: "100", label: "$50 a 100 mil", match: (ars) => ars > 50000 && ars <= 100000 },
  { id: "200", label: "$100 a 200 mil", match: (ars) => ars > 100000 && ars <= 200000 },
  { id: "mas", label: "Más de $200 mil", match: (ars) => ars > 200000 },
];

// Emoji por tipo de juego (no repite ⚔️ comparar, 👥 jugadores ni 🏆 ranking).
const MODO_EMOJI = {
  "Competitivo": "🏁",
  "Cooperativo": "🤝",
  "Equipos": "🆚",
  "Cooperativo y competitivo": "🤝🏁",
};

function modoLabel(modo) {
  return MODO_EMOJI[modo] ? `${MODO_EMOJI[modo]} ${modo}` : modo;
}

// Mecánicas clave (nombres cortos): vienen en index.json, en el mismo orden con que build_catalog.py numera
// la columna "mecs" de cada juego.
let MECANICAS_VOCAB = [];

function mecanicasClave(g, max = 3) {
  return (g.mecs || []).slice(0, max).map((i) => MECANICAS_VOCAB[i]).filter(Boolean);
}

const BUCKETS_DECADA = [
  { id: "2020", label: "2020s", match: (a) => a >= 2020 },
  { id: "2010", label: "2010s", match: (a) => a >= 2010 && a < 2020 },
  { id: "2000", label: "2000s", match: (a) => a >= 2000 && a < 2010 },
  { id: "1990", label: "1990s", match: (a) => a >= 1990 && a < 2000 },
  { id: "antes", label: "Antes de 1990", match: (a) => a < 1990 },
];

// Ordena una lista de juegos por una clave "campo_asc" o "campo_desc" (ej. "ranking_bgg_asc"); los que no tienen el dato van al final.
function sortGames(list, sortKey) {
  const dir = sortKey.endsWith("_asc") ? 1 : -1;
  const field = sortKey.replace(/_(asc|desc)$/, "");
  return [...list].sort((a, b) => {
    const av = a[field];
    const bv = b[field];
    if (av == null && bv == null) return 0;
    if (av == null) return 1;
    if (bv == null) return -1;
    return av < bv ? dir * -1 : av > bv ? dir : 0;
  });
}

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
// Want to buy > Want to play, y Watchlist para todo lo que no está marcado.
function estadoDe(entry) {
  if (entry && entry.own) return "Own";
  if (entry && entry.prevowned) return "Prev. owned";
  if (entry && entry.wanttobuy) return "Want to buy";
  if (entry && entry.wanttoplay) return "Want to play";
  return "Watchlist";
}

function loadGames() {
  const collection = loadCollection().games;
  return fetch("data/index.json")
    .then((r) => {
      if (!r.ok) throw new Error(`index.json: HTTP ${r.status}`);
      return r.json();
    })
    .then(({ cols, rows, mecanicas }) => {
      MECANICAS_VOCAB = mecanicas || [];
      return rows.map((row) => {
        const g = {};
        cols.forEach((c, i) => { g[c] = row[i]; });
        g._tramo = g.tramo;
        delete g.tramo;
        g.bgg_url = `https://boardgamegeek.com/boardgame/${g.bgg_id}`;
        const entry = collection[g.bgg_id];
        g.estado = estadoDe(entry);
        g.quiere_probar = !!(entry && entry.wanttoplay);
        g.mi_puntaje = entry && entry.rating != null ? entry.rating : null;
        return g;
      });
    });
}

// Vuelve a calcular estado y mi_puntaje de los juegos ya cargados (después de
// que el visitante cambió su colección), sin volver a pedir datos.
function applyCollection(games) {
  const collection = loadCollection().games;
  games.forEach((g) => {
    const entry = collection[g.bgg_id];
    g.estado = estadoDe(entry);
    g.quiere_probar = !!(entry && entry.wanttoplay);
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

  // link_cazagangas/cazagangas_status ya vienen resueltos desde
  // check_cazagangas_links.py + integrate_data.py: solo se muestra cuando
  // sabemos que el link responde 200 (no uno armado a ciegas que puede
  // dar 404 — ver DATA_PLAYBOOK.md).
  const cazagangasHtml = opts.showCazagangas && g.cazagangas_status === "200"
    ? `<a class="stat stat-link" href="${escapeHtml(g.link_cazagangas)}" target="_blank" rel="noopener">💰 Cazagangas ↗</a>`
    : "";
  // Mercado Libre (MELI) va siempre: aunque esté en Cazagangas, ahí se ve si se consigue más barato.
  const meliHtml = opts.showCazagangas && g.nombre
    ? `<a class="stat stat-link" href="${escapeHtml(mercadoLibreUrl(g.nombre))}" target="_blank" rel="noopener" title="Buscar en Mercado Libre">🟡 MELI ↗</a>`
    : "";

  // Precio en pesos: el real de Cazagangas si lo tiene (precio_ars) y, si no, el estimado desde el marketplace
  // de BGG (precio_ref_usd, USD, solo nuevos) — ver precioDe() y PRECIO_MULT.
  const precio = opts.showPrecioRef ? precioDe(g) : null;
  const precioTitulo = !precio ? "" : precio.real
    ? `Precio más barato hoy en Cazagangas, entre las tiendas argentinas que lo tienen${fechaPreciosCazagangas ? ` (actualizado el ${fechaLargaCorta(fechaPreciosCazagangas)})` : ""}.`
    : `Precio ESTIMADO en Argentina: mediana del marketplace de BGG (US$${Math.round(g.precio_ref_usd)}) × dólar oficial × ${PRECIO_MULT} por importación e impuestos. Es una referencia gruesa, puede errar por ±25% o más.`;
  const precioRefHtml = precio
    ? `<span class="stat" title="${escapeHtml(precioTitulo)}">💵 ${formatPrecio(precio)}</span>`
    : "";

  // Búsqueda de reseñas en YouTube con el nombre principal (el que usan los canales).
  const youtubeUrl = `https://www.youtube.com/results?search_query=${encodeURIComponent(`${g.nombre} board game review`)}`;
  const youtubeHtml = g.nombre
    ? `<a class="stat stat-link" href="${escapeHtml(youtubeUrl)}" target="_blank" rel="noopener" title="Buscar reseñas en YouTube">▶ Reviews ↗</a>`
    : "";

  const compraHtml = (cazagangasHtml || meliHtml || precioRefHtml || youtubeHtml)
    ? `
      <div class="stat-row">
        ${precioRefHtml}
        ${cazagangasHtml}
        ${meliHtml}
        ${youtubeHtml}
      </div>`
    : "";

  // Mientras llega la ficha (imagen) se reserva el lugar de la imagen, así la card no se reacomoda; al cargar, aparece con un fundido.
  const imagenHtml = g.imagen
    ? `<span class="card-thumb-box" style="--thumb:url('${escapeHtml(g.imagen)}')"><img class="card-thumb" src="${escapeHtml(g.imagen)}" alt="" loading="lazy" decoding="async" onload="this.classList.add('is-ready');var r=this.naturalWidth/this.naturalHeight;if(r<0.85||r>1.18)this.parentNode.classList.add('is-fit')" onerror="this.classList.add('is-ready')"></span>`
    : `<div class="card-thumb card-thumb--vacio" aria-hidden="true"></div>`;
  const reviewsTxt = g.reviews_bgg != null ? `${Number(g.reviews_bgg).toLocaleString("es-AR")} reviews` : "";
  const rankingTxt = g.ranking_bgg != null ? `Ranking BGG #${Number(g.ranking_bgg).toLocaleString("es-AR")}` : "";

  return `
    <div class="card" data-id="${escapeHtml(String(g.bgg_id ?? ""))}">
      <div class="card-headline">
        <div class="card-title">${g.ranking_bgg != null ? `<span class="card-rank" title="${escapeHtml(rankingTxt)}">#${Number(g.ranking_bgg).toLocaleString("es-AR")}</span> ` : ""}${nombreHtml}${g.anio ? ` <span class="card-year">(${g.anio})</span>` : ""}</div>
        <span class="card-rating" title="${escapeHtml([reviewsTxt, rankingTxt].filter(Boolean).join(" · "))}"><span>⭐ <b>${g.puntaje_bgg != null ? g.puntaje_bgg.toFixed(2) : "?"}</b></span>${g.reviews_bgg != null ? `<span class="stat-reviews">${Number(g.reviews_bgg).toLocaleString("es-AR")} reviews</span>` : ""}</span>
      </div>
      <div class="card-top">
        <div class="card-left">${imagenHtml}</div>
        <div class="card-main">
          <div class="card-meta">
            ${g.estado && g.estado !== "Watchlist" ? `<span class="badge card-estado ${estadoBadgeClass(g.estado)}">${escapeHtml(g.estado)}</span>` : ""}
            <span class="card-sub">${[g.modo ? modoLabel(g.modo) : null, g.publisher_principal].filter(Boolean).map(escapeHtml).join(" · ")}</span>
            ${opts.showComparar ? `<button type="button" class="card-compare-btn" data-compare="${escapeHtml(String(g.bgg_id))}" title="Comparar" aria-label="Comparar ${escapeHtml(g.nombre)}">⚔️</button>` : ""}
          </div>
          ${mecanicasClave(g).length ? `<div class="card-mecs" title="${escapeHtml((g.mecanicas || []).join(" · "))}">${mecanicasClave(g).map(escapeHtml).join(" · ")}</div>` : ""}
          <div class="stat-row">
            <span class="stat" title="Cantidad de jugadores que indica la caja">👥 ${jugRange}</span>
            ${jugBestLabel ? `<span class="stat${esBest ? " stat-best" : ""}" title="Cantidad ideal de jugadores, según la comunidad de BGG">🎯 Ideal ${jugBestLabel}</span>` : ""}
            <span class="stat">⏱ ${g.duracion != null ? g.duracion + " min" : "?"}</span>
            <span class="stat">⚙️ ${complejidadHtml}</span>
          </div>
          ${compraHtml}
        </div>
      </div>
      ${variantesHtml}
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

// Títulos largos: se achica la letra hasta entrar en la fila (mínimo 12px); si aun así no entra, queda el "…".
// Se mide todo junto (una lectura y una escritura) en vez de card por card, para no forzar un re-layout por título.
function fitCardTitles() {
  const titulos = [...document.querySelectorAll(".card-headline .card-title")];
  titulos.forEach((el) => { el.style.fontSize = ""; });
  const medidas = titulos.map((el) => ({ el, ancho: el.clientWidth, texto: el.scrollWidth, fuente: parseFloat(getComputedStyle(el).fontSize) }));
  medidas.forEach(({ el, ancho, texto, fuente }) => {
    if (texto > ancho) el.style.fontSize = Math.max(12, Math.floor((fuente * ancho / texto) * 2) / 2) + "px";
  });
}

{
  let pending = false;
  const schedule = () => {
    if (pending) return;
    pending = true;
    requestAnimationFrame(() => { pending = false; fitCardTitles(); });
  };
  // Solo se mira la lista de cards (no todo el documento), y solo cuando cambian sus hijos.
  document.addEventListener("DOMContentLoaded", () => {
    const lista = document.getElementById("grid");
    if (lista) new MutationObserver(schedule).observe(lista, { childList: true, subtree: true });
  });
  window.addEventListener("resize", schedule);
  if (document.fonts && document.fonts.ready) document.fonts.ready.then(schedule);
}

// Pie de página común: contacto + "conocé más" + copyright, debajo del logo de BGG que ya trae cada página.
// Los datos de contacto se arman por partes para que no aparezcan enteros en el código.
const FOOTER_CONTACTO = [
  { label: "Email", href: "mailto:" + ["nachomondino1", "gmail.com"].join("@") },
  { label: "WhatsApp", href: "https://wa.me/" + ["54", "9", "1165848574"].join("") },
];
const FOOTER_CONOCE_MAS = [
  { label: "GitHub", href: "https://github.com/nachomondino1" },
  { label: "LinkedIn", href: "https://www.linkedin.com/in/ignacio-mondino" },
  { label: "Portfolio", href: "https://nachomondino1.github.io/portfolio/" },
];

function mountFooterExtras() {
  const links = (list) => list
    .map((l) => `<a href="${escapeHtml(l.href)}" target="_blank" rel="noopener">${escapeHtml(l.label)}</a>`)
    .join('<span aria-hidden="true">·</span>');
  const html = `
    <nav class="site-footer__links" aria-label="Contacto">
      <span>¿Dudas o ideas? Escribime:</span> ${links(FOOTER_CONTACTO)}
    </nav>
    <nav class="site-footer__links site-footer__links--soft" aria-label="Más sobre mí">
      <span>Conocé más:</span> ${links(FOOTER_CONOCE_MAS)}
    </nav>
    <p class="site-footer__copy">© ${new Date().getFullYear()} Juegos de mesa</p>`;
  document.querySelectorAll(".site-footer").forEach((f) => f.insertAdjacentHTML("beforeend", html));
}

mountFooterExtras();

// Definiciones cortas de las mecánicas del filtro (una por nombre de MECANICAS_VOCAB): tooltip en cada opción del
// filtro de ¿Cuál comprar? y en la card de mecánicas del análisis, más la lista "¿Qué es cada una?".
const MECANICAS_HINT = {
  "Worker Placement": "Mandás trabajadores a espacios del tablero para hacer acciones; si un rival ocupa uno, no lo podés usar.",
  "Deck Building": "Empezás con un mazo básico y sumás cartas durante la partida para mejorarlo.",
  "Area Control": "Competís por dominar zonas del tablero, que dan puntos, recursos o ventajas.",
  "Tile Placement": "Colocás losetas para formar un mapa o estructura; dónde las ponés condiciona lo que sigue.",
  "Route Building": "Construís rutas o conexiones entre puntos del tablero.",
  "Drafting": "Elegís una carta de varias y pasás el resto al siguiente jugador.",
  "Auction": "Los jugadores pujan para quedarse con algo.",
  "Trick-taking": "Cada uno juega una carta por ronda y gana la baza quien juega la mejor.",
  "Set Collection": "Juntás grupos de elementos (iguales, variados o combinados) para puntuar.",
  "Pick-up & Deliver": "Recogés algo en un lugar y lo llevás a otro para cumplir pedidos.",
  "Push Your Luck": "Decidís si seguir arriesgando por más premio o frenar y asegurar lo logrado.",
  "Hand Management": "Administrás con cuidado las cartas de tu mano: cuándo jugarlas o guardarlas.",
  "Dice Rolling": "Los dados determinan resultados; muchos juegos dejan repetir o modificar tiradas.",
  "Pattern Building": "Combinás piezas, colores o símbolos para formar patrones que dan puntos.",
  "Trading": "Intercambiás recursos o cartas con los otros jugadores.",
  "Deduction": "Juntás pistas y descartás posibilidades para descubrir algo oculto.",
  "Memory": "Hay que recordar posiciones, cartas o información que ya se vio.",
  "Voting": "Los jugadores votan para decidir algo.",
  "Bluffing": "Podés mentir sobre tus cartas o intenciones; los demás deciden si creerte.",
  "Take That": "Acciones directas para fastidiar a un rival: robarle, atacarlo, quitarle cosas.",
  "Storytelling": "El juego va armando una historia entre todos, con narración o imaginación.",
  "Role Playing": "Cada jugador encarna un personaje que evoluciona durante la partida.",
  "Campaign": "Partidas conectadas: lo que pasa en una afecta a las siguientes.",
  "Card Driven": "Las cartas son las que disparan acciones y eventos del juego.",
  "Roll & Move": "Tirás dados y avanzás esa cantidad de casilleros.",
  "Race": "Gana quien llegue primero a una meta.",
  "Stock Holding": "Comprás y vendés acciones cuyo valor sube y baja durante la partida.",
  "Real-Time": "Se juega a la vez y contra reloj, sin esperar turnos.",
  "Action Queue": "Programás con anticipación una cola de acciones que después se ejecutan.",
  "Area Movement": "Movés piezas entre zonas o regiones del tablero.",
  "Action Points": "Tenés una cantidad de puntos por turno para gastar entre varias acciones.",
  "Player Powers": "Cada jugador tiene habilidades propias y distintas.",
  "Simultaneous Actions": "Todos eligen sus acciones a la vez y después se revelan.",
  "Pattern Recognition": "Hay que detectar patrones o combinaciones en lo que se ve.",
  "Paper & Pencil": "Se anota y dibuja sobre una hoja o planilla.",
};
