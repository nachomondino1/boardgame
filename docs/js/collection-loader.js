// "Cargá tus juegos": panel para armar la colección del visitante. Dos vías:
// usuario de BGG (se activa con la función /api/collection) y marcar a mano
// buscando en names.json. Se guarda en localStorage (ver shared.js). Cada vez
// que cambia la colección llama a onChange para que la página se actualice.

const MAX_RESULTS = 20;
const PENDING_RETRIES = 8; // 202 de BGG: reintentos de la página, además de los de la función
const PENDING_DELAY_MS = 4000;
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
  let saveFailed = false;

  container.innerHTML = `
    <div class="col-loader">
      <div class="col-loader__block">
        <h3 class="col-loader__label">Con tu usuario de BGG</h3>
        <form class="col-user" data-user-form>
          <input type="text" name="user" placeholder="Tu usuario de BGG" autocomplete="off" maxlength="40" />
          <button type="submit" class="col-user__btn">Traer mi colección</button>
        </form>
        <p class="col-hint" data-user-hint role="status">Tiene que ser público: BGG no deja leer colecciones ocultas.</p>
      </div>
      <div class="col-loader__block">
        <h3 class="col-loader__label">O marcá tus juegos a mano</h3>
        <input type="text" class="col-search" placeholder="Buscar juego (ej: catan)" autocomplete="off" />
        <ul class="col-list" data-results></ul>
        <div class="col-heading">
          <h3 class="col-loader__label" data-mine-title>Tu colección</h3>
          <button type="button" class="col-clear" data-clear hidden>Borrar mis datos</button>
        </div>
        <p class="col-saved" data-saved role="status"></p>
        <ul class="col-list" data-mine></ul>
      </div>
    </div>`;

  const search = container.querySelector(".col-search");
  const userForm = container.querySelector("[data-user-form]");
  const userHint = container.querySelector("[data-user-hint]");
  const resultsEl = container.querySelector("[data-results]");
  const mineEl = container.querySelector("[data-mine]");
  const savedEl = container.querySelector("[data-saved]");

  // Cada cambio se guarda en el momento (no hay botón "Guardar"): esta línea lo deja a la vista.
  function persist() {
    saveFailed = !saveCollection(collection);
  }

  function savedMessage() {
    if (saveFailed) return "⚠ No pude guardar en este navegador (¿ventana privada?). Si cambiás de página, se pierde.";
    if (!Object.keys(collection.games).length) return "Todavía no cargaste juegos.";
    const hora = collection.savedAt
      ? new Date(collection.savedAt).toLocaleTimeString("es-AR", { hour: "2-digit", minute: "2-digit", hour12: false })
      : "";
    return `✓ Guardado en este navegador${hora ? ` a las ${hora}` : ""}. Podés cambiar de página tranquilo.`;
  }

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
    persist();
    render();
    onChange(collection);
  }

  function setFlag(id, flag) {
    const entry = collection.games[id] || { own: false, prevowned: false, wanttobuy: false, rating: null };
    const activar = flagActivo(entry) !== flag;
    ESTADOS_MARCABLES.forEach((e) => { entry[e.flag] = activar && e.flag === flag; });
    guardarEntrada(id, entry);
  }

  function removeGame(id) {
    delete collection.games[id];
    persist();
    render();
    onChange(collection);
  }

  function rowHtml(id, nombre) {
    const entry = collection.games[id];
    const activo = flagActivo(entry);
    const botones = ESTADOS_MARCABLES
      .map((e) => `<button type="button" class="col-btn${activo === e.flag ? " active" : ""}" data-id="${escapeHtml(id)}" data-flag="${e.flag}">${e.label}</button>`)
      .join("");
    // Quitar borra el juego de la colección guardada en este navegador (no cambia nada en BGG).
    const quitar = entry
      ? `<button type="button" class="col-remove" data-remove="${escapeHtml(id)}" title="Quitar de mi colección (solo en este navegador, no cambia BGG)" aria-label="Quitar ${escapeHtml(nombre)} de mi colección">✕ Quitar</button>`
      : "";
    return `<li class="col-row"><span class="col-name">${escapeHtml(nombre)}</span><span class="col-actions">${botones}${quitar}</span></li>`;
  }

  function render() {
    const query = normalize(search.value.trim());
    if (!query) {
      resultsEl.innerHTML = "";
    } else {
      const found = names.filter((n) => n.norm.includes(query)).slice(0, MAX_RESULTS);
      resultsEl.innerHTML = found.length
        ? found.map((n) => rowHtml(n.id, n.nombre)).join("")
        : `<li class="col-empty">${namesPromise && !names.length ? "Cargando juegos…" : "No encontré juegos con ese nombre."}</li>`;
    }

    const ids = Object.keys(collection.games)
      .filter((id) => nameById.has(id))
      .sort((a, b) => nameById.get(a).localeCompare(nameById.get(b), "es"));
    const total = Object.keys(collection.games).length;
    container.querySelector("[data-mine-title]").textContent = `Tu colección (${total})`;
    container.querySelector("[data-clear]").hidden = total === 0;
    savedEl.textContent = savedMessage();
    mineEl.innerHTML = !total
      ? `<li class="col-empty">Todavía no marcaste ningún juego. Buscá uno arriba.</li>`
      : ids.length
        ? ids.map((id) => rowHtml(id, nameById.get(id))).join("")
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

  // Trae la colección desde /api/collection. BGG a veces responde 202 ("estoy
  // preparando la lista"): se reintenta unos segundos antes de rendirse.
  async function fetchBggCollection(user) {
    for (let attempt = 0; attempt < PENDING_RETRIES; attempt++) {
      let response;
      try {
        response = await fetch(`/api/collection?user=${encodeURIComponent(user)}`);
      } catch (e) {
        throw new Error("No pude conectar con el servidor. Probá de nuevo en un rato.");
      }
      const body = await response.json().catch(() => ({}));
      if (response.status === 200) return body;
      if (response.status !== 202) throw new Error(body.message || `Error ${response.status}`);
      userHint.textContent = "BGG está preparando tu colección, esperá unos segundos…";
      await new Promise((resolve) => setTimeout(resolve, PENDING_DELAY_MS));
    }
    throw new Error("BGG todavía no tiene lista tu colección. Probá de nuevo en un minuto.");
  }

  userForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const user = userForm.elements.user.value.trim();
    if (!user) return;
    if (collection.source === "manual" && Object.keys(collection.games).length
        && !confirm("Esto reemplaza los juegos que marcaste a mano. ¿Seguir?")) return;
    const button = userForm.querySelector("button");
    button.disabled = true;
    userHint.textContent = "Buscando tu colección en BGG…";
    try {
      const result = await fetchBggCollection(user);
      if (!result.count) {
        userHint.textContent = `Encontré a ${user}, pero no tiene juegos en su colección (o la tiene oculta).`;
        return;
      }
      const games = {};
      result.games.forEach((g) => { games[g.id] = { own: g.own, prevowned: g.prevowned, wanttobuy: g.wanttobuy, rating: g.rating }; });
      collection = { source: "bgg", user: result.user, savedAt: null, games };
      persist();
      await ensureNames();
      const desconocidos = Object.keys(games).filter((id) => !nameById.has(id)).length;
      render();
      onChange(collection);
      userHint.textContent = `Listo: ${result.count} juegos de ${result.user}.`
        + (saveFailed ? "" : " Ya quedó guardada en este navegador.")
        + (desconocidos ? ` ${desconocidos} no están en el catálogo y no se muestran.` : "");
    } catch (err) {
      userHint.textContent = err.message;
    } finally {
      button.disabled = false;
    }
  });
  if (collection.source === "bgg" && collection.user) userForm.elements.user.value = collection.user;

  search.addEventListener("focus", ensureNames);
  search.addEventListener("input", () => { ensureNames(); render(); });
  container.addEventListener("click", (e) => {
    const btn = e.target.closest(".col-btn");
    if (btn) setFlag(btn.dataset.id, btn.dataset.flag);
    const remove = e.target.closest(".col-remove");
    if (remove) removeGame(remove.dataset.remove);
  });
  container.querySelector("[data-clear]").addEventListener("click", () => {
    if (!confirm("¿Borrar toda tu colección de este navegador?")) return;
    collection = emptyCollection();
    persist();
    render();
    onChange(collection);
  });

  // Si ya había una colección guardada, hace falta names.json para mostrar los nombres.
  if (Object.keys(collection.games).length) ensureNames();
  render();
}
