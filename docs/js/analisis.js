// Análisis de la ludoteca: números y gráficos de barras sobre los juegos Own, calculados
// en el navegador. Vive en Mi ludoteca, al pie, pero no depende de esa página: recibe el
// contenedor y la lista de juegos (con estado y mi_puntaje ya aplicados), así que se puede
// mover a otra página sin tocar nada de acá.
// Necesita shared.js (escapeHtml, jugBestRange, hydrate).

const ANALISIS_JUGADORES_MAX = 7; // la última barra agrupa "7 o más"

const ANALISIS_COMPLEJIDAD = BUCKETS_COMPLEJIDAD.map((b) => ({ label: `${b.label} (${b.hint})`, match: b.match }));
const ANALISIS_DURACION = BUCKETS_DURACION;

function pluralJuegos(n) {
  return `${n} juego${n === 1 ? "" : "s"}`;
}

// Una barra por fila: etiqueta, barra proporcional al máximo y el valor al final.
// Una sola serie, así que no lleva leyenda: el título dice qué se está contando.
function barChartHtml({ titulo, subtitulo, filas, nota, ayuda }) {
  const max = Math.max(1, ...filas.map((f) => f.valor));
  const rows = filas
    .map((f) => {
      const title = escapeHtml(f.hint ? `${f.label}: ${f.hint}` : `${f.label}: ${pluralJuegos(f.valor)}`);
      const cero = f.valor ? "" : " bar-row--cero";
      const fila = `
        <span class="bar-label">${escapeHtml(f.label)}</span>
        <span class="bar-track"><span class="bar-fill" style="width:${(f.valor / max) * 100}%"></span></span>
        <span class="bar-value">${f.valor}</span>`;
      // Con juegos, la fila se despliega para ver cuáles son; sin juegos queda fija.
      if (f.juegos && f.juegos.length) {
        const lista = [...f.juegos].sort((a, b) => a.localeCompare(b, "es")).map((n) => `<li>${escapeHtml(n)}</li>`).join("");
        return `<li class="bar-item"><details class="bar-details"><summary class="bar-row${cero}" title="${title}">${fila}</summary><ul class="bar-games">${lista}</ul></details></li>`;
      }
      return `<li class="bar-item"><div class="bar-row${cero}" title="${title}">${fila}</div></li>`;
    })
    .join("");
  return `
    <article class="analisis-card">
      <h3 class="analisis-card__title">${escapeHtml(titulo)}</h3>
      ${subtitulo ? `<p class="analisis-card__sub">${escapeHtml(subtitulo)}</p>` : ""}
      <ul class="bar-list">${rows}</ul>
      ${nota ? `<p class="analisis-card__note">${nota}</p>` : ""}
      ${ayuda ? `<details class="analisis-card__help"><summary>ℹ️ ¿Qué es cada una?</summary><dl>${ayuda.map(([t, d]) => `<dt>${escapeHtml(t)}</dt><dd>${escapeHtml(d)}</dd>`).join("")}</dl></details>` : ""}
    </article>`;
}

function statTileHtml(num, label) {
  return `<div class="analisis-stat"><span class="analisis-stat__num">${num}</span><span class="analisis-stat__label">${escapeHtml(label)}</span></div>`;
}

function bucketCounts(games, buckets, getValue) {
  const conDato = games.filter((g) => getValue(g) != null);
  return {
    filas: buckets.map((b) => {
      const juegos = conDato.filter((g) => b.match(getValue(g))).map((g) => g.nombre);
      return { label: b.label, valor: juegos.length, juegos };
    }),
    sinDato: games.length - conDato.length,
  };
}

function notaSinDato(n) {
  return n ? `${pluralJuegos(n)} sin este dato en BGG.` : "";
}

// Rango "ideal" (mejor con, según la comunidad de BGG) o "posible" (mínimo y máximo de la caja).
function rangoPosible(g) {
  return g.jug_min != null && g.jug_max != null ? [g.jug_min, g.jug_max] : null;
}

