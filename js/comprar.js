let GAMES = [];

const TIPOS = ["Competitivo", "Cooperativo", "Equipos", "Ambos", "A confirmar"];

const state = {
  tipos: new Set(),
  duracionMax: 180,
  complejidadMax: 5,
  jugadores: null,
  soloMejor: false,
  sort: "puntaje_ajust_bgg_desc",
};

function matchesFilters(g) {
  if (g.estado !== "Watchlist") return false;
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

function setupControls() {
  const tipoChips = document.getElementById("tipo-chips");
  TIPOS.forEach((tipo) => {
    const chip = document.createElement("span");
    chip.className = "chip";
    chip.textContent = tipo;
    chip.addEventListener("click", () => {
      if (state.tipos.has(tipo)) {
        state.tipos.delete(tipo);
        chip.classList.remove("active");
      } else {
        state.tipos.add(tipo);
        chip.classList.add("active");
      }
      render();
    });
    tipoChips.appendChild(chip);
  });

  const duracionInput = document.getElementById("duracion-max");
  const duracionLabel = document.getElementById("duracion-max-label");
  duracionInput.addEventListener("input", (e) => {
    state.duracionMax = Number(e.target.value);
    duracionLabel.textContent = state.duracionMax >= 180 ? "180+ min" : `${state.duracionMax} min`;
    render();
  });

  const complejidadInput = document.getElementById("complejidad-max");
  const complejidadLabel = document.getElementById("complejidad-max-label");
  complejidadInput.addEventListener("input", (e) => {
    state.complejidadMax = Number(e.target.value);
    complejidadLabel.textContent = state.complejidadMax >= 5 ? "5 (sin límite)" : state.complejidadMax.toFixed(1);
    render();
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
