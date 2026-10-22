let GAMES = [];

const state = {
  query: "",
  jugadores: null,
  estados: new Set(),
  sort: "puntaje_ajust_bgg_desc",
};

const ESTADOS = ["Own", "Watchlist", "Prev. owned"];

function matchesFilters(g) {
  if (state.query) {
    if (!normalize(g.nombre).includes(normalize(state.query))) return false;
  }
  if (state.jugadores != null) {
    if (g.jug_min == null || g.jug_max == null) return false;
    if (state.jugadores < g.jug_min || state.jugadores > g.jug_max) return false;
  }
  if (state.estados.size > 0 && !state.estados.has(g.estado)) return false;
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
  document.getElementById("search").addEventListener("input", (e) => {
    state.query = e.target.value;
    render();
  });

  const playerLabel = document.getElementById("player-label");
  document.getElementById("player-minus").addEventListener("click", () => {
    state.jugadores = Math.max(1, (state.jugadores ?? 2) - 1);
    playerLabel.textContent = state.jugadores;
    render();
  });
  document.getElementById("player-plus").addEventListener("click", () => {
    state.jugadores = Math.min(12, (state.jugadores ?? 1) + 1);
    playerLabel.textContent = state.jugadores;
    render();
  });
  document.getElementById("player-clear").addEventListener("click", () => {
    state.jugadores = null;
    playerLabel.textContent = "todos";
    render();
  });

  const estadoChips = document.getElementById("estado-chips");
  ESTADOS.forEach((estado) => {
    const chip = document.createElement("span");
    chip.className = "chip";
    chip.textContent = estado;
    chip.addEventListener("click", () => {
      if (state.estados.has(estado)) {
        state.estados.delete(estado);
        chip.classList.remove("active");
      } else {
        state.estados.add(estado);
        chip.classList.add("active");
      }
      render();
    });
    estadoChips.appendChild(chip);
  });

  document.getElementById("sort-select").addEventListener("change", (e) => {
    state.sort = e.target.value;
    render();
  });

}

document.getElementById("nav").innerHTML = navTemplate("index.html");
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
