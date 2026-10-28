# Juegos de mesa

Prototipo de página estática para buscar y filtrar la colección de juegos de mesa (sin build system: HTML + CSS + JS vanilla).

## Correr local

```bash
cd docs && python3 -m http.server 8765
```

Y abrir `http://localhost:8765`.

Vivo en: https://nachomondino1.github.io/boardgame/

## Páginas

- `index.html` — **Mi ludoteca**: los juegos con Estado Own o Prev. owned (lo que tenés o tuviste), buscador, filtros y orden. Watchlist no se navega acá, solo en ¿Cuál comprar?.
- `hoy.html` — **¿Qué jugamos hoy?**: elegís cuántos son y te muestra qué podés jugar de lo que ya tenés (Estado = Own), ordenado por una heurística de qué tan bueno es cada juego para hoy. El toggle "incluir Watchlist" extiende la búsqueda a lo que no tenés todavía, y el toggle "buscar por cantidad ideal (best)" cambia el filtro de jugadores de Jug. mín/máx a Jug Best min/máx.
- `comprar.html` — **¿Cuál comprar?**: solo Watchlist, con sliders de duración máxima y complejidad máxima, el mismo filtro de jugadores, y (cuando están cargados/relevados) link a la tienda, costo y relación precio/calidad en cada tarjeta, con opción de ordenar por estos dos últimos. Incluye una sección colapsable "Comparar dos juegos" (tabla lado a lado con todos los campos relevantes, resaltando quién gana cada fila) — antes era una página aparte (`comparar.html`), se fusionó acá porque se usa siempre junto con esta página.

## Archivos

- `docs/` — el sitio tal cual lo sirve GitHub Pages (**Deploy from branch** `main`, carpeta `/docs`):
  - `docs/index.html` / `docs/hoy.html` / `docs/comprar.html` — las 3 páginas.
  - `docs/css/pages/comparar.css` — estilos de la sección "Comparar dos juegos" dentro de `comprar.html` (ver arriba).
  - `docs/js/shared.js` — helpers comunes a las 3 páginas (carga de datos, armado de las tarjetas, nav, etc.).
  - `docs/css/style.css` / `docs/js/app.js` / `docs/js/hoy.js` / `docs/js/comprar.js` — estilos y lógica de cada página.
  - `docs/data/data.json` — el universo de juegos, con las columnas derivadas ya calculadas. Se regenera solo, ver abajo.
