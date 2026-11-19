let GAMES = [];

const TIPOS = ["Competitivo", "Cooperativo", "Equipos", "Cooperativo y competitivo"];

// Renderizar hasta ~1000 tarjetas completas (con toda su data-viz interna)
// en cada cambio de filtro es lo que hacía sentir lento el filtrado,
// sobre todo en mobile — no el cálculo del filtro en sí (eso es rapidísimo
// incluso con 1000 juegos), sino construir y pintar cientos de nodos DOM.
// Solución: paginar (mostrar PAGE_SIZE de entrada, "Mostrar más" para el
// resto) en vez de todo de una.
const PAGE_SIZE = 60;

const state = {
  query: "",
  tipos: new Set(),
  duraciones: new Set(), // ids de BUCKETS_DURACION; vacío = todas
  complejidades: new Set(), // ids de BUCKETS_COMPLEJIDAD; vacío = todas
  decadas: new Set(), // ids de BUCKETS_DECADA; vacío = todas
  mecanicas: new Set(), // posiciones en MECANICAS_VOCAB; el juego tiene que tener todas las elegidas
  precios: new Set(), // ids de BUCKETS_PRECIO; vacío = todos. Con alguno elegido, solo entran juegos con precio de referencia
  jugadores: null,
  soloMejor: false,
  soloQuieroComprar: false,
  sort: "ranking_bgg_asc",
  visibleCount: PAGE_SIZE,
};

const ESTADOS_COMPRA = new Set(["Watchlist", "Want to buy"]);

function matchesFilters(g) {
  if (state.soloQuieroComprar) {
    if (g.estado !== "Want to buy") return false;
  } else if (!ESTADOS_COMPRA.has(g.estado)) {
    return false;
  }
  if (state.query) {
    if (!matchesNombre(g, state.query)) return false;
  }
  if (state.tipos.size > 0 && !state.tipos.has(g.modo)) return false;
  if (state.duraciones.size > 0) {
    if (g.duracion == null || !BUCKETS_DURACION.some((b) => state.duraciones.has(b.id) && b.match(g.duracion))) return false;
  }
  if (state.complejidades.size > 0) {
    if (g.complejidad == null || !BUCKETS_COMPLEJIDAD.some((b) => state.complejidades.has(b.id) && b.match(g.complejidad))) return false;
  }
  if (state.precios.size > 0) {
    if (g.precio_ref_usd == null || !BUCKETS_PRECIO.some((b) => state.precios.has(b.id) && b.match(g.precio_ref_usd))) return false;
  }
  if (state.mecanicas.size > 0) {
    const tiene = g.mecs || [];
    for (const id of state.mecanicas) if (!tiene.includes(Number(id))) return false;
  }
  if (state.decadas.size > 0) {
    if (g.anio == null || !BUCKETS_DECADA.some((b) => state.decadas.has(b.id) && b.match(g.anio))) return false;
  }
  if (state.jugadores != null) {
    if (state.soloMejor) {
      if (g.jug_best_min == null) return false;
      const bestMax = g.jug_best_max ?? g.jug_best_min;
      if (state.jugadores < g.jug_best_min || state.jugadores > bestMax) return false;
    } else {
      if (g.jug_min == null || g.jug_max == null) return false;
      if (state.jugadores < g.jug_min || state.jugadores > g.jug_max) return false;
    }
  }
  return true;
}

function render() {
  const filtered = sortGames(GAMES.filter(matchesFilters), state.sort);
  const grouped = collapseGrupos(filtered);
  const grid = document.getElementById("grid");
  const count = document.getElementById("result-count");
  const loadMoreRow = document.getElementById("load-more-row");
  const visible = grouped.slice(0, state.visibleCount);

  count.textContent = grouped.length
    ? `${visible.length} de ${grouped.length} juego${grouped.length === 1 ? "" : "s"}`
    : "0 juegos";

  grid.innerHTML = visible.length
    ? visible
        .map((entry) =>
          cardTemplate(entry.game, {
            jugadores: state.jugadores,
            variantes: entry.variantes,
            grupoNombre: entry.grupoNombre,
            showCazagangas: true,
            showPrecioRef: true,
            showComparar: true,
          })
        )
        .join("")
    : `<div class="empty-state">No encontré juegos con estos filtros.</div>`;

  syncCompareButtons();
  hydrate(visible.map((entry) => entry.game)).then((n) => { if (n) render(); });

  const restantes = grouped.length - visible.length;
  loadMoreRow.innerHTML = restantes > 0
    ? `<button type="button" class="load-more-btn" id="load-more-btn">Mostrar ${Math.min(PAGE_SIZE, restantes)} más (quedan ${restantes})</button>`
    : "";
  if (restantes > 0) {
    document.getElementById("load-more-btn").addEventListener("click", () => {
      state.visibleCount += PAGE_SIZE;
      render();
    });
  }
}

