// "Preguntale a una IA": arma un texto con tu ludoteca y tus candidatos a comprar para pegarlo en ChatGPT,
// Claude o Gemini. No hay backend ni API key: la conversación pasa afuera del sitio. Sin notas personales.

const IA_DESTINOS = [
  ["ChatGPT", "https://chatgpt.com/"],
  ["Claude", "https://claude.ai/new"],
  ["Gemini", "https://gemini.google.com/app"],
];

function lineaJuegoIA(g, conMiPuntaje) {
  const jug = g.jug_min != null && g.jug_max != null ? (g.jug_min === g.jug_max ? `${g.jug_min}` : `${g.jug_min}-${g.jug_max}`) : null;
  const best = jugBestRange(g);
  const mecs = mecanicasClave(g, 5);
  const precio = conMiPuntaje ? null : precioDe(g);
  const partes = [
    conMiPuntaje && g.mi_puntaje != null ? `mi puntaje ${g.mi_puntaje}` : null,
    g.puntaje_bgg != null ? `BGG ${g.puntaje_bgg.toFixed(1)}` : null,
    g.complejidad != null ? `complejidad ${g.complejidad.toFixed(1)}/5` : null,
    jug ? `${jug} jugadores${best ? ` (ideal ${best[0] === best[1] ? best[0] : best[0] + "-" + best[1]})` : ""}` : null,
    g.duracion != null ? `${g.duracion} min` : null,
    g.modo ? modoLabel(g.modo) : null,
    mecs.length ? mecs.join(", ") : null,
    precio ? `precio en Argentina ~$${Math.round(precio.valor).toLocaleString("es-AR")}${precio.real ? "" : " (estimado)"}` : null,
  ].filter(Boolean);
  return `- ${g.nombre}${g.anio ? ` (${g.anio})` : ""}: ${partes.join(" · ")}`;
}

// Resumen del análisis de Mi ludoteca (mismos cálculos que los gráficos), para que la IA vea fortalezas y huecos.
function perfilIA(own) {
  const lineas = [];
  const cal = calidadPorJugadores(own).map((d) => `${d.label} jug.: ${d.juegos.length ? `${d.juegos.length} juego${d.juegos.length === 1 ? "" : "s"}${d.promedio != null ? `, puntaje BGG promedio ${d.promedio.toFixed(1)}` : ""}` : "ninguno"}`);
  lineas.push(`Juegos recomendados por la comunidad de BGG según cantidad de jugadores (un juego cuenta en cada cantidad en que se recomienda):\n  ${cal.join("\n  ")}`);
  const bucket = (titulo, buckets, get) => {
    const b = bucketCounts(own, buckets, get);
    lineas.push(`${titulo}: ${b.filas.map((f) => `${f.label} ${f.valor}`).join(" · ")}`);
  };
  bucket("Complejidad", ANALISIS_COMPLEJIDAD, (g) => g.complejidad);
  bucket("Duración", ANALISIS_DURACION, (g) => g.duracion);
  const modos = new Map();
  own.forEach((g) => { if (g.modo) modos.set(g.modo, (modos.get(g.modo) || 0) + 1); });
  if (modos.size) lineas.push(`Tipo de juego: ${[...modos].sort((a, b) => b[1] - a[1]).map(([m, n]) => `${modoLabel(m)} ${n}`).join(" · ")}`);
  const mecs = new Map();
  own.forEach((g) => mecanicasClave(g, 99).forEach((m) => mecs.set(m, (mecs.get(m) || 0) + 1)));
  if (mecs.size) {
    lineas.push(`Mecánicas más frecuentes: ${[...mecs].sort((a, b) => b[1] - a[1]).slice(0, 10).map(([m, n]) => `${m} ${n}`).join(", ")}`);
    const faltan = MECANICAS_VOCAB.filter((m) => !mecs.has(m));
    if (faltan.length) lineas.push(`Mecánicas que no tengo: ${faltan.join(", ")}`);
  }
  return lineas.join("\n");
}

