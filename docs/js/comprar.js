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
  duracionMax: 180,
  complejidadMax: 5,
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
    if (!normalize(g.nombre).includes(normalize(state.query))) return false;
  }
  if (state.tipos.size > 0 && !state.tipos.has(g.modo)) return false;
  if (g.duracion != null && g.duracion > state.duracionMax) return false;
  if (g.complejidad != null && g.complejidad > state.complejidadMax) return false;
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

function sortGames(list) {
  const key = state.sort;
  const dir = key.endsWith("_asc") ? 1 : -1;
  const field = key.replace(/_(asc|desc)$/, "");
  return [...list].sort((a, b) => {
    const av = a[field];
    const bv = b[field];
    if (av == null && bv == null) return 0;
    if (av == null) return 1;
    if (bv == null) return -1;
    return av < bv ? dir * -1 : av > bv ? dir : 0;
  });
}

function render() {
  const filtered = sortGames(GAMES.filter(matchesFilters));
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
          })
        )
        .join("")
    : `<div class="empty-state">No encontré juegos con estos filtros.</div>`;

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

function setupControls() {
  document.getElementById("search").addEventListener("input", (e) => {
    state.query = e.target.value;
    scheduleFilterChange(200);
  });

  const tipoMultiselect = document.getElementById("tipo-multiselect");
  const tipoButton = document.getElementById("tipo-button");
  const tipoButtonLabel = document.getElementById("tipo-button-label");
  const tipoPanel = document.getElementById("tipo-panel");

  function updateTipoButtonLabel() {
    if (state.tipos.size === 0) tipoButtonLabel.textContent = "Todos";
    else if (state.tipos.size === 1) tipoButtonLabel.textContent = [...state.tipos][0];
    else tipoButtonLabel.textContent = `${state.tipos.size} seleccionados`;
  }

  function closeTipoPanel() {
    tipoPanel.hidden = true;
    tipoMultiselect.classList.remove("open");
    tipoButton.setAttribute("aria-expanded", "false");
  }

  TIPOS.forEach((tipo) => {
    const option = document.createElement("label");
    option.className = "multiselect-option";
    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.value = tipo;
    checkbox.addEventListener("change", () => {
      if (checkbox.checked) state.tipos.add(tipo);
      else state.tipos.delete(tipo);
      updateTipoButtonLabel();
      onFilterChange();
    });
    option.appendChild(checkbox);
    option.appendChild(document.createTextNode(tipo));
    tipoPanel.appendChild(option);
  });

  tipoButton.addEventListener("click", (e) => {
    e.stopPropagation();
    const willOpen = tipoPanel.hidden;
    tipoPanel.hidden = !willOpen;
    tipoMultiselect.classList.toggle("open", willOpen);
    tipoButton.setAttribute("aria-expanded", String(willOpen));
  });

  document.addEventListener("click", (e) => {
    if (!tipoMultiselect.contains(e.target)) closeTipoPanel();
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") closeTipoPanel();
  });

  const duracionInput = document.getElementById("duracion-max");
  const duracionLabel = document.getElementById("duracion-max-label");
  duracionInput.addEventListener("input", (e) => {
    state.duracionMax = Number(e.target.value);
    duracionLabel.textContent = state.duracionMax >= 180 ? "180+ min" : `${state.duracionMax} min`;
    scheduleFilterChange();
  });

  const complejidadInput = document.getElementById("complejidad-max");
  const complejidadLabel = document.getElementById("complejidad-max-label");
  complejidadInput.addEventListener("input", (e) => {
    state.complejidadMax = Number(e.target.value);
    complejidadLabel.textContent = state.complejidadMax >= 5 ? "5 (sin límite)" : state.complejidadMax.toFixed(1);
    scheduleFilterChange();
  });

  const playerLabel = document.getElementById("player-label");
  const bestOnlyInput = document.getElementById("best-only");

  function syncBestOnlyAvailability() {
    bestOnlyInput.disabled = state.jugadores == null;
    if (state.jugadores == null && state.soloMejor) {
      state.soloMejor = false;
      bestOnlyInput.checked = false;
    }
  }

  document.getElementById("player-minus").addEventListener("click", () => {
    state.jugadores = Math.max(1, (state.jugadores ?? 1) - 1);
    playerLabel.textContent = state.jugadores;
    syncBestOnlyAvailability();
    onFilterChange();
  });
  document.getElementById("player-plus").addEventListener("click", () => {
    state.jugadores = Math.min(12, (state.jugadores ?? 0) + 1);
    playerLabel.textContent = state.jugadores;
    syncBestOnlyAvailability();
    onFilterChange();
  });
  document.getElementById("player-clear").addEventListener("click", () => {
    state.jugadores = null;
    playerLabel.textContent = "todos";
    syncBestOnlyAvailability();
    onFilterChange();
  });

  bestOnlyInput.addEventListener("change", (e) => {
    state.soloMejor = e.target.checked;
    onFilterChange();
  });

  document.getElementById("sort-select").addEventListener("change", (e) => {
    state.sort = e.target.value;
    onFilterChange();
  });

  document.getElementById("quiero-comprar-only").addEventListener("change", (e) => {
    state.soloQuieroComprar = e.target.checked;
    onFilterChange();
  });
}

