let GAMES = [];

const state = {
  query: "",
  sort: "ranking_bgg_asc",
};

function matchesFilters(g) {
  // Mi ludoteca es lo que tenés (o tuviste): Watchlist vive solo en ¿Cuál comprar?
  if (g.estado !== "Own" && g.estado !== "Prev. owned") return false;
  if (state.query) {
    if (!matchesNombre(g, state.query)) return false;
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
    ? filtered.map((g) => cardTemplate(g)).join("")
    : GAMES.some((g) => g.estado === "Own" || g.estado === "Prev. owned")
      ? `<div class="empty-state">No encontré juegos con esa búsqueda.</div>`
      : "";
  hydrate(filtered).then((n) => { if (n) render(); });
}

function setupControls() {
  document.getElementById("search").addEventListener("input", (e) => {
    state.query = e.target.value;
    render();
    ensureAltNames().then(() => { if (state.query) render(); });
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
