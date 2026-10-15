let GAMES = [];

const state = {
  jugadores: null,
  incluirDeseados: false,
  soloBest: false,
};

function matchesFilters(g) {
  if (state.jugadores == null) return false;
  if (state.soloBest) {
    if (!matchesJugBest(g, state.jugadores)) return false;
  } else {
    if (g.jug_min == null || g.jug_max == null) return false;
    if (state.jugadores < g.jug_min || state.jugadores > g.jug_max) return false;
  }
  if (!state.incluirDeseados && g.estado !== "Own") return false;
  return true;
}

function render() {
  const grid = document.getElementById("grid");
  const count = document.getElementById("result-count");
  const label = document.getElementById("player-number");
  label.textContent = state.jugadores == null ? "?" : state.jugadores;

  if (state.jugadores == null) {
    count.textContent = "";
    grid.innerHTML = `<div class="empty-state">Elegí cuántos jugadores son hoy ☝️</div>`;
    return;
  }

  const posibles = GAMES.filter(matchesFilters);
  const withScore = posibles.map((g) => ({ g, score: recommendationScore(g, state.jugadores) }));
  withScore.sort((a, b) => b.score - a.score);

  count.textContent = `${posibles.length} juego${posibles.length === 1 ? "" : "s"} posibles`;

  if (!posibles.length) {
    const sugerencia = state.incluirDeseados
      ? "No encontré ningún juego (ni siquiera en tu watchlist) para esa cantidad de jugadores."
      : "No tenés ningún juego Own para esa cantidad. Probá tildar \"incluir watchlist\" para ver qué comprarías.";
    grid.innerHTML = `<div class="empty-state">${sugerencia}</div>`;
    return;
  }

  const gamesHtml = withScore
    .map((x) => cardTemplate(x.g, { jugadores: state.jugadores }))
    .join("");

  grid.innerHTML = `<div class="grid">${gamesHtml}</div>`;
}

function setJugadores(n) {
  state.jugadores = Math.max(1, Math.min(12, n));
  render();
}

function setupControls() {
  document.getElementById("player-minus").addEventListener("click", () => {
    setJugadores((state.jugadores ?? 1) - 1);
  });
  document.getElementById("player-plus").addEventListener("click", () => {
    setJugadores((state.jugadores ?? 0) + 1);
  });
  document.getElementById("incluir-deseados").addEventListener("change", (e) => {
    state.incluirDeseados = e.target.checked;
    render();
  });
  document.getElementById("solo-best").addEventListener("change", (e) => {
    state.soloBest = e.target.checked;
    render();
  });
}

document.getElementById("nav").innerHTML = navTemplate("hoy.html");
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
