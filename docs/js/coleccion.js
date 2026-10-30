// Mi colección: buscar un juego en names.json y marcar Own / Prev. owned / Want to buy.
// Se guarda en localStorage (ver loadCollection/saveCollection en shared.js).

const MAX_RESULTS = 20;
const ESTADOS_MARCABLES = [
  { label: "Lo tengo", flag: "own" },
  { label: "Lo tuve", flag: "prevowned" },
  { label: "Quiero comprar", flag: "wanttobuy" },
];

let NAMES = []; // [{ id, nombre, norm }] en orden de ranking: los más populares salen primero
let NAME_BY_ID = new Map();
let collection = loadCollection();

function flagActivo(entry) {
  const marcado = ESTADOS_MARCABLES.find((e) => entry && entry[e.flag]);
  return marcado ? marcado.flag : null;
}

// Un solo estado a la vez; volver a tocar el activo lo quita. Si no queda ni
// estado ni puntaje, el juego sale de la colección.
function setFlag(id, flag) {
  const entry = collection.games[id] || { own: false, prevowned: false, wanttobuy: false, rating: null };
  const activar = flagActivo(entry) !== flag;
  ESTADOS_MARCABLES.forEach((e) => { entry[e.flag] = activar && e.flag === flag; });
  guardarEntrada(id, entry);
}

function setRating(id, rating) {
  const entry = collection.games[id];
  if (!entry) return;
  entry.rating = rating;
  guardarEntrada(id, entry);
}

function guardarEntrada(id, entry) {
  if (flagActivo(entry) || entry.rating != null) collection.games[id] = entry;
  else delete collection.games[id];
  collection.source = collection.source || "manual";
  saveCollection(collection);
  render();
}

function rowHtml(id, nombre, conPuntaje) {
  const entry = collection.games[id];
  const activo = flagActivo(entry);
  const botones = ESTADOS_MARCABLES
    .map((e) => `<button type="button" class="col-btn${activo === e.flag ? " active" : ""}" data-id="${escapeHtml(id)}" data-flag="${e.flag}">${e.label}</button>`)
    .join("");
  const puntaje = conPuntaje
    ? `<select class="col-rating" data-id="${escapeHtml(id)}" aria-label="Mi puntaje de ${escapeHtml(nombre)}">
        <option value="">Sin puntaje</option>
        ${[10, 9, 8, 7, 6, 5, 4, 3, 2, 1].map((n) => `<option value="${n}"${entry && entry.rating === n ? " selected" : ""}>${n}/10</option>`).join("")}
      </select>`
    : "";
  return `<li class="col-row"><span class="col-name">${escapeHtml(nombre)}</span><span class="col-actions">${botones}${puntaje}</span></li>`;
}

function render() {
  const query = normalize(document.getElementById("search").value.trim());
  const results = document.getElementById("results");
  if (!query) {
    results.innerHTML = "";
  } else {
    const found = NAMES.filter((n) => n.norm.includes(query)).slice(0, MAX_RESULTS);
    results.innerHTML = found.length
      ? found.map((n) => rowHtml(n.id, n.nombre, false)).join("")
      : `<li class="col-empty">No encontré juegos con ese nombre.</li>`;
  }

  const ids = Object.keys(collection.games)
    .filter((id) => NAME_BY_ID.has(id))
    .sort((a, b) => NAME_BY_ID.get(a).localeCompare(NAME_BY_ID.get(b), "es"));
  document.getElementById("mine-title").textContent = `Tu colección (${ids.length})`;
  document.getElementById("clear-all").hidden = ids.length === 0;
  document.getElementById("mine").innerHTML = ids.length
    ? ids.map((id) => rowHtml(id, NAME_BY_ID.get(id), true)).join("")
    : `<li class="col-empty">Todavía no marcaste ningún juego. Buscá uno arriba.</li>`;
}

function setupControls() {
  document.getElementById("search").addEventListener("input", render);
  document.querySelector("main").addEventListener("click", (e) => {
    const btn = e.target.closest(".col-btn");
    if (btn) setFlag(btn.dataset.id, btn.dataset.flag);
  });
  document.querySelector("main").addEventListener("change", (e) => {
    if (e.target.classList.contains("col-rating")) {
      setRating(e.target.dataset.id, e.target.value ? Number(e.target.value) : null);
    }
  });
  document.getElementById("clear-all").addEventListener("click", () => {
    if (!confirm("¿Borrar toda tu colección de este navegador?")) return;
    collection = emptyCollection();
    saveCollection(collection);
    render();
  });
}

document.getElementById("nav").innerHTML = navTemplate("coleccion.html");

fetch("data/names.json")
  .then((r) => {
    if (!r.ok) throw new Error(`names.json: HTTP ${r.status}`);
    return r.json();
  })
  .then(({ rows }) => {
    NAMES = rows.map(([id, nombre]) => ({ id, nombre, norm: normalize(nombre) }));
    NAME_BY_ID = new Map(rows);
    setupControls();
    render();
  })
  .catch((err) => {
    document.getElementById("results").innerHTML =
      `<li class="col-empty">No pude cargar los datos: ${escapeHtml(err.message)}</li>`;
  });