// --- Comparar dos juegos (sección colapsable, reusa el GAMES ya cargado
// arriba — no vuelve a pedir data.json). Antes era comparar.html/comparar.js,
// una página aparte; se fusionó acá porque se usa siempre junto con "¿Cuál
// comprar?" (comparar candidatos antes de decidir cuál comprar).

const compareState = { a: null, b: null };

// Cada fila de la tabla: cómo sacar el valor, cómo mostrarlo, y si aplica
// (y en qué sentido) resaltar cuál de los dos juegos "gana" esa fila.
const COMPARE_ROWS = [
  { label: "Estado", get: (g) => g.estado },
  { label: "Modo", get: (g) => g.modo },
  { label: "Año", get: (g) => g.anio },
  {
    label: "Jugadores",
    get: (g) => (g.jug_min != null && g.jug_max != null
      ? (g.jug_min === g.jug_max ? `${g.jug_min}` : `${g.jug_min}–${g.jug_max}`)
      : null),
  },
  {
    label: "Mejor con",
    get: (g) => {
      const range = jugBestRange(g);
      if (!range) return null;
      return range[0] === range[1] ? `${range[0]}` : `${range[0]}–${range[1]}`;
    },
  },
  { label: "Duración", get: (g) => g.duracion, format: (v) => `${v} min`, better: "lower" },
  { label: "Complejidad", get: (g) => g.complejidad, format: (v) => v.toFixed(1), better: "lower" },
  { label: "Puntaje BGG", get: (g) => g.puntaje_bgg, format: (v) => v.toFixed(2), better: "higher" },
  { label: "Reviews BGG", get: (g) => g.reviews_bgg, format: (v) => v.toLocaleString("es-AR") },
  { label: "Ranking BGG", get: (g) => g.ranking_bgg, format: (v) => `#${Number(v).toLocaleString("es-AR")}`, better: "lower" },
  { label: "Mi puntaje", get: (g) => g.mi_puntaje, format: (v) => `${v}/10`, better: "higher" },
  { label: "Costo", get: (g) => g.costo, format: (v) => `$${v.toLocaleString("es-AR")}`, better: "lower" },
  { label: "Precio / calidad", get: (g) => g.precio_calidad, format: (v) => v.toFixed(2), better: "higher" },
  {
    label: "Ficha BGG",
    html: true,
    get: (g) => (g.bgg_url ? `<a href="${escapeHtml(g.bgg_url)}" target="_blank" rel="noopener">Ver en BGG ↗</a>` : null),
  },
  {
    label: "Cazagangas",
    html: true,
    get: (g) => (g.cazagangas_status === "200" && g.link_cazagangas
      ? `<a href="${escapeHtml(g.link_cazagangas)}" target="_blank" rel="noopener">Ver en Cazagangas ↗</a>`
      : null),
  },
  { label: "Diseñador", get: (g) => g.disenador },
  { label: "Mecánicas", get: (g) => (g.mecanicas && g.mecanicas.length ? g.mecanicas.join(", ") : null) },
  { label: "Categorías", get: (g) => (g.categorias && g.categorias.length ? g.categorias.join(", ") : null) },
];

function findGame(name) {
  if (!name) return null;
  const norm = normalize(name);
  return GAMES.find((g) => normalize(g.nombre) === norm) || null;
}