// Los mejores del ranking de BGG que no tenés ni tuviste ni descartaste (uno por grupo de ediciones).
const IA_TOP_BGG = 15;
function topBggIA(games) {
  const excluidos = new Set(["Own", "Prev. owned", "Descartado", "Want to buy", "Want to play"]);
  const vistos = new Set();
  return games
    .filter((g) => g.ranking_bgg != null && !excluidos.has(g.estado))
    .sort((a, b) => a.ranking_bgg - b.ranking_bgg)
    .filter((g) => { const k = g.grupo || g.bgg_id; if (vistos.has(k)) return false; vistos.add(k); return true; })
    .slice(0, IA_TOP_BGG);
}

function lineaTengoIA(g) {
  const best = jugBestRange(g);
  const partes = [
    g.mi_puntaje != null ? `mi puntaje ${g.mi_puntaje}` : null,
    g.puntaje_bgg != null ? `BGG ${g.puntaje_bgg.toFixed(1)}` : null,
    best ? `ideal ${best[0] === best[1] ? best[0] : best[0] + "-" + best[1]} jug.` : null,
  ].filter(Boolean);
  return `- ${g.nombre}${partes.length ? `: ${partes.join(" · ")}` : ""}`;
}

// Dónde puede leer la IA el resto del catálogo (archivos de texto que genera build_catalog.py).
function masOpcionesIA() {
  const url = (f) => new URL(`data/ia/${f}`, location.href).href;
  return "Si necesitás más opciones que las listadas, podés leer el catálogo completo en texto (una línea por juego, ordenado por ranking de BGG): " +
    `${url("catalogo.txt")} . También hay una lista por cantidad ideal de jugadores: ${url("jugadores-N.txt")} (N de 1 a 6; el 6 incluye 6 o más). ` +
    "Si no podés abrir links, decímelo y pedime las opciones a mí.";
}

// Juegos que pasan los filtros actuales de ¿Cuál comprar? (sin los que ya tengo), mejores primero, uno por grupo de ediciones.
// Sin filtros devuelve null; si dejan más de la mitad del catálogo, lista vacía (`muchos`): el top de BGG alcanza.
const IA_MAX_FILTRADOS = 30;
function filtradosIA(games, filtrados) {
  if (!filtrados || !filtrados.length || filtrados.length > games.length * 0.9) return null; // sin filtros (casi todo el catálogo)
  if (filtrados.length > games.length * 0.5) return { total: filtrados.length, lista: [], muchos: true };
  const vistos = new Set();
  const lista = filtrados
    .filter((g) => g.estado !== "Own" && g.estado !== "Descartado")
    .sort((a, b) => (a.ranking_bgg ?? 1e9) - (b.ranking_bgg ?? 1e9))
    .filter((g) => { const k = g.grupo || g.bgg_id; if (vistos.has(k)) return false; vistos.add(k); return true; });
  return { total: lista.length, lista: lista.slice(0, IA_MAX_FILTRADOS) };
}