- `data/01_data_understanding/universo_juegos.jsonl` — **catálogo de identidad**: `bgg_id`, `nombre`, `bgg_url`, `link_cazagangas` — qué juegos conoce este repo, sin tu opinión sobre ellos. Se commitea. `search_new_game.py --add` lo completa solo, `link_cazagangas` incluido cuando el slug resuelto verifica 200 (si no, queda vacío para cargarlo a mano).
- `data/01_data_understanding/ludoteca.jsonl` — **tu opinión**, pero solo para los juegos que curaste (`Own`/`Prev. owned`/`Want to buy`/`Descartado`, o un `Watchlist` con algo cargado): `bgg_id`, `nombre`, `estado`, `transportable`, `mi_puntaje`, `pros`, `cons`, `notas`. Un juego del catálogo sin fila acá no es un error — `estado` cae en "Watchlist" por default (ver `integrate_data.py`). Se commitea: solo `search_new_game.py --add --estado <...>` le agrega filas nuevas, nunca pisa una existente. Ver el README de `01_data_understanding/` para el detalle completo.
- `data/01_data_understanding/bgg_data.jsonl` — caché de datos de BGG (rating, duración, etc.) para cada `bgg_id` de `universo_juegos.jsonl`, `bgg_id` primer campo de cada línea. Se commitea igual (para no depender de la red en cada build). Una fila que falta es regenerable (`search_new_game.py` la completa); una fila que ya existe nunca se reescribe sola, así que una corrección manual (`modify_values.py`) no se pierde — a diferencia de antes, cuando un refresh reescribía el archivo entero.
- `data/01_data_understanding/grupos.json` — curado a mano, juegos que son el mismo sistema de juego con otra caja (ver "¿Cuál comprar?" abajo y `DATA_PLAYBOOK.md`).
- `data/01_data_understanding/cazagangas_data.jsonl` — código HTTP real (verificado) del `link_cazagangas` de cada juego de `universo_juegos.jsonl`, generado por `check_cazagangas_links.py` (ver abajo).
- `01_data_understanding/collect_initial_data/bgg/` — librería y scripts específicos de BGG: `bgg_common.py`, `initialize_bgg_data.py` (bootstrap único, no se vuelve a correr), `modify_values.py` (editar campos puntuales a mano) y `extract_new_fields.py` (sumar una columna nueva a todas las filas).
- `01_data_understanding/collect_initial_data/cazagangas/` — `cazagangas_common.py` (slug best-effort + verificación HTTP) y `check_cazagangas_links.py` (re-verifica masivamente los links ya cargados, manual).
- `01_data_understanding/collect_initial_data/search_new_game.py` — vive afuera de `bgg/`/`cazagangas/` porque orquesta las dos: con `--add <id o nombre>` suma un juego nuevo a `universo_juegos.jsonl` + `bgg_data.jsonl` + `cazagangas_data.jsonl`/`link_cazagangas` (si el slug verifica 200) de una; con `--estado <...>` además, agrega una fila a `ludoteca.jsonl` (si no se pasa, el juego queda como Watchlist implícito, sin fila). Sin `--add` (uso normal, lo que corre el cron), completa `bgg_data.jsonl` con lo que falte. Ver el README de `01_data_understanding/`.
- `01_data_understanding/collect_initial_data/cazagangas/check_cazagangas_links.py` — verifica con un HEAD real el `link_cazagangas` ya cargado en `universo_juegos.jsonl` (no arma ninguna URL) y guarda el código HTTP (`200`/`404`/`error`) en `data/01_data_understanding/cazagangas_data.jsonl`. Corre a mano (`--limit N` para ir de a tandas), no está en el cron — ver `DATA_PLAYBOOK.md`.
- `02_data_preparation/integrate_data.py` — junta `universo_juegos.jsonl` (base) + `ludoteca.jsonl`/`bgg_data.jsonl` (por `bgg_id`) + `grupos.json`/`cazagangas_data.jsonl` (por nombre) en un solo archivo (`data/02_data_preparation/integrated_data.jsonl`, gitignored: es un intermedio del build, se regenera siempre). Solo integra, no calcula nada.
- `02_data_preparation/construct_data.py` — lee `data/02_data_preparation/integrated_data.jsonl`, calcula las columnas derivadas (`duracion`, `modo`, `puntaje_ajust_bgg`, `precio_calidad` — ver "Columnas calculadas" abajo) y escribe `docs/data/data.json`. `transportable`/`bgg_url`/`link_cazagangas`/`grupo`/`cazagangas_status` no se calculan acá, pasan de largo tal cual vienen (`transportable` es 100% manual, ver `01_data_understanding/README.md`; los otros cuatro ya vienen resueltos de `integrate_data.py`).
- `02_data_preparation/select_data.py` — corre después de `construct_data.py`, sobre `docs/data/data.json`: recorta los candidatos con `estado = "Watchlist"` (nunca los curados — `Own`/`Prev. owned`/`Want to buy`/`Descartado` siempre quedan) descartando los que están por debajo del percentil `MIN_REVIEWS_PERCENTILE` de reviews en BGG (calculado sobre el propio Watchlist de cada corrida, no un número fijo) y quedándose con los `TOP_N_WATCHLIST` mejor puntuados del resto. Pensado para que "¿Cuál comprar?" no tenga que lidiar con miles de tarjetas de baja calidad de dato/interés.
- `.github/workflows/sync-data.yml` — corre `search_new_game.py`, `integrate_data.py` y `construct_data.py` el día 1 de cada mes a las 12:00 UTC y en cada ejecución manual, y si algo cambió lo commitea y pushea a `main`. Eso dispara un redeploy automático de GitHub Pages. Si agregaste un juego y no querés esperar al mes, lo disparás a mano (ver abajo). `check_cazagangas_links.py` no corre acá (ver arriba).
- `01_data_understanding/collect_initial_data/bosque_ludico/` — **[PAUSADO]** precio en la tienda. Los scripts existen (`resolve_bosque_links.py`/`collect_bosque_precios.py`) pero nada los corre activamente, y a diferencia de `cazagangas_data.jsonl` su salida ni siquiera está commiteada (ver `.gitignore`) — integrarla a `integrate_data.py` es trabajo futuro, ver `01_data_understanding/README.md` y `DATA_PLAYBOOK.md`.
- `03_modeling/`, `04_evaluation/`, `05_deployment/` — estructura tipo CRISP-DM que le dimos al repo (ver el README de cada carpeta); `03_modeling/`/`04_evaluation/` son placeholders (no hay predicción, del dato recolectado se pasa directo a construir lo que consume el sitio).