function compareCellHtml(game, row, winner) {
  if (!game) return `<td class="compare-cell compare-cell--empty">—</td>`;
  const raw = row.get(game);
  if (raw == null || raw === "") return `<td class="compare-cell compare-cell--empty">?</td>`;
  const cls = winner ? "compare-cell compare-cell--winner" : "compare-cell";
  if (row.html) return `<td class="${cls}">${raw}</td>`;  // raw ya viene con su propio escapeHtml en el valor dinámico (ver get())
  const text = row.format ? row.format(typeof raw === "string" ? Number(raw) : raw) : raw;
  return `<td class="${cls}">${escapeHtml(String(text))}</td>`;
}

function compareRowWinner(row, a, b) {
  if (!row.better || !a || !b) return null;
  const av = a ? row.get(a) : null;
  const bv = b ? row.get(b) : null;
  if (av == null || bv == null || av === "" || bv === "") return null;
  const an = Number(av);
  const bn = Number(bv);
  if (an === bn) return null;
  const aWins = row.better === "higher" ? an > bn : an < bn;
  return aWins ? "a" : "b";
}

function renderCompare() {
  const { a, b } = compareState;
  const container = document.getElementById("compare-result");
  if (!container) return;

  if (!a && !b) {
    container.innerHTML = `<div class="empty-state">Elegí dos juegos arriba para compararlos.</div>`;
    return;
  }

  const nameCell = (game, placeholder) => game
    ? `<div class="compare-name">${escapeHtml(game.nombre)}</div>`
    : `<div class="compare-name compare-name--empty">${placeholder}</div>`;

  const rowsHtml = COMPARE_ROWS.map((row) => {
    const winner = compareRowWinner(row, a, b);
    return `
      <tr>
        <th scope="row">${escapeHtml(row.label)}</th>
        ${compareCellHtml(a, row, winner === "a")}
        ${compareCellHtml(b, row, winner === "b")}
      </tr>
    `;
  }).join("");

  container.innerHTML = `
    <table class="compare-table">
      <thead>
        <tr>
          <th scope="col"></th>
          <th scope="col">${nameCell(a, "Elegí el Juego A")}</th>
          <th scope="col">${nameCell(b, "Elegí el Juego B")}</th>
        </tr>
      </thead>
      <tbody>${rowsHtml}</tbody>
    </table>
  `;
}

function syncCompareUrl() {
  const params = new URLSearchParams(location.search);
  if (compareState.a) params.set("a", compareState.a.nombre);
  else params.delete("a");
  if (compareState.b) params.set("b", compareState.b.nombre);
  else params.delete("b");
  const qs = params.toString();
  history.replaceState(null, "", qs ? `?${qs}` : location.pathname);
}

function setupCompareControls() {
  const inputA = document.getElementById("game-a");
  const inputB = document.getElementById("game-b");

  const datalist = document.getElementById("games-list");
  const names = [...new Set(GAMES.map((g) => g.nombre))].sort((x, y) => x.localeCompare(y, "es"));
  datalist.innerHTML = names.map((n) => `<option value="${escapeHtml(n)}"></option>`).join("");

  inputA.addEventListener("change", () => {
    compareState.a = findGame(inputA.value);
    syncCompareUrl();
    renderCompare();
  });
  inputB.addEventListener("change", () => {
    compareState.b = findGame(inputB.value);
    syncCompareUrl();
    renderCompare();
  });

  const toggle = document.getElementById("compare-toggle");
  const body = document.getElementById("compare-body");
  toggle.addEventListener("click", () => {
    const willOpen = body.hidden;
    body.hidden = !willOpen;
    toggle.setAttribute("aria-expanded", String(willOpen));
  });

  const params = new URLSearchParams(location.search);
  const presetA = params.get("a");
  const presetB = params.get("b");
  if (presetA) {
    inputA.value = presetA;
    compareState.a = findGame(presetA);
  }
  if (presetB) {
    inputB.value = presetB;
    compareState.b = findGame(presetB);
  }
  // Si llegaron presets por URL (ej. un link compartido), el panel arranca
  // abierto de una en vez de forzar un click extra para ver el resultado.
  if (presetA || presetB) {
    body.hidden = false;
    toggle.setAttribute("aria-expanded", "true");
  }
}

document.getElementById("nav").innerHTML = navTemplate("comprar.html");
setupFiltersToggle();

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
      `<div class="empty-state">No pude cargar data.json: ${escapeHtml(err.message)}</div>`;
  });