function jugadoresCard(own, { titulo, subtitulo, rango, conInsight }) {
  const filas = [];
  for (let n = 1; n <= ANALISIS_JUGADORES_MAX; n++) {
    const ultimo = n === ANALISIS_JUGADORES_MAX;
    const juegos = own.filter((g) => {
      const r = rango(g);
      return r && (ultimo ? r[1] >= n : n >= r[0] && n <= r[1]);
    }).map((g) => g.nombre);
    filas.push({ label: ultimo ? `${n} o más` : `${n}`, valor: juegos.length, juegos });
  }
  const sinDato = own.filter((g) => !rango(g)).length;
  // El hueco más claro: la cantidad (de 2 a 6) con menos juegos, solo si hay con qué comparar.
  const candidatas = filas.slice(1, 6);
  const minimo = Math.min(...candidatas.map((f) => f.valor));
  const huecos = candidatas.filter((f) => f.valor === minimo).map((f) => f.label);
  const insight = conInsight && own.length >= 5 && Math.max(...candidatas.map((f) => f.valor)) > minimo
    ? `Donde menos juegos ideales tenés: <strong>${huecos.join(", ")}</strong> jugadores (${pluralJuegos(minimo)}).`
    : "";
  return barChartHtml({
    titulo,
    subtitulo,
    filas,
    nota: [insight, notaSinDato(sinDato)].filter(Boolean).join(" "),
  });
}

const JUGADORES_IDEALES = {
  titulo: "👥 Jugadores ideales",
  subtitulo: "Tus juegos que funcionan mejor con esa cantidad de gente (según la comunidad de BGG). Un juego puede tener más de una cantidad ideal, así que cuenta en cada una (por ejemplo, uno ideal para 2 y 3 aparece en las dos).",
  rango: jugBestRange,
  conInsight: true,
};

const JUGADORES_POSIBLES = {
  titulo: "👥 Jugadores posibles",
  subtitulo: "Tus juegos que se pueden jugar con esa cantidad, aunque no sea la ideal",
  rango: rangoPosible,
  conInsight: false,
};

function modoCard(own) {
  const conteo = new Map();
  own.forEach((g) => { if (g.modo) conteo.set(g.modo, (conteo.get(g.modo) || 0) + 1); });
  const filas = [...conteo].map(([label, valor]) => ({ label: modoLabel(label), valor, juegos: own.filter((g) => g.modo === label).map((g) => g.nombre) })).sort((a, b) => b.valor - a.valor);
  if (!filas.length) return "";
  return barChartHtml({ titulo: "🎲 Tipo de juego", filas, nota: notaSinDato(own.filter((g) => !g.modo).length) });
}

// Las mecánicas populares que salen en el filtro (las de la guía que están en el vocabulario de BGG): se
// muestran todas, también las que no tenés (en cero), para ver qué tipo de juego te falta.
const MECANICAS_POPULARES = [
  "Deck Building", "Tile Placement", "Worker Placement", "Set Collection", "Drafting", "Area Control",
  "Route Building", "Dice Rolling", "Push Your Luck", "Bluffing", "Pattern Building", "Deduction",
  "Campaign", "Simultaneous Actions", "Trick-taking",
];

// Cómo las llama BGG a las que el sitio nombra distinto (mismo mapeo que MECANICAS_CLAVE en build_catalog.py):
// las fichas traen el nombre de BGG, así que sin esto "Area Control" daría siempre cero.
const MECANICA_NOMBRE_BGG = {
  "Deck Building": "Deck, Bag, and Pool Building", "Area Control": "Area Majority / Influence",
  "Route Building": "Network and Route Building", "Drafting": "Open Drafting", "Bluffing": "Betting and Bluffing",
  "Campaign": "Scenario / Mission / Campaign Game", "Simultaneous Actions": "Simultaneous Action Selection",
};
const tieneMecanica = (g, label) => g.mecanicas.includes(label) || g.mecanicas.includes(MECANICA_NOMBRE_BGG[label]);

function mecanicasCard(own) {
  if (own.some((g) => !g._hydrated)) {
    return `<article class="analisis-card"><h3 class="analisis-card__title">🧩 Mecánicas populares</h3><p class="analisis-card__sub">Cargando…</p></article>`;
  }
  const conMecanicas = own.filter((g) => g.mecanicas && g.mecanicas.length);
  const conteo = new Map(MECANICAS_POPULARES.map((m) => [m, 0]));
  conMecanicas.forEach((g) => conteo.forEach((n, m) => { if (tieneMecanica(g, m)) conteo.set(m, n + 1); }));
  const filas = [...conteo].map(([label, valor]) => ({ label, valor, hint: MECANICAS_HINT[label], juegos: conMecanicas.filter((g) => tieneMecanica(g, label)).map((g) => g.nombre) }))
    .sort((a, b) => b.valor - a.valor || a.label.localeCompare(b.label, "es"));
  if (!conMecanicas.length) return "";
  const faltan = filas.filter((f) => !f.valor).length;
  return barChartHtml({
    titulo: "🧩 Mecánicas populares",
    subtitulo: `Sobre ${pluralJuegos(conMecanicas.length)} con mecánicas cargadas en BGG${faltan ? ` · las que están en cero son las que no tenés` : ""}`,
    filas,
    ayuda: filas.filter((f) => f.hint).map((f) => [f.label, f.hint]),
  });
}

