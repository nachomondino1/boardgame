let GAMES = [];

const TIPOS = ["Competitivo", "Cooperativo", "Equipos", "Cooperativo y competitivo"];

const state = {
  query: "",
  tipos: new Set(),
  duracionMax: 180,
  complejidadMax: 5,
  jugadores: null,
  soloMejor: false,
  soloQuieroComprar: false,
  sort: "puntaje_ajust_bgg_desc",
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
  const grid = document.getElementById("grid");
  const count = document.getElementById("result-count");
  count.textContent = `${filtered.length} juego${filtered.length === 1 ? "" : "s"}`;
  grid.innerHTML = filtered.length
    ? filtered.map((g) => cardTemplate(g, { jugadores: state.jugadores })).join("")
    : `<div class="empty-state">No encontré juegos con estos filtros.</div>`;
}

// Arrastrar un slider dispara un evento "input" por cada pixel: renderizar
// la grilla entera (hasta ~1000 tarjetas) en cada uno se siente trabado.
// rAF junta todos los eventos de un mismo frame en un solo render.
let renderScheduled = false;
function scheduleRender() {
  if (renderScheduled) return;
  renderScheduled = true;
  requestAnimationFrame(() => {
    renderScheduled = false;
    render();
  });
}

function setupControls() {
  document.getElementById("search").addEventListener("input", (e) => {
    state.query = e.target.value;
    render();
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
      render();
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
    scheduleRender();
  });

  const complejidadInput = document.getElementById("complejidad-max");
  const complejidadLabel = document.getElementById("complejidad-max-label");
  complejidadInput.addEventListener("input", (e) => {
    state.complejidadMax = Number(e.target.value);
    complejidadLabel.textContent = state.complejidadMax >= 5 ? "5 (sin límite)" : state.complejidadMax.toFixed(1);
    scheduleRender();
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
    render();
  });
  document.getElementById("player-plus").addEventListener("click", () => {
    state.jugadores = Math.min(12, (state.jugadores ?? 0) + 1);
    playerLabel.textContent = state.jugadores;
    syncBestOnlyAvailability();
    render();
  });
  document.getElementById("player-clear").addEventListener("click", () => {
    state.jugadores = null;
    playerLabel.textContent = "todos";
    syncBestOnlyAvailability();
    render();
  });

  bestOnlyInput.addEventListener("change", (e) => {
    state.soloMejor = e.target.checked;
    render();
  });

  document.getElementById("sort-select").addEventListener("change", (e) => {
    state.sort = e.target.value;
    render();
  });

  document.getElementById("quiero-comprar-only").addEventListener("change", (e) => {
    state.soloQuieroComprar = e.target.checked;
    render();
  });
}

document.getElementById("nav").innerHTML = navTemplate("comprar.html");
setupFiltersToggle();

loadGames()
  .then((data) => {
    GAMES = data;
    setupControls();
    render();
  })
  .catch((err) => {
    document.getElementById("grid").innerHTML =
      `<div class="empty-state">No pude cargar data.json: ${escapeHtml(err.message)}</div>`;
  });