function armarPromptIA(games, top, filtr) {
  const tengo = games.filter((g) => g.estado === "Own");
  const quiero = games.filter((g) => g.estado === "Want to buy" || g.estado === "Want to play");
  return [
    "Sos un asesor de juegos de mesa. Tengo esta ludoteca y esta lista de candidatos. Ayudame a decidir qué comprar: " +
      "recomendá solo juegos de las listas que te paso (no inventes juegos ni precios), explicá por qué, " +
      "y decime qué me aporta cada uno que no tenga ya, mirando el análisis para ver qué huecos o puntos flacos tiene mi ludoteca. Si te falta algo (cuántos jugadores somos, tiempo, presupuesto), preguntame.",
    `ANÁLISIS DE MI LUDOTECA (${tengo.length} juegos):\n${perfilIA(tengo)}`,
    `JUEGOS QUE TENGO:\n${tengo.map(lineaTengoIA).join("\n") || "(ninguno)"}`,
    `CANDIDATOS A COMPRAR O PROBAR (${quiero.length}):\n${quiero.map((g) => `${lineaJuegoIA(g, false)} [${g.estado}]`).join("\n") || "(ninguno)"}`,
    filtr && filtr.lista.length ? `JUEGOS QUE CUMPLEN LOS FILTROS QUE PUSE (${filtr.total}${filtr.total > filtr.lista.length ? `; te paso los ${filtr.lista.length} mejores por ranking de BGG` : ""}). Recomendame principalmente de acá:\n${filtr.lista.map((g) => `${lineaJuegoIA(g, false)}${g.ranking_bgg ? ` [ranking #${g.ranking_bgg}]` : ""}${g.estado ? ` [${g.estado}]` : ""}`).join("\n")}` : null,
    !(filtr && filtr.lista.length) && top && top.length ? `OTROS JUEGOS MUY BIEN VALORADOS EN BGG QUE NO TENGO (${top.length}, por ranking):\n${top.map((g) => `${lineaJuegoIA(g, false)}${g.ranking_bgg ? ` [ranking #${g.ranking_bgg}]` : ""}`).join("\n")}` : null,
    "Precios en pesos argentinos; los marcados como estimados son una referencia gruesa. Respondé en español. " +
      "Priorizá mis candidatos; sugerí de los otros solo si aportan algo que me falta.",
    masOpcionesIA(),
  ].filter(Boolean).join("\n\n");
}

function mountPreguntarIA(btn, getGames, getFiltrados) {
  const dlg = document.createElement("dialog");
  dlg.className = "ia-dialog";
  dlg.innerHTML = `
    <form method="dialog"><button class="ia-close" aria-label="Cerrar">✕</button></form>
    <h3>🤖 Preguntale a una IA</h3>
    <p class="ia-help">Copiá este texto con tu ludoteca y tus candidatos, y pegalo en el chat que prefieras para que te ayude a elegir.</p>
    <p class="ia-tip"></p>
    <textarea class="ia-text" readonly rows="10"></textarea>
    <div class="ia-actions">
      <button type="button" class="ia-copy">📋 Copiar</button>
      ${IA_DESTINOS.map(([n, u]) => `<a href="${u}" target="_blank" rel="noopener" class="ia-link">${n} ↗</a>`).join("")}
    </div>`;
  document.body.appendChild(dlg);
  const ta = dlg.querySelector(".ia-text");
  const tip = dlg.querySelector(".ia-tip");
  const copy = dlg.querySelector(".ia-copy");
  copy.addEventListener("click", () => {
    ta.select();
    const ok = navigator.clipboard ? navigator.clipboard.writeText(ta.value) : Promise.reject();
    ok.catch(() => document.execCommand("copy"));
    copy.textContent = "✓ Copiado";
    setTimeout(() => { copy.textContent = "📋 Copiar"; }, 1800);
  });
  btn.addEventListener("click", async () => {
    const games = getGames();
    const top = topBggIA(games);
    const filtr = filtradosIA(games, getFiltrados && getFiltrados());
    const rel = games.filter((g) => g.estado === "Own" || g.estado === "Want to buy" || g.estado === "Want to play").concat(top, filtr ? filtr.lista : []);
    tip.innerHTML = filtr && filtr.muchos
      ? `💡 Tus filtros todavía dejan <strong>${filtr.total}</strong> juegos, demasiados para listarlos. Sumá más (jugadores, duración, complejidad…) para achicar el mundo de opciones y que la IA elija entre los mejores que cumplen.`
      : filtr
      ? `🎯 Tus filtros achican el mundo: incluí los <strong>${filtr.lista.length}</strong> mejores de los <strong>${filtr.total}</strong> juegos que los cumplen, y la IA va a elegir principalmente entre ellos.`
      : `💡 Tip: antes de tocar este botón, poné filtros (jugadores, duración, complejidad…). Así la IA elige solo entre los juegos que te sirven, en vez de todo el catálogo.`;
    ta.value = "Cargando…";
    dlg.showModal();
    await hydrate(rel).catch(() => {});
    ta.value = armarPromptIA(games, top, filtr);
  });
}