// Cualquier cambio de filtro vuelve a mostrar desde la primera página
// (si no, "quedan 300 más" de un filtro viejo no tiene sentido con el
// filtro nuevo aplicado).
function onFilterChange() {
  state.visibleCount = PAGE_SIZE;
  render();
}

// Un slider dispara un evento "input" por cada pixel arrastrado, y
// escribir ~1000 juegos filtrados + construir el HTML de hasta PAGE_SIZE
// tarjetas en cada uno se siente trabado en mobile. En vez de renderizar
// en cada evento (ni siquiera agrupando por frame con rAF alcanza: arrastrar
// rápido sigue generando un render por frame), se espera a que el usuario
// deje de mover el slider (debounce) — la etiqueta del valor sí se
// actualiza al instante, solo el filtrado/render de la grilla se demora.
let filterChangeTimer = null;
function scheduleFilterChange(delayMs = 150) {
  clearTimeout(filterChangeTimer);
  filterChangeTimer = setTimeout(onFilterChange, delayMs);
}

// --- Filtros: píldoras con menú (js/filter-pills.js) -------------------------------

const MAX_JUGADORES_FILTRO = 8;

const FILTROS = [
  { id: "jugadores", titulo: "Jugadores", icono: "👥", multiple: false, numero: true,
    unidad: (n) => `${n} jugador${n === 1 ? "" : "es"}`,
    opciones: Array.from({ length: MAX_JUGADORES_FILTRO }, (_, i) => ({ id: String(i + 1), label: String(i + 1) })),
    extra: { key: "soloMejor", label: "Solo si es el mejor número", sufijo: "mejor número" } },
  { id: "duraciones", titulo: "Duración", icono: "⏱", multiple: true, opciones: BUCKETS_DURACION },
  { id: "complejidades", titulo: "Complejidad", icono: "⚙️", multiple: true,
    opciones: BUCKETS_COMPLEJIDAD.map((b) => ({ ...b, hint: `Peso en BGG: ${b.hint}` })) },
  { id: "precios", titulo: "Precio", icono: "💵", multiple: true,
    nota: "⚠️ Solo aparecen los juegos con precio de referencia de BGG (alrededor de 1 de cada 5).", opciones: BUCKETS_PRECIO.map((b) => ({ ...b, hint: "Referencia de BGG" })) },
  { id: "decadas", titulo: "Década", icono: "📅", multiple: true, opciones: BUCKETS_DECADA },
  { id: "tipos", titulo: "Tipo", icono: "🎲", multiple: true, opciones: TIPOS.map((t) => ({ id: t, label: modoLabel(t) })) },
];

function setupControls() {
  FILTROS.push({
    id: "mecanicas", titulo: "Mecánicas", icono: "🧩", multiple: true,
    nota: "Muestra los juegos que tienen todas las mecánicas que elijas.",
    opciones: MECANICAS_VOCAB.map((label, i) => ({ id: String(i), label, hint: MECANICAS_HINT[label] })),
    ayudaTitulo: "ℹ️ ¿Qué es cada una?",
    ayuda: MECANICAS_VOCAB.filter((l) => MECANICAS_HINT[l]).map((l) => [l, MECANICAS_HINT[l]]),
  });
  document.getElementById("search").addEventListener("input", (e) => {
    state.query = e.target.value;
    scheduleFilterChange(200);
    ensureAltNames().then(() => { if (state.query) scheduleFilterChange(0); });
  });

  mountFilterPills(document.getElementById("filter-pills"), {
    filters: FILTROS,
    toggles: [{ key: "soloQuieroComprar", label: "Solo quiero comprar", icono: "🛒" }],
    state,
    clearButton: document.getElementById("clear-filters"),
    onChange: onFilterChange,
  });

  document.getElementById("sort-select").addEventListener("change", (e) => {
    state.sort = e.target.value;
    onFilterChange();
  });
}

