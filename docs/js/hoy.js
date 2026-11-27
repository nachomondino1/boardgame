// ¿Qué jugamos hoy?: dada la cantidad de jugadores (y, si se quiere, el tiempo), muestra qué sacar de
// la ludoteca. Primero los juegos para los que la comunidad de BGG recomienda justo esa cantidad
// ("mejor con N"), después los que también funcionan. "Elegime uno" sortea entre los mejores.
let GAMES = [];

const state = {
  jugadores: null,
  tiempoMax: null, // minutos; null = sin límite
  incluirDeseados: false,
  sort: "ranking_bgg_asc",
  pickId: null, // juego sorteado por "Elegime uno"
};

const PICK_POOL = 8; // "Elegime uno" sortea entre los primeros N de la mejor tanda

const FILTROS = [
  { id: "tiempoMax", titulo: "Tiempo", icono: "⏱", multiple: false, numero: true,
    unidad: (n) => (n === 30 ? "Hasta 30 min" : n === 60 ? "Hasta 1 hora" : "Hasta 2 horas"),
    opciones: [
      { id: "30", label: "Hasta 30 min" },
      { id: "60", label: "Hasta 1 hora" },
      { id: "120", label: "Hasta 2 horas" },
    ] },
];

// Ordena por el campo del juego directo, como en ¿Cuál comprar?.
function matchesFilters(g) {
  if (state.jugadores == null) return false;
  if (g.jug_min == null || g.jug_max == null) return false;
  if (state.jugadores < g.jug_min || state.jugadores > g.jug_max) return false;
  // Sin duración en BGG no se esconde: es mejor mostrarlo que perderlo.
  if (state.tiempoMax != null && g.duracion != null && g.duracion > state.tiempoMax) return false;
  const estadosPermitidos = state.incluirDeseados ? new Set(["Own", "Want to buy"]) : new Set(["Own"]);
  return estadosPermitidos.has(g.estado);
}

function tandaHtml(titulo, sub, games) {
  return `
    <section class="hoy-tanda">
      <h2 class="hoy-tanda__title">${titulo} <span class="hoy-tanda__count">${games.length}</span></h2>
      <p class="hoy-tanda__sub">${sub}</p>
      <div class="grid">${games.map((g) => cardTemplate(g, { jugadores: state.jugadores })).join("")}</div>
    </section>`;
}

function elegirUno(pool, evitarId) {
  const candidatos = pool.length > 1 ? pool.filter((g) => g.bgg_id !== evitarId) : pool;
  return candidatos[Math.floor(Math.random() * candidatos.length)];
}

