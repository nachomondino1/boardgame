// Análisis de la ludoteca: números y gráficos de barras sobre los juegos Own, calculados
// en el navegador. Vive en Mi ludoteca, al pie, pero no depende de esa página: recibe el
// contenedor y la lista de juegos (con estado y mi_puntaje ya aplicados), así que se puede
// mover a otra página sin tocar nada de acá.
// Necesita shared.js (escapeHtml, jugBestRange, hydrate).

const ANALISIS_JUGADORES_MAX = 7; // la última barra agrupa "7 o más"

const ANALISIS_COMPLEJIDAD = [
  { label: "Liviano (menos de 2)", match: (c) => c < 2 },
  { label: "Medio (2 a 3)", match: (c) => c >= 2 && c < 3 },
  { label: "Pesado (3 o más)", match: (c) => c >= 3 },
];

const ANALISIS_DURACION = [
  { label: "Hasta 30 min", match: (d) => d <= 30 },
  { label: "31 a 60 min", match: (d) => d > 30 && d <= 60 },
  { label: "61 a 120 min", match: (d) => d > 60 && d <= 120 },
  { label: "Más de 2 horas", match: (d) => d > 120 },
];

function pluralJuegos(n) {
  return `${n} juego${n === 1 ? "" : "s"}`;
}

// Una barra por fila: etiqueta, barra proporcional al máximo y el valor al final.
// Una sola serie, así que no lleva leyenda: el título dice qué se está contando.
function barChartHtml({ titulo, subtitulo, filas, nota }) {
  const max = Math.max(1, ...filas.map((f) => f.valor));
  const rows = filas
    .map((f) => `
      <li class="bar-row" title="${escapeHtml(f.label)}: ${escapeHtml(pluralJuegos(f.valor))}">
        <span class="bar-label">${escapeHtml(f.label)}</span>
        <span class="bar-track"><span class="bar-fill" style="width:${(f.valor / max) * 100}%"></span></span>
        <span class="bar-value">${f.valor}</span>
      </li>`)
    .join("");
  return `
    <article class="analisis-card">
      <h3 class="analisis-card__title">${escapeHtml(titulo)}</h3>
      ${subtitulo ? `<p class="analisis-card__sub">${escapeHtml(subtitulo)}</p>` : ""}
      <ul class="bar-list">${rows}</ul>
      ${nota ? `<p class="analisis-card__note">${nota}</p>` : ""}
    </article>`;
}

function statTileHtml(num, label) {
  return `<div class="analisis-stat"><span class="analisis-stat__num">${num}</span><span class="analisis-stat__label">${escapeHtml(label)}</span></div>`;
}

function bucketCounts(games, buckets, getValue) {
  const conDato = games.filter((g) => getValue(g) != null);
  return {
    filas: buckets.map((b) => ({ label: b.label, valor: conDato.filter((g) => b.match(getValue(g))).length })),
    sinDato: games.length - conDato.length,
  };
}

function notaSinDato(n) {
  return n ? `${pluralJuegos(n)} sin este dato en BGG.` : "";
}

function jugadoresCard(own) {
  const filas = [];
  for (let n = 1; n <= ANALISIS_JUGADORES_MAX; n++) {
    const ultimo = n === ANALISIS_JUGADORES_MAX;
    filas.push({
      label: ultimo ? `${n} o más` : `${n}`,
      valor: own.filter((g) => {
        const r = jugBestRange(g);
        return r && (ultimo ? r[1] >= n : n >= r[0] && n <= r[1]);
      }).length,
    });
  }
  const sinDato = own.filter((g) => !jugBestRange(g)).length;
  // El hueco más claro: la cantidad (de 2 a 6) con menos juegos, solo si hay con qué comparar.
  const candidatas = filas.slice(1, 6);
  const minimo = Math.min(...candidatas.map((f) => f.valor));
  const huecos = candidatas.filter((f) => f.valor === minimo).map((f) => f.label);
  const insight = own.length >= 5 && Math.max(...candidatas.map((f) => f.valor)) > minimo
    ? `Donde menos juegos tenés: <strong>${huecos.join(", ")}</strong> jugadores (${pluralJuegos(minimo)}).`
    : "";
  return barChartHtml({
    titulo: "¿Para cuántos jugadores?",
    subtitulo: "Juegos que funcionan mejor con esa cantidad de gente",
    filas,
    nota: [insight, notaSinDato(sinDato)].filter(Boolean).join(" "),
  });
}

