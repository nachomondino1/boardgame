// Helpers compartidos por index.html (catálogo), hoy.html y comprar.html.

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

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str || "";
  return div.innerHTML;
}

function loadGames() {
  return fetch("data/data.json").then((r) => r.json());
}

// Puntaje de "qué tan recomendado" es un juego para jugar HOY con N jugadores.
// No es una fórmula del Sheet: combina Mi gusto (duración <=60, complejidad <=2.5),
// si N es el número ideal de jugadores, y el puntaje personal/BGG como desempate.
function recommendationScore(g, n) {
  let score = 0;
  if (n != null && parseJugBest(g.jug_best, n)) score += 3;
  if (g.complejidad != null && g.complejidad <= 2.5) score += 1.5;
  if (g.duracion != null && g.duracion <= 60) score += 1;
  if (g.modo && normalize(g.modo).includes("cooperativo")) score += 0.5;
  if (g.mi_puntaje != null) score += g.mi_puntaje / 10;
  else if (g.p_x_r != null) score += (g.p_x_r / 10) * 0.5;
  return score;
}

function cardTemplate(g, opts) {
  opts = opts || {};
  const idealHoy = opts.jugadores != null && parseJugBest(g.jug_best, opts.jugadores);
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

  const bggLink = g.bgg_url
    ? `<a class="bgg-link" href="${escapeHtml(g.bgg_url)}" target="_blank" rel="noopener">BGG ↗</a>`
    : "";

  const recomendadoBadge = opts.recomendado
    ? `<span class="badge ideal-badge">✨ Recomendado</span>`
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
        ${recomendadoBadge}
        ${bggLink}
      </div>
      ${detailsHtml}
    </div>
  `;
}

function navTemplate(active) {
  const links = [
    { href: "index.html", label: "Catálogo" },
    { href: "hoy.html", label: "¿Qué jugamos hoy?" },
    { href: "comprar.html", label: "¿Cuál comprar?" },
  ];
  return `<nav class="top-nav">${links
    .map((l) => `<a href="${l.href}" class="${l.href === active ? "active" : ""}">${l.label}</a>`)
    .join("")}</nav>`;
}