function render() {
  const grid = document.getElementById("grid");
  const count = document.getElementById("result-count");
  document.getElementById("player-number").textContent = state.jugadores == null ? "?" : state.jugadores;

  if (!GAMES.some((g) => g.estado === "Own")) {
    count.textContent = "";
    grid.innerHTML = `
      <div class="empty-state">
        <p>Todavía no cargaste tus juegos.</p>
        <a class="hoy-pick__btn" href="ludoteca.html">Cargar mis juegos →</a>
      </div>`;
    return;
  }

  if (state.jugadores == null) {
    count.textContent = "";
    grid.innerHTML = `<div class="empty-state">Elegí cuántos jugadores son hoy ☝️</div>`;
    return;
  }

  const n = state.jugadores;
  const posibles = sortGames(GAMES.filter(matchesFilters), state.sort);
  const ideales = posibles.filter((g) => matchesJugBest(g, n));
  const funcionan = posibles.filter((g) => !matchesJugBest(g, n));

  count.textContent = `${posibles.length} posible${posibles.length === 1 ? "" : "s"}`
    + (ideales.length ? ` · ${ideales.length} ideal${ideales.length === 1 ? "" : "es"}` : "");

  if (!posibles.length) {
    const sugerencia = state.incluirDeseados || state.tiempoMax != null
      ? "No encontré juegos con esos filtros. Probá sacar alguno."
      : "No tenés ningún juego para esa cantidad. Probá sumar lo que querés comprar para ver qué conviene.";
    grid.innerHTML = `<div class="empty-state">${sugerencia}</div>`;
    return;
  }

  const pool = (ideales.length ? ideales : funcionan).slice(0, PICK_POOL);
  const elegido = posibles.find((g) => g.bgg_id === state.pickId) || null;
  if (!elegido) state.pickId = null;

  const pickHtml = `
    <div class="hoy-pick">
      ${elegido
        ? `<button type="button" class="hoy-pick__btn hoy-pick__btn--ghost" data-pick>🎲 Elegir otro</button>
           <span class="hoy-pick__hint">Esta vez, probá con <b>${escapeHtml(elegido.nombre)}</b> (marcado en la lista)</span>`
        : `<button type="button" class="hoy-pick__btn" data-pick>🎲 Elegime uno</button>
           <span class="hoy-pick__hint">entre los mejores para ${n}</span>`}
    </div>`;

  const sub = ideales.length
    ? `Los marcados con ⭐ son los que la comunidad de BGG recomienda justo para ${n}.`
    : `Ninguno tiene a ${n} como cantidad ideal, pero todos se pueden jugar.`;
  const seccion = `
    <section class="hoy-tanda">
      <p class="hoy-tanda__sub">${sub}</p>
      <div class="grid">${posibles.map((g) => cardTemplate(g, { jugadores: n })).join("")}</div>
    </section>`;

  grid.innerHTML = pickHtml + seccion;
  grid.dataset.pool = pool.map((g) => g.bgg_id).join(",");
  hydrate(elegido ? [elegido, ...posibles] : posibles).then((cargados) => { if (cargados) render(); });
  ideales.forEach((g) => {
    const c = grid.querySelector(`.card[data-id="${g.bgg_id}"]`);
    if (c) c.classList.add("card-best");
  });
  if (elegido) {
    const card = grid.querySelector(`.card[data-id="${elegido.bgg_id}"]`);
    if (card) {
      card.classList.add("card-elegida");
      if (state.scrollAlElegido) card.scrollIntoView({ behavior: "smooth", block: "center" });
    }
  }
  state.scrollAlElegido = false;
}

function setJugadores(n) {
  state.jugadores = Math.max(1, Math.min(12, n));
  state.pickId = null;
  render();
}

function setupControls() {
  document.getElementById("player-minus").addEventListener("click", () => {
    setJugadores((state.jugadores ?? 1) - 1);
  });
  document.getElementById("player-plus").addEventListener("click", () => {
    setJugadores((state.jugadores ?? 0) + 1);
  });
  mountFilterPills(document.getElementById("filter-pills"), {
    filters: FILTROS,
    toggles: [{ key: "incluirDeseados", label: "Sumar lo que quiero comprar", icono: "🛒" }],
    state,
    clearButton: document.getElementById("clear-filters"),
    onChange: render,
  });

  document.getElementById("grid").addEventListener("click", (e) => {
    if (!e.target.closest("[data-pick]")) return;
    const ids = (document.getElementById("grid").dataset.pool || "").split(",").filter(Boolean);
    const pool = ids.map((id) => GAMES.find((g) => g.bgg_id === id)).filter(Boolean);
    const elegido = elegirUno(pool, state.pickId);
    if (elegido) {
      state.pickId = elegido.bgg_id;
      state.scrollAlElegido = true;
      render();
    }
  });

  document.getElementById("sort-select").addEventListener("change", (e) => {
    state.sort = e.target.value;
    render();
  });
}


loadGames()
  .then((data) => {
    GAMES = data;
    setupControls();
    render();
  })
  .catch((err) => {
    document.getElementById("grid").innerHTML =
      `<div class="empty-state">No pude cargar los datos: ${escapeHtml(err.message)}</div>`;
  });