function modoCard(own) {
  const conteo = new Map();
  own.forEach((g) => { if (g.modo) conteo.set(g.modo, (conteo.get(g.modo) || 0) + 1); });
  const filas = [...conteo].map(([label, valor]) => ({ label, valor })).sort((a, b) => b.valor - a.valor);
  if (!filas.length) return "";
  return barChartHtml({ titulo: "Tipo de juego", filas, nota: notaSinDato(own.filter((g) => !g.modo).length) });
}

function mecanicasCard(own) {
  if (own.some((g) => !g._hydrated)) {
    return `<article class="analisis-card"><h3 class="analisis-card__title">Mecánicas más frecuentes</h3><p class="analisis-card__sub">Cargando…</p></article>`;
  }
  const conMecanicas = own.filter((g) => g.mecanicas && g.mecanicas.length);
  const conteo = new Map();
  conMecanicas.forEach((g) => g.mecanicas.forEach((m) => conteo.set(m, (conteo.get(m) || 0) + 1)));
  const filas = [...conteo].map(([label, valor]) => ({ label, valor }))
    .sort((a, b) => b.valor - a.valor || a.label.localeCompare(b.label, "es")).slice(0, 6);
  if (!filas.length) return "";
  return barChartHtml({
    titulo: "Mecánicas más frecuentes",
    subtitulo: `Sobre ${pluralJuegos(conMecanicas.length)} con mecánicas cargadas en BGG`,
    filas,
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
      <h3 class="analisis-card__title">Tu puntaje contra BGG</h3>
      <p class="analisis-card__sub">${resumen} (${pluralJuegos(puntuados.length)} puntuados)</p>
      ${arriba.length ? `<h4 class="analisis-card__list-title">Los que ponés más alto</h4><ul class="puntaje-list">${lista(arriba)}</ul>` : ""}
      ${abajo.length ? `<h4 class="analisis-card__list-title">Los que ponés más bajo</h4><ul class="puntaje-list">${lista(abajo)}</ul>` : ""}
    </article>`;
}

function renderAnalisis(container, games) {
  const own = games.filter((g) => g.estado === "Own");
  const want = games.filter((g) => g.estado === "Want to buy");
  const prev = games.filter((g) => g.estado === "Prev. owned");
  container.hidden = own.length + want.length === 0;
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
      ${statTileHtml(prev.length, "que tuviste")}
      ${statTileHtml(puntuados, "con tu puntaje")}
      ${statTileHtml(ranks.length ? `#${Math.min(...ranks).toLocaleString("es-AR")}` : "–", "mejor ranking BGG")}
    </div>
    <div class="analisis-grid">
      ${own.length ? jugadoresCard(own) : ""}
      ${own.length ? barChartHtml({ titulo: "Complejidad", subtitulo: "Peso del juego según BGG, de 1 a 5", filas: complejidad.filas, nota: notaSinDato(complejidad.sinDato) }) : ""}
      ${own.length ? barChartHtml({ titulo: "Duración", filas: duracion.filas, nota: notaSinDato(duracion.sinDato) }) : ""}
      ${own.length ? modoCard(own) : ""}
      ${own.length ? mecanicasCard(own) : ""}
      ${puntajeCard(games)}
    </div>`;

  // Las mecánicas salen de la ficha: se piden una vez y se vuelve a dibujar.
  hydrate(own).then((n) => { if (n) renderAnalisis(container, games); });
}