// --- Comparar dos juegos (sección colapsable, reusa el GAMES ya cargado
// arriba — no vuelve a pedir data.json). Antes era comparar.html/comparar.js,
// una página aparte; se fusionó acá porque se usa siempre junto con "¿Cuál
// comprar?" (comparar candidatos antes de decidir cuál comprar).

const MAX_COMPARE = 4;
const COMPARE_LISTA_MAX = 5; // mecánicas y categorías que se muestran por juego
const compareState = { games: [] };

// Cada fila de la tabla: cómo sacar el valor, cómo mostrarlo, y si aplica
// (y en qué sentido) resaltar cuál de los dos juegos "gana" esa fila.
const COMPARE_ROWS = [
  { label: "Estado", desc: "Cómo figura el juego en tu colección (en seguimiento, quiero comprar, lo tengo).", emoji: "📌", get: (g) => g.estado },
  { label: "Modo", desc: "Si se juega compitiendo, en cooperativo o por equipos.", emoji: "🎲", get: (g) => (g.modo ? modoLabel(g.modo) : null) },
  { label: "Año", desc: "Año de publicación.", emoji: "📅", get: (g) => g.anio },
  {
    label: "Jugadores", desc: "Cantidad de jugadores que indica la caja.", emoji: "👥",
    get: (g) => (g.jug_min != null && g.jug_max != null
      ? (g.jug_min === g.jug_max ? `${g.jug_min}` : `${g.jug_min}–${g.jug_max}`)
      : null),
  },
  {
    label: "Mejor con", desc: "Cantidad ideal de jugadores según la comunidad de BGG, que no siempre coincide con la caja.", emoji: "🎯",
    get: (g) => {
      const range = jugBestRange(g);
      if (!range) return null;
      return range[0] === range[1] ? `${range[0]}` : `${range[0]}–${range[1]}`;
    },
  },
  { label: "Duración", desc: "Minutos de una partida. En color, el más corto.", emoji: "⏱", get: (g) => g.duracion, format: (v) => `${v} min`, better: "lower" },
  { label: "Complejidad", desc: "Peso del juego en BGG, de 1 (liviano) a 5 (pesado). En color, el más simple.", emoji: "⚙️", get: (g) => g.complejidad, format: (v) => v.toFixed(1), better: "lower" },
  { label: "Puntaje BGG", desc: "Promedio de las notas de la comunidad de BGG, sobre 10. En color, el más alto.", emoji: "⭐", get: (g) => g.puntaje_bgg, format: (v) => v.toFixed(2), better: "higher" },
  { label: "Reviews BGG", desc: "Cuánta gente lo puntuó: con más reviews, el puntaje es más confiable.", emoji: "💬", get: (g) => g.reviews_bgg, format: (v) => v.toLocaleString("es-AR") },
  { label: "Ranking BGG", desc: "Posición en el ranking general de BGG (#1 es el mejor). En color, el mejor ubicado.", emoji: "🏆", get: (g) => g.ranking_bgg, format: (v) => `#${Number(v).toLocaleString("es-AR")}`, better: "lower" },
  { label: "Mi puntaje", desc: "Tu propia nota, si la cargaste.", emoji: "🙋", get: (g) => g.mi_puntaje, format: (v) => `${v}/10`, better: "higher" },
  { label: "Precio ref. (USD)", desc: "Precio aproximado en dólares, tomado de ofertas recientes en BGG. Es solo una referencia, no un precio local.", emoji: "💵", get: (g) => g.precio_ref_usd, format: (v) => `~$${Math.round(v).toLocaleString("es-AR")}`, better: "lower" },
  {
    label: "Ficha BGG", desc: "Link a la página del juego en BoardGameGeek.", emoji: "🔗",
    html: true,
    get: (g) => (g.bgg_url ? `<a href="${escapeHtml(g.bgg_url)}" target="_blank" rel="noopener">Ver en BGG ↗</a>` : null),
  },
  {
    label: "Cazagangas", desc: "Link para ver el precio en Argentina.", emoji: "💰",
    html: true,
    get: (g) => (g.cazagangas_status === "200" && g.link_cazagangas
      ? `<a href="${escapeHtml(g.link_cazagangas)}" target="_blank" rel="noopener">Ver en Cazagangas ↗</a>`
      : null),
  },
  { label: "Diseñador", desc: "Quién lo diseñó.", emoji: "✍️", get: (g) => g.disenador },
  { label: "Mecánicas", desc: "Tipos de reglas que usa (en chico: solo las primeras cinco; la lista completa al pasar el mouse).", emoji: "🧩", lista: true, get: (g) => (g.mecanicas && g.mecanicas.length ? g.mecanicas.join(" · ") : null) },
  { label: "Categorías", desc: "Temas o géneros del juego.", emoji: "🏷️", lista: true, get: (g) => (g.categorias && g.categorias.length ? g.categorias.join(" · ") : null) },
];

