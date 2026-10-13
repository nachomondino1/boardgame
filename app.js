let GAMES = [];

const state = {
  query: "",
  jugadores: null,
  estados: new Set(),
  ocasion: "Todas",
  soloGusto: false,
  sort: "p_x_r_desc",
};

const ESTADOS = ["Own", "Want to buy", "Watchlist", "Descartado"];

function normalize(str) {
  return (str || "")
    .toString()
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase();
}

function parseJugBest(jugBest, n) {
  if (!jugBest) return false;
  const cleaned = jugBest.trim();
  if (cleaned.includes("-")) {
    const [a, b] = cleaned.split("-").map((x) => parseInt(x, 10));
    return n >= a && n <= b;
  }
  const nums = cleaned.match(/\d+/g);
  if (!nums) return false;
  return nums.map(Number).includes(n);
}

function estadoBadgeClass(estado) {
  switch (estado) {
    case "Own": return "badge-own";
    case "Want to buy": return "badge-want";
    case "Watchlist": return "badge-watch";
    case "Descartado": return "badge-descartado";
    default: return "badge-other";
  }
}

function complexityColor(c) {
  if (c == null) return "#9a9a9a";
  const clamped = Math.max(0, Math.min(5, c));
  const hue = 120 - (clamped / 5) * 120;
  return `hsl(${hue}, 62%, 42%)`;
}

function matchesFilters(g) {
  if (state.query) {
    if (!normalize(g.nombre).includes(normalize(state.query))) return false;
  }
  if (state.jugadores != null) {
    if (g.jug_min == null || g.jug_max == null) return false;
    if (state.jugadores < g.jug_min || state.jugadores > g.jug_max) return false;
  }
  if (state.estados.size > 0 && !state.estados.has(g.estado)) return false;
  if (state.ocasion !== "Todas" && g.ocasion_ideal !== state.ocasion) return false;
  if (state.soloGusto) {
    if (g.complejidad == null || g.complejidad > 2.5) return false;
    if (g.duracion == null || g.duracion > 60) return false;
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

function cardTemplate(g) {
  const idealHoy = state.jugadores != null && parseJugBest(g.jug_best, state.jugadores);
  const jugRange = g.jug_min != null && g.jug_max != null
    ? (g.jug_min === g.jug_max ? `${g.jug_min}` : `${g.jug_min}–${g.jug_max}`)
    : "?";
  const complejidadHtml = g.complejidad != null
    ? `<span class="complexity-pill" style="background:${complexityColor(g.complejidad)}">${g.complejidad.toFixed(1)}</span>`
    : `<span class="tag">complejidad ?</span>`;

  const notesParts = [];
  if (g.pros) notesParts.push(`<p><strong>Pros:</strong> ${escapeHtml(g.pros)}</p>`);
  if (g.cons) notesParts.push(`<p><strong>Contras:</strong> ${escapeHtml(g.cons)}</p>`);
  if (g.notas) notesParts.push(`<p><strong>Notas:</strong> ${escapeHtml(g.notas)}</p>`);
  if (g.descripcion) notesParts.push(`<p>${escapeHtml(g.descripcion)}</p>`);
  const detailsHtml = notesParts.length
    ? `<details><summary>Más info</summary>${notesParts.join("")}</details>`
    : "";

  return `
    <div class="card">
      <div class="card-title-row">
        <div>
          <div class="card-title">${escapeHtml(g.nombre)}</div>
          <div class="card-sub">${escapeHtml(g.modo || "")}${g.anio ? " · " + g.anio : ""}</div>
        </div>
        <span class="badge ${estadoBadgeClass(g.estado)}">${escapeHtml(g.estado || "?")}</span>
      </div>
      <div class="stat-row">
        <span class="stat">👥 ${jugRange}${g.jug_best ? ` (mejor: ${escapeHtml(g.jug_best)})` : ""}</span>
        <span class="stat">⏱ ${g.duracion != null ? g.duracion + " min" : "?"}</span>
        <span class="stat">⚙️ ${complejidadHtml}</span>
      </div>
      <div class="stat-row">
        <span class="stat">BGG: ${g.puntaje_bgg != null ? g.puntaje_bgg.toFixed(2) : "?"}</span>
        <span class="stat">P×r: ${g.p_x_r != null ? g.p_x_r.toFixed(2) : "?"}</span>
        ${g.mi_puntaje != null ? `<span class="stat">Mi puntaje: ${g.mi_puntaje}/10</span>` : ""}
      </div>
      <div class="stat-row">
        ${g.ocasion_ideal ? `<span class="tag">${escapeHtml(g.ocasion_ideal)}</span>` : ""}
        ${idealHoy ? `<span class="badge ideal-badge">Ideal para hoy</span>` : ""}
      </div>
      ${detailsHtml}
    </div>
  `;
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

function render() {
  const filtered = sortGames(GAMES.filter(matchesFilters));
  const grid = document.getElementById("grid");
  const count = document.getElementById("result-count");
  count.textContent = `${filtered.length} juego${filtered.length === 1 ? "" : "s"}`;
  grid.innerHTML = filtered.length
    ? filtered.map(cardTemplate).join("")
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

  document.getElementById("ocasion-select").addEventListener("change", (e) => {
    state.ocasion = e.target.value;
    render();
  });

  document.getElementById("sort-select").addEventListener("change", (e) => {
    state.sort = e.target.value;
    render();
  });

  document.getElementById("gusto-toggle").addEventListener("change", (e) => {
    state.soloGusto = e.target.checked;
    render();
  });
}

function populateOcasionOptions() {
  const select = document.getElementById("ocasion-select");
  const ocasiones = [...new Set(GAMES.map((g) => g.ocasion_ideal).filter(Boolean))].sort();
  ocasiones.forEach((o) => {
    const opt = document.createElement("option");
    opt.value = o;
    opt.textContent = o;
    select.appendChild(opt);
  });
}

fetch("data.json")
  .then((r) => r.json())
  .then((data) => {
    GAMES = data;
    populateOcasionOptions();
    setupControls();
    render();
  })
  .catch((err) => {
    document.getElementById("grid").innerHTML =
      `<div class="empty-state">No pude cargar data.json: ${escapeHtml(err.message)}</div>`;
  });
