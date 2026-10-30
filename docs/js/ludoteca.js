let GAMES = [];

const state = {
  query: "",
  jugadores: null,
  estados: new Set(["Own"]),
  sort: "ranking_bgg_asc",
};

// Filtros (js/filter-pills.js). Por default se ve lo que tenés; "Limpiar filtros" vuelve a eso.
const FILTROS = [
  { id: "jugadores", titulo: "Jugadores", icono: "👥", multiple: false, numero: true,
    unidad: (n) => `${n} jugador${n === 1 ? "" : "es"}`,
    opciones: Array.from({ length: 8 }, (_, i) => ({ id: String(i + 1), label: String(i + 1) })) },
  { id: "estados", titulo: "Estado", icono: "📚", multiple: true, defecto: ["Own"],
    opciones: [{ id: "Own", label: "Lo tengo" }, { id: "Prev. owned", label: "Lo tuve" }] },
];

function matchesFilters(g) {
  // Mi ludoteca es lo que tenés (o tuviste): Watchlist vive solo en ¿Cuál comprar?
  if (g.estado !== "Own" && g.estado !== "Prev. owned") return false;
  if (state.query) {
    if (!matchesNombre(g, state.query)) return false;
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
    : `<div class="empty-state">${GAMES.some((g) => g.estado === "Own" || g.estado === "Prev. owned")
        ? "No encontré juegos con estos filtros."
        : "Todavía no cargaste tus juegos. Usá \"Cargar o editar mis juegos\", acá arriba."}</div>`;
  hydrate(filtered).then((n) => { if (n) render(); });
}

function setupControls() {
  document.getElementById("search").addEventListener("input", (e) => {
    state.query = e.target.value;
    render();
    ensureAltNames().then(() => { if (state.query) render(); });
  });

  mountFilterPills(document.getElementById("filter-pills"), {
    filters: FILTROS,
    state,
    clearButton: document.getElementById("clear-filters"),
    onChange: render,
  });

  document.getElementById("sort-select").addEventListener("change", (e) => {
    state.sort = e.target.value;
    render();
  });

}

document.getElementById("nav").innerHTML = navTemplate("ludoteca.html");

const detailsEl = document.getElementById("col-details");
mountCollectionLoader(document.getElementById("collection-loader"), {
  onChange: () => {
    applyCollection(GAMES);
    render();
    renderAnalisis(document.getElementById("analisis"), GAMES);
  },
});

loadGames()
  .then((data) => {
    GAMES = data;
    setupControls();
    // Sin colección cargada, el panel arranca abierto: es lo único que hay para hacer.
    if (!GAMES.some((g) => g.estado !== "Watchlist")) detailsEl.open = true;
    render();
    renderAnalisis(document.getElementById("analisis"), GAMES);
  })
  .catch((err) => {
    document.getElementById("grid").innerHTML =
      `<div class="empty-state">No pude cargar los datos: ${escapeHtml(err.message)}</div>`;
  });
