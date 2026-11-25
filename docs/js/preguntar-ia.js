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

// Los mejores del ranking de BGG que no tenés ni tuviste ni descartaste (uno por grupo de ediciones).
const IA_TOP_BGG = 40;
function topBggIA(games) {
  const excluidos = new Set(["Own", "Prev. owned", "Descartado", "Want to buy", "Want to play"]);
  const vistos = new Set();
  return games
    .filter((g) => g.ranking_bgg != null && !excluidos.has(g.estado))
    .sort((a, b) => a.ranking_bgg - b.ranking_bgg)
    .filter((g) => { const k = g.grupo || g.bgg_id; if (vistos.has(k)) return false; vistos.add(k); return true; })
    .slice(0, IA_TOP_BGG);
}

function armarPromptIA(games, top) {
  const tengo = games.filter((g) => g.estado === "Own");
  const quiero = games.filter((g) => g.estado === "Want to buy" || g.estado === "Want to play");
  return [
    "Sos un asesor de juegos de mesa. Tengo esta ludoteca y esta lista de candidatos. Ayudame a decidir qué comprar: " +
      "recomendá solo juegos de las listas que te paso (no inventes juegos ni precios), explicá por qué, " +
      "y decime qué me aporta cada uno que no tenga ya. Si te falta algo (cuántos jugadores somos, tiempo, presupuesto), preguntame.",
    `MI LUDOTECA (${tengo.length}):\n${tengo.map((g) => lineaJuegoIA(g, true)).join("\n") || "(vacía)"}`,
    `CANDIDATOS A COMPRAR O PROBAR (${quiero.length}):\n${quiero.map((g) => `${lineaJuegoIA(g, false)} [${g.estado}]`).join("\n") || "(ninguno)"}`,
    top && top.length ? `OTROS JUEGOS MUY BIEN VALORADOS EN BGG QUE NO TENGO (${top.length}, por ranking):\n${top.map((g) => `${lineaJuegoIA(g, false)}${g.ranking_bgg ? ` [ranking #${g.ranking_bgg}]` : ""}`).join("\n")}` : null,
    "Precios en pesos argentinos; los marcados como estimados son una referencia gruesa. Respondé en español. " +
      "Priorizá mis candidatos; sugerí de los otros solo si aportan algo que me falta. Si necesitás más opciones que las listadas, pedímelas o buscalas en BoardGameGeek.",
  ].filter(Boolean).join("\n\n");
}

function mountPreguntarIA(btn, getGames) {
  const dlg = document.createElement("dialog");
  dlg.className = "ia-dialog";
  dlg.innerHTML = `
    <form method="dialog"><button class="ia-close" aria-label="Cerrar">✕</button></form>
    <h3>🤖 Preguntale a una IA</h3>
    <p class="ia-help">Copiá este texto con tu ludoteca y tus candidatos, y pegalo en el chat que prefieras para que te ayude a elegir.</p>
    <textarea class="ia-text" readonly rows="10"></textarea>
    <div class="ia-actions">
      <button type="button" class="ia-copy">📋 Copiar</button>
      ${IA_DESTINOS.map(([n, u]) => `<a href="${u}" target="_blank" rel="noopener" class="ia-link">${n} ↗</a>`).join("")}
    </div>`;
  document.body.appendChild(dlg);
  const ta = dlg.querySelector(".ia-text");
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
    const rel = games.filter((g) => g.estado === "Own" || g.estado === "Want to buy" || g.estado === "Want to play").concat(top);
    ta.value = "Cargando…";
    dlg.showModal();
    await hydrate(rel).catch(() => {});
    ta.value = armarPromptIA(games, top);
  });
}
