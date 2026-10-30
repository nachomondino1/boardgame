// "Cargá tus juegos": panel para armar la colección del visitante. Dos vías:
// usuario de BGG (se activa con la función /api/collection) y marcar a mano
// buscando en names.json. Se guarda en localStorage (ver shared.js). Cada vez
// que cambia la colección llama a onChange para que la página se actualice.

const MAX_RESULTS = 20;
const ESTADOS_MARCABLES = [
  { label: "Lo tengo", flag: "own" },
  { label: "Lo tuve", flag: "prevowned" },
  { label: "Quiero comprar", flag: "wanttobuy" },
];

function mountCollectionLoader(container, { onChange }) {
  let names = []; // [{ id, nombre, norm }] en orden de ranking: los más populares salen primero
  let nameById = new Map();
  let namesPromise = null;
  let collection = loadCollection();

  container.innerHTML = `
    <div class="col-loader">
      <div class="col-loader__block">
        <h3 class="col-loader__label">Con tu usuario de BGG</h3>
        <form class="col-user" data-user-form>
          <input type="text" name="user" placeholder="Tu usuario de BGG" autocomplete="off" disabled />
          <button type="submit" class="col-user__btn" disabled>Traer mi colección</button>
        </form>
        <p class="col-hint">Próximamente. Por ahora, marcá tus juegos a mano.</p>
      </div>
      <div class="col-loader__block">
        <h3 class="col-loader__label">O marcá tus juegos a mano</h3>
        <input type="text" class="col-search" placeholder="Buscar juego (ej: catan)" autocomplete="off" />
        <ul class="col-list" data-results></ul>
        <div class="col-heading">
          <h3 class="col-loader__label" data-mine-title>Tu colección</h3>
          <button type="button" class="col-clear" data-clear hidden>Borrar mis datos</button>
        </div>
        <ul class="col-list" data-mine></ul>
        <p class="col-hint">Se guarda solo en este navegador.</p>
      </div>
    </div>`;

  const search = container.querySelector(".col-search");
  const resultsEl = container.querySelector("[data-results]");
  const mineEl = container.querySelector("[data-mine]");

  function flagActivo(entry) {
    const marcado = ESTADOS_MARCABLES.find((e) => entry && entry[e.flag]);
    return marcado ? marcado.flag : null;
  }

  // Un solo estado a la vez; volver a tocar el activo lo quita. Si no queda ni
  // estado ni puntaje, el juego sale de la colección.
  function guardarEntrada(id, entry) {
    if (flagActivo(entry) || entry.rating != null) collection.games[id] = entry;
    else delete collection.games[id];
    collection.source = collection.source || "manual";
    saveCollection(collection);
    render();
    onChange(collection);
  }

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
    const query = normalize(search.value.trim());
    if (!query) {
      resultsEl.innerHTML = "";
    } else {
      const found = names.filter((n) => n.norm.includes(query)).slice(0, MAX_RESULTS);
      resultsEl.innerHTML = found.length
        ? found.map((n) => rowHtml(n.id, n.nombre, false)).join("")
        : `<li class="col-empty">${namesPromise && !names.length ? "Cargando juegos…" : "No encontré juegos con ese nombre."}</li>`;
    }

    const ids = Object.keys(collection.games)
      .filter((id) => nameById.has(id))
      .sort((a, b) => nameById.get(a).localeCompare(nameById.get(b), "es"));
    const total = Object.keys(collection.games).length;
    container.querySelector("[data-mine-title]").textContent = `Tu colección (${total})`;
    container.querySelector("[data-clear]").hidden = total === 0;
    mineEl.innerHTML = !total
      ? `<li class="col-empty">Todavía no marcaste ningún juego. Buscá uno arriba.</li>`
      : ids.length
        ? ids.map((id) => rowHtml(id, nameById.get(id), true)).join("")
        : `<li class="col-empty">Cargando tu colección…</li>`;
  }

  // names.json (0,4 MB comprimido) se pide recién cuando alguien usa el panel,
  // no al abrir la página.
  function ensureNames() {
    if (!namesPromise) {
      namesPromise = fetch("data/names.json")
        .then((r) => {
          if (!r.ok) throw new Error(`names.json: HTTP ${r.status}`);
          return r.json();
        })
        .then(({ rows }) => {
          names = rows.map(([id, nombre]) => ({ id, nombre, norm: normalize(nombre) }));
          nameById = new Map(rows);
          render();
        })
        .catch((err) => {
          namesPromise = null;
          resultsEl.innerHTML = `<li class="col-empty">No pude cargar los datos: ${escapeHtml(err.message)}</li>`;
        });
    }
    return namesPromise;
  }

  search.addEventListener("focus", ensureNames);
  search.addEventListener("input", () => { ensureNames(); render(); });
  container.addEventListener("click", (e) => {
    const btn = e.target.closest(".col-btn");
    if (btn) setFlag(btn.dataset.id, btn.dataset.flag);
  });
  container.addEventListener("change", (e) => {
    if (e.target.classList.contains("col-rating")) {
      setRating(e.target.dataset.id, e.target.value ? Number(e.target.value) : null);
    }
  });
  container.querySelector("[data-clear]").addEventListener("click", () => {
    if (!confirm("¿Borrar toda tu colección de este navegador?")) return;
    collection = emptyCollection();
    saveCollection(collection);
    render();
    onChange(collection);
  });

  // Si ya había una colección guardada, hace falta names.json para mostrar los nombres.
  if (Object.keys(collection.games).length) ensureNames();
  render();
}
