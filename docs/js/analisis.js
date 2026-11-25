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
function barChartHtml({ titulo, subtitulo, filas, nota, ayuda, leyenda, visibles, escala }) {
  const max = escala || Math.max(1, ...filas.map((f) => f.valor));
  let grupoActual = null;
  const rowHtml = (filas) => (grupoActual = null, filas)
    .map((f) => {
      const cab = f.grupo && f.grupo !== grupoActual ? (grupoActual = f.grupo, `<li class="bar-group">${escapeHtml(f.grupo)}</li>`) : "";
      const title = escapeHtml(f.hint ? `${f.label}: ${f.hint}` : `${f.label}: ${pluralJuegos(f.valor)}`);
      const cero = f.valor ? "" : " bar-row--cero";
      const fila = `
        <span class="bar-label">${escapeHtml(f.label)}</span>
        <span class="bar-track${f.ideal != null ? " bar-track--doble" : ""}"><span class="bar-fill" style="width:${(f.valor / max) * 100}%"></span>${f.ideal != null ? `<span class="bar-fill bar-fill--ideal" style="width:${(f.ideal / max) * 100}%"></span>` : ""}</span>
        <span class="bar-value">${f.valorTxt != null ? f.valorTxt : f.ideal != null ? `<strong>${f.ideal}</strong> / ${f.valor}` : f.valor}</span>`;
      // Con juegos, la fila se despliega para ver cuáles son; sin juegos queda fija.
      if (f.juegos && f.juegos.length) {
        const ordenar = (arr) => [...arr].sort((a, b) => a.localeCompare(b, "es"));
        const ideales = new Set(f.idealJuegos || []);
        const lista = [...ordenar(f.juegos.filter((n) => ideales.has(n))).map((n) => `<li class="bar-game--ideal">${escapeHtml(n)}</li>`),
          ...ordenar(f.juegos.filter((n) => !ideales.has(n))).map((n) => `<li>${escapeHtml(n)}</li>`)].join("");
        return `${cab}<li class="bar-item"><details class="bar-details"><summary class="bar-row${cero}" title="${title}">${fila}</summary><ul class="bar-games">${lista}</ul></details></li>`;
      }
      return `${cab}<li class="bar-item"><div class="bar-row${cero}" title="${title}">${fila}</div></li>`;
    })
    .join("");
  const rows = rowHtml(filas.slice(0, visibles || filas.length));
  const resto = visibles && filas.length > visibles ? filas.slice(visibles) : [];
  return `
    <article class="analisis-card">
      <h3 class="analisis-card__title">${escapeHtml(titulo)}</h3>
      ${subtitulo ? `<p class="analisis-card__sub">${escapeHtml(subtitulo)}</p>` : ""}
      ${leyenda ? `<p class="bar-legend"><span class="bar-legend__item"><i class="bar-legend__dot"></i>Se puede jugar</span><span class="bar-legend__item"><i class="bar-legend__dot bar-legend__dot--ideal"></i>Ideal</span></p>` : ""}
      <ul class="bar-list">${rows}</ul>
      ${resto.length ? `<details class="bar-more"><summary>Ver ${resto.length} más</summary><ul class="bar-list">${rowHtml(resto)}</ul></details>` : ""}
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

// Rango "posible": mínimo y máximo de la caja. El "ideal" (mejor con, según BGG) es jugBestRange.
function rangoPosible(g) {
  return g.jug_min != null && g.jug_max != null ? [g.jug_min, g.jug_max] : null;
}

// Para cada cantidad de jugadores (1 a ANALISIS_JUGADORES_MAX o más): los juegos que la comunidad de BGG recomienda
// para esa cantidad (rango jug_min–jug_max, no solo la ideal) y el
// promedio de puntaje BGG de esos juegos (null si no hay ninguno con puntaje).
function calidadPorJugadores(own) {
  return Array.from({ length: ANALISIS_JUGADORES_MAX }, (_, i) => {
    const n = i + 1;
    const ultimo = n === ANALISIS_JUGADORES_MAX;
    const juegos = own.filter((g) => g.jug_min != null && g.jug_max != null && (ultimo ? g.jug_max >= n : n >= g.jug_min && n <= g.jug_max));
    const conPuntaje = juegos.filter((g) => g.puntaje_bgg != null);
    const promedio = conPuntaje.length ? conPuntaje.reduce((a, g) => a + g.puntaje_bgg, 0) / conPuntaje.length : null;
    return { n, label: ultimo ? `${n} o más` : `${n}`, juegos, promedio };
  });
}

function calidadJugadoresCard(own) {
  const datos = calidadPorJugadores(own);
  if (!datos.some((d) => d.promedio != null)) return "";
  const filas = datos.map((d) => ({
    label: d.label, valor: d.promedio != null ? d.promedio : 0,
    valorTxt: d.promedio != null ? `${d.promedio.toFixed(1)} <small>(${d.juegos.length})</small>` : "–",
    juegos: d.juegos.map((g) => g.nombre),
  }));
  const conDato = datos.filter((d) => d.promedio != null);
  const mejor = conDato.reduce((a, b) => (b.promedio > a.promedio ? b : a));
  const peor = conDato.reduce((a, b) => (b.promedio < a.promedio ? b : a));
  const sin = datos.filter((d) => !d.juegos.length).map((d) => d.label);
  const notas = [
    conDato.length >= 2 && mejor.promedio - peor.promedio >= 0.3
      ? `Tus mejores juegos son para <strong>${mejor.label}</strong> (${mejor.promedio.toFixed(1)}) y los más flojos para <strong>${peor.label}</strong> (${peor.promedio.toFixed(1)}).` : "",
    sin.length ? `Sin ningún juego recomendado para: ${sin.join(", ")}.` : "",
  ];
  return barChartHtml({
    titulo: "⭐ Calidad según cantidad de jugadores",
    subtitulo: "Puntaje promedio en BGG de tus juegos que la comunidad recomienda para esa cantidad de gente (entre paréntesis, cuántos son). Un juego cuenta en cada cantidad en la que se recomienda, no solo en la ideal.",
    filas, escala: 10, nota: notas.filter(Boolean).join(" "),
  });
}

function jugadoresCard(own) {
  const filas = [];
  const enRango = (r, n, ultimo) => r && (ultimo ? r[1] >= n : n >= r[0] && n <= r[1]);
  for (let n = 1; n <= ANALISIS_JUGADORES_MAX; n++) {
    const ultimo = n === ANALISIS_JUGADORES_MAX;
    const posibles = own.filter((g) => enRango(rangoPosible(g), n, ultimo));
    const ideales = posibles.filter((g) => enRango(jugBestRange(g), n, ultimo));
    filas.push({
      label: ultimo ? `${n} o más` : `${n}`,
      valor: posibles.length,
      ideal: ideales.length,
      juegos: posibles.map((g) => g.nombre),
      idealJuegos: ideales.map((g) => g.nombre),
    });
  }
  const sinPosible = own.filter((g) => !rangoPosible(g)).length;
  const sinIdeal = own.filter((g) => !jugBestRange(g)).length;
  // El hueco más claro: la cantidad (de 2 a 6) con menos juegos ideales, solo si hay con qué comparar.
  const candidatas = filas.slice(1, 6);
  const minimo = Math.min(...candidatas.map((f) => f.ideal));
  const huecos = candidatas.filter((f) => f.ideal === minimo).map((f) => f.label);
  const insight = own.length >= 5 && Math.max(...candidatas.map((f) => f.ideal)) > minimo
    ? `Donde menos juegos ideales tenés: <strong>${huecos.join(", ")}</strong> jugadores (${pluralJuegos(minimo)}).`
    : "";
  const notas = [
    insight,
    sinPosible ? `${pluralJuegos(sinPosible)} sin cantidad de jugadores en BGG.` : "",
    sinIdeal ? `${pluralJuegos(sinIdeal)} sin cantidad ideal en BGG.` : "",
  ];
  return barChartHtml({
    titulo: "👥 Jugadores posibles e ideales",
    subtitulo: "Cuántos de tus juegos se pueden jugar con esa cantidad de gente y, de esos, cuántos son ideales según la comunidad de BGG. Un juego puede tener más de una cantidad ideal, así que cuenta en cada una.",
    leyenda: true,
    filas,
    nota: notas.filter(Boolean).join(" "),
  });
}

function modoCard(own) {
  const conteo = new Map();
  own.forEach((g) => { if (g.modo) conteo.set(g.modo, (conteo.get(g.modo) || 0) + 1); });
  const filas = [...conteo].map(([label, valor]) => ({ label: modoLabel(label), valor, juegos: own.filter((g) => g.modo === label).map((g) => g.nombre) })).sort((a, b) => b.valor - a.valor);
  if (!filas.length) return "";
  return barChartHtml({ titulo: "🎲 Tipo de juego", filas, nota: notaSinDato(own.filter((g) => !g.modo).length) });
}

// Mecánicas curadas: la columna `mecs` del índice (MECANICAS_CLAVE en build_catalog.py) deja afuera las que ya
// dice la card (cooperativo, equipos) y las técnicas. Se muestran todas, también las que no tenés (en cero),
// para ver qué tipo de juego te falta.
function mecanicasCard(own) {
  const conMecanicas = own.filter((g) => g.mecs && g.mecs.length);
  if (!conMecanicas.length) return "";
  const orden = MECANICAS_GRUPOS_ORDEN;
  const filas = MECANICAS_VOCAB.map((label, i) => {
    const juegos = conMecanicas.filter((g) => g.mecs.includes(i)).map((g) => g.nombre);
    return { label, grupo: MECANICAS_GRUPOS[i], valor: juegos.length, hint: MECANICAS_HINT[label], juegos };
  }).sort((a, b) => orden.indexOf(a.grupo) - orden.indexOf(b.grupo) || b.valor - a.valor || a.label.localeCompare(b.label, "es"));
  // La card se achica: arriba las primeras filas (por grupo, en cada uno las que tenés primero); el resto, también por grupo, en "Ver N más".
  const faltan = filas.filter((f) => !f.valor).length;
  const VISIBLES = 12;
  return barChartHtml({
    visibles: VISIBLES,
    titulo: "🧩 Mecánicas",
    subtitulo: `Sobre ${pluralJuegos(conMecanicas.length)} con mecánicas cargadas en BGG${faltan ? " · las que están en cero son las que no tenés" : ""} · "Ver más" despliega el resto de los grupos`,
    filas,
    ayuda: filas.filter((f) => f.hint).map((f) => [f.label, f.hint]),
  });
}

// Qué te gusta más: promedio de tu puntaje por mecánica, con lo que tenés o tuviste y puntuaste.
function gustosCard(games) {
  const puntuados = games.filter((g) => (g.estado === "Own" || g.estado === "Prev. owned") && g.mi_puntaje != null && g.mecs && g.mecs.length);
  if (puntuados.length < 6) return "";
  const media = puntuados.reduce((a, g) => a + g.mi_puntaje, 0) / puntuados.length;
  const filas = MECANICAS_VOCAB.map((label, i) => {
    const juegos = puntuados.filter((g) => g.mecs.includes(i));
    const prom = juegos.length ? juegos.reduce((a, g) => a + g.mi_puntaje, 0) / juegos.length : null;
    return { label, prom, juegos };
  }).filter((f) => f.juegos.length >= 2)
    .sort((a, b) => b.prom - a.prom || b.juegos.length - a.juegos.length)
    .map((f) => ({ label: f.label, valor: f.prom, valorTxt: `${f.prom.toFixed(1)} <small>(${f.juegos.length})</small>`, hint: `${f.label}: ${f.prom.toFixed(1)} de promedio en ${pluralJuegos(f.juegos.length)}`, juegos: f.juegos.map((g) => g.nombre) }));
  if (filas.length < 3) return "";
  const visibles = Math.min(6, filas.length);
  return barChartHtml({
    titulo: "❤️ Qué mecánicas te gustan más",
    subtitulo: `Tu puntaje promedio en los juegos que tenés o tuviste con cada mecánica (entre paréntesis, cuántos; mínimo 2). Tu promedio general es ${media.toFixed(1)}.`,
    filas, visibles, escala: 10,
    nota: `Las que más puntuás: <strong>${filas.slice(0, 3).map((f) => escapeHtml(f.label)).join(", ")}</strong>.`,
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
      ${own.length ? jugadoresCard(own) : ""}
      ${own.length ? calidadJugadoresCard(own) : ""}
      ${own.length ? barChartHtml({ titulo: "⚙️ Complejidad", subtitulo: "Peso del juego según BGG, de 1 a 5", filas: complejidad.filas, nota: notaSinDato(complejidad.sinDato) }) : ""}
      ${own.length ? barChartHtml({ titulo: "⏱ Duración", filas: duracion.filas, nota: notaSinDato(duracion.sinDato) }) : ""}
      ${own.length ? modoCard(own) : ""}
      ${own.length ? mecanicasCard(own) : ""}
      ${gustosCard(games)}
      ${puntajeCard(games)}
    </div>`;

  // Las mecánicas salen de la ficha: se piden una vez y se vuelve a dibujar.
  hydrate(games.filter((g) => g.estado === "Own" || g.estado === "Prev. owned")).then((n) => { if (n) renderAnalisis(container, games); });
}