function findGame(name) {
  if (!name) return null;
  const norm = normalize(name);
  return GAMES.find((g) => normalize(g.nombre) === norm) || null;
}

function compareCellHtml(game, row, winner) {
  const raw = row.get(game);
  if (raw == null || raw === "") return `<td class="compare-cell compare-cell--empty">?</td>`;
  const cls = winner ? "compare-cell compare-cell--winner" : "compare-cell";
  if (row.lista) {
    // Listas largas (mecánicas, categorías): chicas, solo las primeras y "+N"; la lista completa va en el title.
    const items = String(raw).split(" · ");
    const resto = items.length - COMPARE_LISTA_MAX;
    const texto = items.slice(0, COMPARE_LISTA_MAX).join(" · ") + (resto > 0 ? ` · +${resto}` : "");
    return `<td class="compare-cell compare-cell--lista" title="${escapeHtml(String(raw))}">${escapeHtml(texto)}</td>`;
  }
  if (row.html) return `<td class="${cls}">${raw}</td>`;  // raw ya viene con su propio escapeHtml en el valor dinámico (ver get())
  const text = row.format ? row.format(typeof raw === "string" ? Number(raw) : raw) : raw;
  return `<td class="${cls}">${escapeHtml(String(text))}</td>`;
}

// Posiciones (en `games`) que "ganan" la fila: el mejor valor, si hay al menos dos con dato y no empatan todos.
function compareRowWinners(row, games) {
  if (!row.better) return new Set();
  const vals = games.map((g) => {
    const v = row.get(g);
    return v == null || v === "" ? null : Number(v);
  });
  const conDato = vals.filter((v) => v != null && !Number.isNaN(v));
  if (conDato.length < 2) return new Set();
  const mejor = row.better === "higher" ? Math.max(...conDato) : Math.min(...conDato);
  if (conDato.every((v) => v === mejor)) return new Set();
  return new Set(vals.map((v, i) => (v === mejor ? i : -1)).filter((i) => i >= 0));
}

function renderCompare() {
  const games = compareState.games;
  const container = document.getElementById("compare-result");
  if (!container) return;

  if (!games.length) {
    container.innerHTML = `<div class="empty-state">Elegí juegos con el botón ⚔️ de cada card para compararlos.</div>`;
    return;
  }

  // Una fila sin dato en ninguno de los juegos no aporta nada: no se muestra.
  const filasConDato = COMPARE_ROWS.filter((row) => games.some((g) => {
    const v = row.get(g);
    return v != null && v !== "";
  }));
  const rowsHtml = filasConDato.map((row) => {
    const winners = compareRowWinners(row, games);
    return `
      <tr>
        <th scope="row" title="${escapeHtml(row.label)}"><span class="cmp-emoji" aria-hidden="true">${row.emoji}</span><span class="cmp-label">${escapeHtml(row.label)}</span></th>
        ${games.map((g, i) => compareCellHtml(g, row, winners.has(i))).join("")}
      </tr>
    `;
  }).join("");

  container.innerHTML = `
    <div class="compare-scroll">
      <table class="compare-table" style="--n:${games.length}">
        <thead>
          <tr>
            <th scope="col"></th>
            ${games.map((g) => `<th scope="col"><div class="compare-name">${escapeHtml(g.nombre)}</div></th>`).join("")}
          </tr>
        </thead>
        <tbody>${rowsHtml}</tbody>
      </table>
    </div>
    <details class="compare-legend">
      <summary>ℹ️ ¿Qué significa cada fila?</summary>
      <dl>
        ${filasConDato.map((row) => `<dt>${row.emoji} ${escapeHtml(row.label)}</dt><dd>${escapeHtml(row.desc)}</dd>`).join("")}
      </dl>
    </details>
  `;
}

