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
- `comprar.html` — **¿Cuál comprar?**: solo Watchlist, con sliders de duración máxima y complejidad máxima, el mismo filtro de jugadores, y (cuando están cargados/relevados) link a la tienda, costo y relación precio/calidad en cada tarjeta, con opción de ordenar por estos dos últimos.

## Archivos

- `docs/` — el sitio tal cual lo sirve GitHub Pages (**Deploy from branch** `main`, carpeta `/docs`):
  - `docs/index.html` / `docs/hoy.html` / `docs/comprar.html` — las 3 páginas.
  - `docs/js/shared.js` — helpers comunes a las 3 páginas (carga de datos, armado de las tarjetas, nav, etc.).
  - `docs/css/style.css` / `docs/js/app.js` / `docs/js/hoy.js` / `docs/js/comprar.js` — estilos y lógica de cada página.
  - `docs/data/data.json` — el universo de juegos integrado: lo que tenés/tuviste (tu ludoteca) + candidatos a comprar (top N de BGG). Se regenera solo, ver abajo.
- `01_data_understanding/ludoteca/mi_ludoteca.json` — lo que tenés o tuviste (Estado Own/Prev. owned), un JSON que editás directo (a mano o pidiéndoselo a Claude) en vez de un Google Sheet — ver el README de `01_data_understanding/` para el porqué del cambio.
- `01_data_understanding/bgg/collect_bgg_rankings.py` — descarga el top 1000 del ranking de BGG desde un dataset público de terceros en GitHub (no la API de BGG, bloqueada) y lo guarda **versionado** en `bgg/bgg_top1000.csv`.
- `01_data_understanding/game_universe.py` — combina tu ludoteca + `bgg_top1000.csv`: cualquier juego del top N que no sea ya tuyo entra como candidato con Estado `"Watchlist"`. `load_universe()` es el punto de entrada que usan tanto `integrate_data.py` como los scripts de Bosque Lúdico. Ver el README de `01_data_understanding/` para el detalle.
- `02_data_preparation/integrate_data.py` — **solo integra**: `game_universe.load_universe()` (fuente de verdad) + el caché de BGG (`docs/data/cache/bgg/`) + el dataset de precios de Bosque Lúdico (`01_data_understanding/bosque_ludico/bosque_data.json`, si corrió), y escribe `docs/data/data.json`. Tu ludoteca siempre tiene prioridad sobre tus propios juegos; BGG y Bosque Lúdico solo completan los campos que quedaron vacíos.
- `02_data_preparation/construct_data.py` — corre después, sobre el mismo `docs/data/data.json`: calcula `puntaje_ajust_bgg` y `precio_calidad`, que no vienen de ninguna fuente sino que se derivan de otras columnas ya integradas (ver "Columnas calculadas" abajo).
- `01_data_understanding/bgg/enrich_bgg.py` — arma `docs/data/cache/bgg/<id>.json` con datos de BGG (descripción, puntaje, reviews, ranking, complejidad, diseñador, edad mín., jugadores, duración mín./máx., mecánicas, categorías) por juego. Corre automático (modo `dummy`, ver abajo); el modo `api` oficial sigue bloqueado.
- `.github/workflows/sync-data.yml` — corre `collect_bgg_rankings.py`, `enrich_bgg.py`, `integrate_data.py` y `construct_data.py` el día 1 de cada mes a las 12:00 UTC y en cada ejecución manual, y si algo cambió lo commitea y pushea a `main`. Eso dispara un redeploy automático de GitHub Pages. Si agregaste un juego y no querés esperar al mes, lo disparás a mano (ver abajo).
- `01_data_understanding/bosque_ludico/resolve_bosque_links.py` y `collect_bosque_precios.py` — resuelven el link a la ficha de cada juego en Watchlist en [El Bosque Lúdico](https://www.elbosqueludico.com.ar) y relevan su precio actual en `bosque_data.json` (ver el README de la carpeta). Paso manual (el cron no lo corre, por el costo en tiempo/requests); `integrate_data.py` lo toma como fallback de `costo`/`link_tienda` si corrió.
- `03_modeling/`, `04_evaluation/`, `05_deployment/` — estructura tipo CRISP-DM que le dimos al repo (ver el README de cada carpeta); `03_modeling/`/`04_evaluation/` son placeholders (no hay predicción, del dato integrado se pasa directo a generar lo que consume el sitio).

### Links a BGG

BGG cerró el acceso sin autenticación a su API XML (devuelve 401), así que no se puede resolver el ID exacto de cada juego en el build automático. Para tus propios juegos (ludoteca), cada uno linkea a una búsqueda de BGG por título, usando `nombre_en` como término (`geeksearch.php?...&q=<nombre>`), que en la práctica cae directo en el juego correcto como primer resultado — salvo que ya tengas el link exacto cargado en `mi_ludoteca.json`. Para ediciones locales o proxys (p. ej. "Misterio (Ruibal)" → busca "Misterio", "Memotest (Ruibal)" → busca "Memory"), el término de búsqueda correcto está hardcodeado en `BGG_SEARCH_OVERRIDES` dentro de `01_data_understanding/ludoteca/ludoteca_source.py`. Los combos/puzzles sin ficha real en BGG (ajedrez+damas, el puzzle de 1000 piezas, etc.) están en `BGG_SKIP` y no muestran link. Los candidatos del top N de BGG ya traen su link exacto directo del dataset de ranking, sin necesidad de búsqueda.

### Enriquecer con datos de BGG

`01_data_understanding/bgg/enrich_bgg.py` completa `descripcion`, `disenador`, `edad_min`, `jug_min/max`, `jug_best_min/max`, `duracion`/`duracion_min`/`duracion_max`, `complejidad` (y `puntaje_bgg`/`reviews_bgg`/`ranking_bgg` para tus propios juegos, que no los traen de otro lado) para los juegos que tienen un link **exacto** a BGG.

**Hoy corre en `--mode dummy` (default), un placeholder temporal:** la vía oficial (`--mode api`, `xmlapi2/thing`) sigue bloqueada (401 sin auth hasta que BGG apruebe la aplicación registrada), y scrapear la página normal está descartado (Cloudflare la protege con un challenge que no se evade ni con cookies de una sesión ya autenticada — se probó explícito, ver `DATA_PLAYBOOK.md`). En cambio, `--mode dummy` usa un dataset público de terceros con un **snapshot de BGG de 2025** (`games_detailed_info2025.csv` de `mmpa/board_game_analysis` en Hugging Face, ~28.000 juegos, sin auth) — cubre ~98% del universo actual (999/1020 ids). No trae precio (BGG no lo trackea; Amazon tampoco se consultó — ver "Pendiente" abajo). Un juego que no esté en ese snapshot no tiene match — sin error, sin dato inventado, esos campos quedan en `null` hasta que BGG apruebe la app.

Cuando eso pase, correr:
```bash
python3 01_data_understanding/bgg/enrich_bgg.py --mode api
python3 02_data_preparation/integrate_data.py
```
y reemplazar el paso del cron (`sync-data.yml`) para que use `--mode api` en vez de dejar el default.

### Columnas calculadas

Ninguna de estas cinco viene directo de una fuente: `02_data_preparation/construct_data.py` las deriva de otras columnas ya integradas.

- `puntaje_ajust_bgg = puntaje_bgg - 3 × 1.4 / √reviews_bgg` — penaliza puntajes altos con pocas reviews. La fórmula viene del Sheet original antes de simplificarlo (se leyó la celda real antes de borrar la columna, no se reinventó — ver el docstring de `construct_data.py`, incluida una inconsistencia que había entre filas y cuál de las dos variantes quedó como oficial).
- `precio_calidad = promedio( -zscore(costo), zscore(puntaje_ajust_bgg) )` — más barato y mejor puntaje ajustado, mejor relación. Mismo origen que la anterior.
- `duracion` — promedio de `duracion_min`/`duracion_max` (ambos de BGG); si falta uno de los dos, el que haya.
- `modo` (`Competitivo`/`Cooperativo`/`Equipos`/`Cooperativo y competitivo`) — derivado de las mecánicas/categorías de BGG (`Cooperative Game`, `Team-Based Game`, `Semi-Cooperative Game`) **solo si no está ya cargado a mano** en `mi_ludoteca.json`; sin mecánicas/categorías en el caché, queda en `null` en vez de asumir "Competitivo" a ciegas.
- `transportable` (`Sí`/`Más o menos`/`No`, qué tan fácil es llevar la caja) — BGG no trackea tamaño de caja en ningún campo; como proxy se usa complejidad + duración (calibrado contra Pistas Cruzadas/La Isla Prohibida/Catan, los únicos tres casos de referencia disponibles). Es una estimación, no un dato medido — sin complejidad o duración, `null`.

### Sincronizar a mano

Si no querés esperar al cron, desde GitHub: Actions → "Sync data.json" → Run workflow. O localmente:
```bash
python3 01_data_understanding/bgg/collect_bgg_rankings.py
python3 01_data_understanding/bgg/enrich_bgg.py
python3 02_data_preparation/integrate_data.py
python3 02_data_preparation/construct_data.py
```

## Qué tiene

- Buscador instantáneo por nombre (Mi ludoteca).
- Filtro "¿cuántos jugadores somos?" (usa Jug. mín/máx, y marca con un tag verde "Best con N" si N coincide con Jug Best mín/máx).
- Filtros por Estado en Mi ludoteca (Own / Prev. owned).
- Orden por Puntaje ajustado, Puntaje BGG, Mi puntaje, Complejidad o Duración.
- Toggle "Según mi gusto" (duración ≤60 min, complejidad ≤2.5), tomado de la sección "Mi gusto" de la pestaña Resumen.
- Complejidad con color (verde→rojo), como el formato condicional del Sheet.
- Link directo a BGG en el título de cada tarjeta.
- "¿Qué jugamos hoy?": recomendador simple (no toma nada del Sheet, es una heurística en `shared.js::recommendationScore` que combina Mi gusto + N jugadores dentro de Jug Best mín/máx + puntaje personal/BGG).
- "¿Cuál comprar?": Watchlist (hasta ~1000 candidatos del top N de BGG + lo que no es tuyo) filtrada por tipo (modo), duración, complejidad y jugadores, con link a la tienda y costo cuando están cargados/relevados, y relación precio/calidad calculada (ver "Columnas calculadas"). El ~2% de candidatos sin match en el dataset placeholder de BGG no tiene duración/complejidad/jugadores/modo — las tarjetas lo muestran como "?" en vez de ocultarse.

## Pendiente si esto vale la pena

- Comparar juegos lado a lado.
- Filtro/orden adicional en "¿Cuál comprar?" para que ~1000 candidatos sea navegable (hoy no hay paginación ni un piso de puntaje mínimo).
- Precio de Amazon (u otra tienda más allá de Bosque Lúdico): no se investigó todavía una fuente sin auth/bot-detection para eso; sería un caso igual al de Bosque Lúdico (`01_data_understanding/<fuente_nueva>/`, resolver link + relevar precio, nunca scrapear Amazon directo sin chequear antes su robots.txt y bot-detection).
- Cuando BGG apruebe la app: correr `enrich_bgg.py 'un id puntual' --mode api --force` para reemplazar, juego por juego, lo que vino del dataset placeholder por el dato oficial; `--mode api` sin ids corre sobre todo el universo de una.
