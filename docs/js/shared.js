// Helpers compartidos por index.html (Mi ludoteca), hoy.html y comprar.html.

function normalize(str) {
  return (str || "")
    .toString()
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase();
}

function jugBestRange(g) {
  if (g.jug_best_min == null && g.jug_best_max == null) return null;
  const lo = g.jug_best_min != null ? g.jug_best_min : g.jug_best_max;
  const hi = g.jug_best_max != null ? g.jug_best_max : g.jug_best_min;
  return [lo, hi];
}

function matchesJugBest(g, n) {
  if (n == null) return false;
  const range = jugBestRange(g);
  if (!range) return false;
  return n >= range[0] && n <= range[1];
}

function estadoBadgeClass(estado) {
  switch (estado) {
    case "Own": return "badge-own";
    case "Watchlist": return "badge-watch";
    case "Want to buy": return "badge-buy";
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

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str || "";
  return div.innerHTML;
}

function loadGames() {
  return fetch("data/data.json").then((r) => r.json());
}

// Colapsa una lista ya filtrada/ordenada: la primera aparición de cada
// grupo (la de mejor orden, porque la lista ya viene ordenada) se queda
// como representante de la tarjeta; el resto de sus variantes se cuelgan
// adentro en vez de ocupar su propia fila en la grilla. `g.grupo` ya viene
// calculado en data.json (ver construct_data.py / data/grupos.json).
function collapseGrupos(list) {
  const representantes = new Map(); // nombre del grupo -> entry
  const result = [];
  list.forEach((g) => {
    const grupoNombre = g.grupo;
    if (!grupoNombre) {
      result.push({ game: g, variantes: [], grupoNombre: null });
      return;
    }
    if (representantes.has(grupoNombre)) {
      representantes.get(grupoNombre).variantes.push(g);
    } else {
      const entry = { game: g, variantes: [], grupoNombre };
      representantes.set(grupoNombre, entry);
      result.push(entry);
    }
  });
  return result;
}

// Puntaje de "qué tan recomendado" es un juego para jugar HOY con N jugadores.
// No es una fórmula del Sheet: combina Mi gusto (duración <=60, complejidad <=2.5),
// si N es el número ideal de jugadores, y el puntaje personal/BGG como desempate.
function recommendationScore(g, n) {
  let score = 0;
  if (matchesJugBest(g, n)) score += 3;
  if (g.complejidad != null && g.complejidad <= 2.5) score += 1.5;
  if (g.duracion != null && g.duracion <= 60) score += 1;
  if (g.modo && normalize(g.modo).includes("cooperativo")) score += 0.5;
  if (g.mi_puntaje != null) score += g.mi_puntaje / 10;
  else if (g.puntaje_ajust_bgg != null) score += (g.puntaje_ajust_bgg / 10) * 0.5;
  return score;
}

function cardTemplate(g, opts) {
  opts = opts || {};
  const esBest = opts.jugadores != null && matchesJugBest(g, opts.jugadores);
  const jugRange = g.jug_min != null && g.jug_max != null
    ? (g.jug_min === g.jug_max ? `${g.jug_min}` : `${g.jug_min}–${g.jug_max}`)
    : "?";
  const jugBest = jugBestRange(g);
  const jugBestLabel = jugBest ? (jugBest[0] === jugBest[1] ? `${jugBest[0]}` : `${jugBest[0]}–${jugBest[1]}`) : null;
  const complejidadHtml = g.complejidad != null
    ? `<span class="complexity-pill" style="background:${complexityColor(g.complejidad)}">${g.complejidad.toFixed(1)}</span>`
    : `<span class="tag">complejidad ?</span>`;

  const notesParts = [];
  if (g.pros) notesParts.push(`<p><strong>Pros:</strong> ${escapeHtml(g.pros)}</p>`);
  if (g.cons) notesParts.push(`<p><strong>Contras:</strong> ${escapeHtml(g.cons)}</p>`);
  if (g.notas) notesParts.push(`<p><strong>Notas:</strong> ${escapeHtml(g.notas)}</p>`);
  const detailsHtml = notesParts.length
    ? `<details><summary>Más info</summary>${notesParts.join("")}</details>`
    : "";

  const variantes = opts.variantes || [];
  const variantesHtml = variantes.length
    ? `<details class="variantes">
        <summary>${variantes.length} variante${variantes.length === 1 ? "" : "s"} más de ${escapeHtml(opts.grupoNombre)}</summary>
        <ul>${variantes
          .map((v) => `<li>${v.bgg_url
            ? `<a href="${escapeHtml(v.bgg_url)}" target="_blank" rel="noopener">${escapeHtml(v.nombre)}</a>`
            : escapeHtml(v.nombre)}</li>`)
          .join("")}</ul>
      </details>`
    : "";

  const nombreHtml = g.bgg_url
    ? `<a class="card-title-link" href="${escapeHtml(g.bgg_url)}" target="_blank" rel="noopener">${escapeHtml(g.nombre)}</a>`
    : escapeHtml(g.nombre);

  const bestBadge = esBest
    ? `<span class="badge badge-best">👥 Best con ${opts.jugadores}</span>`
    : "";

  // link_cazagangas/cazagangas_status ya vienen resueltos desde
  // check_cazagangas_links.py + integrate_data.py: solo se muestra cuando
  // sabemos que el link responde 200 (no uno armado a ciegas que puede
  // dar 404 — ver DATA_PLAYBOOK.md).
  const cazagangasHtml = opts.showCazagangas && g.cazagangas_status === "200"
    ? `<a class="stat stat-link" href="${escapeHtml(g.link_cazagangas)}" target="_blank" rel="noopener">💰 Cazagangas ↗</a>`
    : "";

  const compraHtml = (g.costo != null || g.precio_calidad != null || g.link_tienda || cazagangasHtml)
    ? `
      <div class="stat-row">
        ${g.costo != null ? `<span class="stat">💰 $${g.costo.toLocaleString("es-AR")}</span>` : ""}
        ${g.precio_calidad != null ? `<span class="stat">Precio/calidad: ${g.precio_calidad.toFixed(2)}</span>` : ""}
        ${g.link_tienda ? `<a class="stat stat-link" href="${escapeHtml(g.link_tienda)}" target="_blank" rel="noopener">Tienda ↗</a>` : ""}
        ${cazagangasHtml}
      </div>`
    : "";

  return `
    <div class="card">
      <div class="card-title-row">
        <div>
          <div class="card-title">${nombreHtml}</div>
          <div class="card-sub">${escapeHtml(g.modo || "")}${g.anio ? " · " + g.anio : ""}</div>
        </div>
        <span class="badge ${estadoBadgeClass(g.estado)}">${escapeHtml(g.estado || "?")}</span>
      </div>
      <div class="stat-row">
        <span class="stat">👥 ${jugRange}${jugBestLabel ? ` (mejor: ${jugBestLabel})` : ""}</span>
        <span class="stat">⏱ ${g.duracion != null ? g.duracion + " min" : "?"}</span>
        <span class="stat">⚙️ ${complejidadHtml}</span>
      </div>
      <div class="stat-row">
        <span class="stat">BGG: ${g.puntaje_bgg != null ? g.puntaje_bgg.toFixed(2) : "?"}</span>
        <span class="stat">Puntaje ajustado: ${g.puntaje_ajust_bgg != null ? g.puntaje_ajust_bgg.toFixed(2) : "?"}</span>
        ${g.mi_puntaje != null ? `<span class="stat">Mi puntaje: ${g.mi_puntaje}/10</span>` : ""}
      </div>
      ${bestBadge ? `<div class="stat-row">${bestBadge}</div>` : ""}
      ${compraHtml}
      ${detailsHtml}
      ${variantesHtml}
    </div>
  `;
}

// En mobile, el panel de filtros arranca colapsado (botón "Filtros") para no
// tapar los resultados con la pantalla entera de controles; en desktop el
// botón queda oculto por CSS y el panel se ve siempre expandido.
function setupFiltersToggle() {
  const toggle = document.getElementById("filters-toggle");
  const panel = toggle ? toggle.closest(".filters-panel") : null;
  if (!toggle || !panel) return;
  toggle.addEventListener("click", () => {
    const open = panel.classList.toggle("open");
    toggle.setAttribute("aria-expanded", open ? "true" : "false");
  });
}

function navTemplate(active) {
  const links = [
    { href: "index.html", emoji: "📚", label: "Mi ludoteca" },
    { href: "hoy.html", emoji: "🎲", label: "¿Qué jugamos hoy?" },
    { href: "comprar.html", emoji: "🛒", label: "¿Cuál comprar?" },
    { href: "comparar.html", emoji: "⚔️", label: "Comparar" },
  ];
  const linksHtml = links
    .map((l) => `<a href="${l.href}" class="${l.href === active ? "active" : ""}">${l.emoji} ${l.label}</a>`)
    .join("");
  return `
    <div class="top-nav">
      <a href="index.html" class="nav-brand">🎲 Juegos de mesa</a>
      <div class="nav-links">${linksHtml}</div>
    </div>
  `;
}