// Los juegos elegidos viajan en la URL (?g=Brass&g=Ark+Nova...), así un link compartido abre la misma comparación.
function syncCompareUrl() {
  const params = new URLSearchParams(location.search);
  params.delete("a");
  params.delete("b");
  params.delete("g");
  compareState.games.forEach((g) => params.append("g", g.nombre));
  const qs = params.toString();
  history.replaceState(null, "", qs ? `?${qs}` : location.pathname);
}

// Botón ⚔️ en cada card + barra fija abajo (card-compare-btn / compare-bar).
function syncCompareButtons() {
  const sel = compareState.games;
  const ids = sel.map((g) => String(g.bgg_id));
  const primero = sel[0];
  const corto = primero && primero.nombre.length > 16 ? primero.nombre.slice(0, 15) + "…" : primero && primero.nombre;
  document.querySelectorAll("[data-compare]").forEach((btn) => {
    const on = ids.includes(btn.dataset.compare);
    btn.classList.toggle("selected", on);
    btn.textContent = on ? "✓" : "⚔️";
    btn.title = on ? "En comparación (tocá para quitar)" : ids.length === 1 ? `Comparar con ${corto}` : ids.length ? "Sumar a la comparación" : "Comparar";
  });
  const tip = document.getElementById("compare-tip");
  if (tip) tip.hidden = ids.length > 0;
  let bar = document.getElementById("compare-bar");
  if (!bar) {
    bar = document.createElement("div");
    bar.id = "compare-bar";
    bar.className = "compare-bar";
    document.body.appendChild(bar);
    bar.addEventListener("click", (e) => {
      if (e.target.closest("[data-bar-clear]")) {
        compareState.games = [];
        syncCompareUrl();
        renderCompare();
        syncCompareButtons();
      } else if (e.target.closest("[data-bar-open]")) {
        document.getElementById("compare-body").hidden = false;
      }
    });
  }
  bar.hidden = sel.length === 0;
  const nombres = sel.length === 1
    ? `<b>${escapeHtml(sel[0].nombre)}</b> · elegí otro juego para compararlo`
    : `${sel.map((g) => escapeHtml(g.nombre)).join(", ")}${sel.length < MAX_COMPARE ? ` <i>(podés sumar hasta ${MAX_COMPARE})</i>` : ""}`;
  bar.innerHTML = `
    <span class="compare-bar__names">${nombres}</span>
    ${sel.length >= 2 ? `<button type="button" class="compare-bar__go" data-bar-open>Ver comparación (${sel.length}) →</button>` : ""}
    <button type="button" class="compare-bar__clear" data-bar-clear aria-label="Limpiar comparación">✕</button>`;
}

function toggleCompare(id) {
  const game = GAMES.find((g) => String(g.bgg_id) === id);
  if (!game) return;
  const actual = compareState.games;
  compareState.games = actual.includes(game)
    ? actual.filter((g) => g !== game)
    : [...actual, game].slice(-MAX_COMPARE);
  syncCompareUrl();
  renderCompare();
  syncCompareButtons();
  hydrate(compareState.games).then(renderCompare);
}

function setupCompareControls() {
  const cerrar = () => { document.getElementById("compare-body").hidden = true; };
  document.getElementById("compare-close").addEventListener("click", cerrar);
  document.getElementById("compare-body").addEventListener("click", (e) => { if (e.target.id === "compare-body") cerrar(); });
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") cerrar(); });
  document.getElementById("grid").addEventListener("click", (e) => {
    const btn = e.target.closest("[data-compare]");
    if (btn) toggleCompare(btn.dataset.compare);
  });

  // Links compartidos: ?g=Nombre (varios) o los viejos ?a= y ?b=.
  const params = new URLSearchParams(location.search);
  const nombres = [...params.getAll("g"), params.get("a"), params.get("b")].filter(Boolean);
  const games = [...new Set(nombres.map(findGame).filter(Boolean))].slice(0, MAX_COMPARE);
  if (games.length) {
    compareState.games = games;
    hydrate(games).then(renderCompare);
    document.getElementById("compare-body").hidden = false;
  }
  syncCompareButtons();
}

document.getElementById("nav").innerHTML = navTemplate("comprar.html");

loadGames()
  .then((data) => {
    GAMES = data;
    setupControls();
    render();
    setupCompareControls();
    renderCompare();
  })
  .catch((err) => {
    document.getElementById("grid").innerHTML =
      `<div class="empty-state">No pude cargar los datos: ${escapeHtml(err.message)}</div>`;
  });
