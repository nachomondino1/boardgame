let GAMES = [];

const state = { a: null, b: null };

// Cada fila de la tabla: cómo sacar el valor, cómo mostrarlo, y si aplica
// (y en qué sentido) resaltar cuál de los dos juegos "gana" esa fila.
const ROWS = [
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
  { label: "Puntaje ajustado", get: (g) => g.puntaje_ajust_bgg, format: (v) => v.toFixed(2), better: "higher" },
  { label: "Mi puntaje", get: (g) => g.mi_puntaje, format: (v) => `${v}/10`, better: "higher" },
  { label: "Costo", get: (g) => g.costo, format: (v) => `$${v.toLocaleString("es-AR")}`, better: "lower" },
  { label: "Precio / calidad", get: (g) => g.precio_calidad, format: (v) => v.toFixed(2), better: "higher" },
  { label: "Diseñador", get: (g) => g.disenador },
  { label: "Mecánicas", get: (g) => (g.mecanicas && g.mecanicas.length ? g.mecanicas.join(", ") : null) },
  { label: "Categorías", get: (g) => (g.categorias && g.categorias.length ? g.categorias.join(", ") : null) },
];

function findGame(name) {
  if (!name) return null;
  const norm = normalize(name);
  return GAMES.find((g) => normalize(g.nombre) === norm) || null;
}

function cellHtml(game, row, winner) {
  if (!game) return `<td class="compare-cell compare-cell--empty">—</td>`;
  const raw = row.get(game);
  if (raw == null || raw === "") return `<td class="compare-cell compare-cell--empty">?</td>`;
  const text = row.format ? row.format(typeof raw === "string" ? Number(raw) : raw) : raw;
  const cls = winner ? "compare-cell compare-cell--winner" : "compare-cell";
  return `<td class="${cls}">${escapeHtml(String(text))}</td>`;
}

function rowWinner(row, a, b) {
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

function render() {
  const { a, b } = state;
  const container = document.getElementById("compare-result");

  if (!a && !b) {
    container.innerHTML = `<div class="empty-state">Elegí dos juegos arriba para compararlos.</div>`;
    return;
  }

  const nameCell = (game, placeholder) => game
    ? `<div class="compare-name">${escapeHtml(game.nombre)}</div>`
    : `<div class="compare-name compare-name--empty">${placeholder}</div>`;

  const rowsHtml = ROWS.map((row) => {
    const winner = rowWinner(row, a, b);
    return `
      <tr>
        <th scope="row">${escapeHtml(row.label)}</th>
        ${cellHtml(a, row, winner === "a")}
        ${cellHtml(b, row, winner === "b")}
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

function syncUrl() {
  const params = new URLSearchParams();
  if (state.a) params.set("a", state.a.nombre);
  if (state.b) params.set("b", state.b.nombre);
  const qs = params.toString();
  history.replaceState(null, "", qs ? `?${qs}` : location.pathname);
}

function setupControls() {
  const inputA = document.getElementById("game-a");
  const inputB = document.getElementById("game-b");

  const datalist = document.getElementById("games-list");
  const names = [...new Set(GAMES.map((g) => g.nombre))].sort((x, y) => x.localeCompare(y, "es"));
  datalist.innerHTML = names.map((n) => `<option value="${escapeHtml(n)}"></option>`).join("");

  inputA.addEventListener("change", () => {
    state.a = findGame(inputA.value);
    syncUrl();
    render();
  });
  inputB.addEventListener("change", () => {
    state.b = findGame(inputB.value);
    syncUrl();
    render();
  });

  const params = new URLSearchParams(location.search);
  const presetA = params.get("a");
  const presetB = params.get("b");
  if (presetA) {
    inputA.value = presetA;
    state.a = findGame(presetA);
  }
  if (presetB) {
    inputB.value = presetB;
    state.b = findGame(presetB);
  }
}

document.getElementById("nav").innerHTML = navTemplate("comparar.html");

loadGames()
  .then((data) => {
    GAMES = data;
    setupControls();
    render();
  })
  .catch((err) => {
    document.getElementById("compare-result").innerHTML =
      `<div class="empty-state">No pude cargar data.json: ${escapeHtml(err.message)}</div>`;
  });
