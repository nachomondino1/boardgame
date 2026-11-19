// Nav entre páginas. Se carga sin "defer", justo debajo de <div id="nav">, para que aparezca con el
// primer dibujo de la página y no cuando terminan de bajar y correr los demás scripts.
function navTemplate(active) {
  // En mobile la barra va abajo: el logo (que lleva al inicio) no se ve, y los nombres se acortan.
  const links = [
    { href: "ludoteca.html", emoji: "📚", label: "Mi ludoteca", short: "Ludoteca" },
    { href: "hoy.html", emoji: "🎲", label: "¿Qué jugamos hoy?", short: "Jugar hoy" },
    { href: "comprar.html", emoji: "🛒", label: "¿Cuál comprar?", short: "Comprar" },
  ];
  const homeHtml = `<a href="index.html" class="nav-home"><span class="nav-emoji" aria-hidden="true">🏠</span><span class="nav-short">Inicio</span></a>`;
  const linksHtml = homeHtml + links
    .map((l) => `<a href="${l.href}"${l.href === active ? ' class="active"' : ""}><span class="nav-emoji" aria-hidden="true">${l.emoji}</span><span class="nav-label">${l.label}</span><span class="nav-short">${l.short}</span></a>`)
    .join("");
  return `
    <div class="top-nav">
      <a href="index.html" class="nav-brand">🎲 Juegos de mesa</a>
      <div class="nav-links">${linksHtml}</div>
    </div>
  `;
}

const navEl = document.getElementById("nav");
if (navEl) navEl.innerHTML = navTemplate((location.pathname.split("/").pop().replace(/\.html$/, "") || "index") + ".html");