### Links a BGG

Cada juego linkea directo a `https://boardgamegeek.com/boardgame/<bgg_id>` — el `bgg_id` sale del ranking de BGG para los candidatos, o se resuelve por búsqueda (`geeksearch.php?...&q=<nombre>`) en el bootstrap para tus propios juegos sin link exacto cargado (`BGG_SEARCH_OVERRIDES`/`BGG_SKIP` en `initialize_bgg_data.py`, mismo patrón que antes — "Misterio (Ruibal)" → busca "Misterio", etc.). BGG cerró el acceso sin auth a su API XML (401), así que no hay forma automática de resolver el id exacto para esos casos de búsqueda; se arregla a mano agregando `bgg_id`/`bgg_url` directo en la fila de `universo_juegos.jsonl` (y, si corresponde, `bgg_id` en la fila de `ludoteca.jsonl`).

### De dónde salen los datos de BGG

`search_new_game.py`/`initialize_bgg_data.py` completan `descripcion`, `disenador`, `edad_min`, `jug_min/max`, `jug_best_min/max`, `duracion_min/max`, `complejidad`, `puntaje_bgg`, `reviews_bgg`, `ranking_bgg`, `mecanicas`, `categorias`, `imagen` (URL del thumbnail, CDN de BGG) para los juegos que tienen un link exacto a BGG. `imagen` se muestra como miniatura en cada tarjeta (`docs/js/shared.js`, `cardTemplate`); si falta (juego sin match en el dataset), la tarjeta se ve igual sin ella.

**Hoy corre en `--mode dummy` (default), un placeholder temporal:** la vía oficial (`--mode api`, `xmlapi2/thing`) sigue bloqueada (401 sin auth hasta que BGG apruebe la aplicación registrada), y scrapear la página normal está descartado (Cloudflare la protege con un challenge que no se evade ni con cookies de una sesión ya autenticada — se probó explícito, ver `DATA_PLAYBOOK.md`). En cambio, `--mode dummy` usa un dataset público de terceros con un **snapshot de BGG de 2025** (`games_detailed_info2025.csv` de `mmpa/board_game_analysis` en Hugging Face, ~28.000 juegos, sin auth) — cubre ~98% del universo. No trae precio (BGG no lo trackea; Amazon tampoco se consultó — ver "Pendiente" abajo). Un juego que no esté en ese snapshot no tiene match — sin error, sin dato inventado, esos campos quedan en `null` hasta que BGG apruebe la app.

Cuando eso pase, correr `python3 01_data_understanding/collect_initial_data/search_new_game.py --mode api` y reemplazar el paso del cron (`sync-data.yml`) para que use `--mode api` en vez de dejar el default.

### Columnas calculadas

Ninguna de estas cinco viene directo de una fuente: `02_data_preparation/construct_data.py` las deriva de otras columnas ya integradas.

- `puntaje_ajust_bgg = puntaje_bgg - 3 × 1.4 / √reviews_bgg` — penaliza puntajes altos con pocas reviews. La fórmula viene del Sheet original antes de simplificarlo (se leyó la celda real antes de borrar la columna, no se reinventó — ver el docstring de `construct_data.py`, incluida una inconsistencia que había entre filas y cuál de las dos variantes quedó como oficial).
- `precio_calidad = promedio( -zscore(costo), zscore(puntaje_ajust_bgg) )` — más barato y mejor puntaje ajustado, mejor relación. Hoy da `null` para todos: `costo` depende de la integración con Bosque Lúdico, que todavía no existe (ver "Pendiente").
- `duracion` — promedio de `duracion_min`/`duracion_max` (ambos de BGG); si falta uno de los dos, el que haya.
- `modo` (`Competitivo`/`Cooperativo`/`Equipos`/`Cooperativo y competitivo`) — derivado 100% de las mecánicas/categorías de BGG (`Cooperative Game`, `Team-Based Game`, `Semi-Cooperative Game`, `infer_modo` en `bgg_common.py`); sin mecánicas/categorías, queda en `null` en vez de asumir "Competitivo" a ciegas. No vive en ninguna fuente curada a mano.

### Sincronizar a mano

