let GAMES = [];

const state = {
  query: "",
  sort: "ranking_bgg_asc",
};

function matchesFilters(g) {
  // Mi ludoteca es solo lo que tenés: lo que tuviste o querés comprar no se muestra acá.
  if (g.estado !== "Own") return false;
  if (state.query) {
    if (!matchesNombre(g, state.query)) return false;
  }
  return true;
}

function render() {
  const filtered = sortGames(GAMES.filter(matchesFilters), state.sort);
  const grid = document.getElementById("grid");
  const count = document.getElementById("result-count");
  count.textContent = `${filtered.length} juego${filtered.length === 1 ? "" : "s"}`;
  grid.innerHTML = filtered.length
    ? filtered.map((g) => cardTemplate(g)).join("")
    : GAMES.some((g) => g.estado === "Own")
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