// Tu puntaje contra el promedio de BGG, solo para lo que tenés o tuviste y puntuaste.
function puntajeCard(games) {
  const puntuados = games.filter((g) => (g.estado === "Own" || g.estado === "Prev. owned") && g.mi_puntaje != null && g.puntaje_bgg != null)
    .map((g) => ({ g, diff: g.mi_puntaje - g.puntaje_bgg }));
  if (puntuados.length < 3) return "";
  const promedio = puntuados.reduce((acc, p) => acc + p.diff, 0) / puntuados.length;
  const lista = (items) => items.map((p) =>
    `<li><span>${escapeHtml(p.g.nombre)}</span><span class="puntaje-vals">vos ${p.g.mi_puntaje} · BGG ${p.g.puntaje_bgg.toFixed(1)}</span></li>`).join("");
  const arriba = [...puntuados].filter((p) => p.diff > 0).sort((a, b) => b.diff - a.diff).slice(0, 3);
  const abajo = [...puntuados].filter((p) => p.diff < 0).sort((a, b) => a.diff - b.diff).slice(0, 3);
  const resumen = Math.abs(promedio) < 0.25
    ? "Puntuás parecido a BGG."
    : `Puntuás en promedio <strong>${Math.abs(promedio).toFixed(1)} puntos ${promedio > 0 ? "más alto" : "más bajo"}</strong> que BGG.`;
  return `
    <article class="analisis-card">
      <h3 class="analisis-card__title">⭐ Tu puntaje contra BGG</h3>
      <p class="analisis-card__sub">${resumen} (${pluralJuegos(puntuados.length)} puntuados)</p>
      ${arriba.length ? `<h4 class="analisis-card__list-title">Los que ponés más alto</h4><ul class="puntaje-list">${lista(arriba)}</ul>` : ""}
      ${abajo.length ? `<h4 class="analisis-card__list-title">Los que ponés más bajo</h4><ul class="puntaje-list">${lista(abajo)}</ul>` : ""}
    </article>`;
}

function renderAnalisis(container, games) {
  const own = games.filter((g) => g.estado === "Own");
  const want = games.filter((g) => g.estado === "Want to buy");
  container.hidden = own.length + want.length === 0;
  const link = document.getElementById("analisis-link");
  if (link) link.hidden = container.hidden;
  if (container.hidden) return;

  const puntuados = games.filter((g) => (g.estado === "Own" || g.estado === "Prev. owned") && g.mi_puntaje != null).length;
  const ranks = own.filter((g) => g.ranking_bgg != null).map((g) => g.ranking_bgg);
  const complejidad = bucketCounts(own, ANALISIS_COMPLEJIDAD, (g) => g.complejidad);
  const duracion = bucketCounts(own, ANALISIS_DURACION, (g) => g.duracion);

  container.innerHTML = `
    <h2 class="analisis__title">📊 Análisis de tu ludoteca</h2>
    <p class="analisis__lead">Calculado en este navegador con los juegos que marcaste como "Lo tengo".</p>
    <div class="analisis-stats">
      ${statTileHtml(own.length, "juegos en casa")}
      ${statTileHtml(want.length, "en la lista para comprar")}
      ${statTileHtml(puntuados, "con tu puntaje")}
      ${statTileHtml(ranks.length ? `#${Math.min(...ranks).toLocaleString("es-AR")}` : "–", "mejor ranking BGG")}
    </div>
    <div class="analisis-grid">
      ${own.length ? jugadoresCard(own, JUGADORES_POSIBLES) : ""}
      ${own.length ? jugadoresCard(own, JUGADORES_IDEALES) : ""}
      ${own.length ? barChartHtml({ titulo: "⚙️ Complejidad", subtitulo: "Peso del juego según BGG, de 1 a 5", filas: complejidad.filas, nota: notaSinDato(complejidad.sinDato) }) : ""}
      ${own.length ? barChartHtml({ titulo: "⏱ Duración", filas: duracion.filas, nota: notaSinDato(duracion.sinDato) }) : ""}
      ${own.length ? modoCard(own) : ""}
      ${own.length ? mecanicasCard(own) : ""}
      ${puntajeCard(games)}
    </div>`;

  // Las mecánicas salen de la ficha: se piden una vez y se vuelve a dibujar.
  hydrate(own).then((n) => { if (n) renderAnalisis(container, games); });
}