Si no querés esperar al cron, desde GitHub: Actions → "Sync data.json" → Run workflow. O localmente:
```bash
python3 01_data_understanding/collect_initial_data/search_new_game.py
python3 02_data_preparation/integrate_data.py
python3 02_data_preparation/construct_data.py
python3 02_data_preparation/select_data.py
```

## Qué tiene

- Buscador instantáneo por nombre (Mi ludoteca).
- Filtro "¿cuántos jugadores somos?" (usa Jug. mín/máx, y marca con un tag verde "Best con N" si N coincide con Jug Best mín/máx).
- Filtros por Estado en Mi ludoteca (Own / Prev. owned).
- Orden por Ranking BGG, Puntaje BGG, Mi puntaje, Complejidad o Duración.
- Toggle "Según mi gusto" (duración ≤60 min, complejidad ≤2.5), tomado de la sección "Mi gusto" de la pestaña Resumen.
- Complejidad con color (verde→rojo), como el formato condicional del Sheet.
- Link directo a BGG en el título de cada tarjeta.
- "¿Qué jugamos hoy?": filtra por N jugadores dentro de Jug mín/máx (o solo Jug Best mín/máx con "Solo si es el mejor número"), ordenado por Puntaje BGG por default (antes había un recomendador heurístico propio en `shared.js::recommendationScore`, sacado por confuso — ver git log, 2026-10-28).
- "¿Cuál comprar?": Watchlist (hasta ~1000 candidatos del top N de BGG + lo que no es tuyo) filtrada por tipo (modo), duración, complejidad y jugadores, con link a la tienda y costo cuando están cargados/relevados, y relación precio/calidad calculada (ver "Columnas calculadas"). El ~2% de candidatos sin match en el dataset placeholder de BGG no tiene duración/complejidad/jugadores/modo — las tarjetas lo muestran como "?" en vez de ocultarse. Variantes/expansiones del mismo sistema de juego (ej. las cajas de Unmatched) se colapsan en una sola tarjeta, con el resto desplegable (ver `data/01_data_understanding/grupos.json`). Link a la ficha real en [Cazagangas](https://www.cazagangas.com.ar) cuando `check_cazagangas_links.py` confirmó que existe (código 200) — ver `data/01_data_understanding/cazagangas_data.jsonl`. Resultados paginados (60 a la vez, "Mostrar más") y los sliders/el buscador debounced — renderizar hasta ~1000 tarjetas en cada cambio de filtro se sentía lento, sobre todo en mobile.

## Pendiente si esto vale la pena
- Piso de puntaje mínimo en "¿Cuál comprar?" (hoy existe paginación — "Mostrar más", 60 a la vez — pero no un filtro para sacar directamente los candidatos peor puntuados).
- Integrar `bosque_data.csv` en `integrate_data.py` (mismo patrón que `cazagangas_data.jsonl`), para que `costo`/`link_tienda`/`precio_calidad` dejen de ser `null`. Los scripts de recolección ya existen y funcionan (`01_data_understanding/collect_initial_data/bosque_ludico/`), falta sumarlos al merge.
- Precio de Amazon (u otra tienda más allá de Bosque Lúdico): no se investigó todavía una fuente sin auth/bot-detection para eso; sería un caso igual al de Bosque Lúdico, nunca scrapear Amazon directo sin chequear antes su robots.txt y bot-detection.
- Ampliar `check_cazagangas_links.py` a scraper real de Cazagangas: hoy solo confirma que el link existe (código HTTP). Pendiente sumar precio, stock/disponibilidad y en qué tienda(s) de Argentina se puede comprar cada juego (Cazagangas agrega varias tiendas por juego) — mismo patrón que `costo`/`link_tienda`/`precio_calidad` ya tienen pensado para Bosque Lúdico (ver el bullet de arriba), pero con Cazagangas como fuente en vez de (o además de) Bosque Lúdico.
- Cuando BGG apruebe la app: `search_new_game.py --mode api` reemplaza el placeholder sin tocar nada más del pipeline.
- Premio Spiel des Jahres (Ganador/Shortlist/Recomendado): no está en el dataset placeholder de BGG (se chequeó el header, no trae esa columna) ni en la API oficial. Falta decidir la fuente (¿scraping del sitio oficial de Spiel des Jahres, o carga manual una vez al año ya que la lista es chica y estable?) y cómo cargarla — probablemente como columna propia en `ludoteca.jsonl`, nunca enriquecimiento automático de BGG.
- Describe data / Explore data (CRISP-DM 2 y 3): contar nulos, correlaciones entre variables, etc. — no existen todavía.
