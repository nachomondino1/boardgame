# Juegos de mesa

Prototipo de página estática para buscar y filtrar la colección de juegos de mesa (sin build system: HTML + CSS + JS vanilla).

Vivo en: https://nachomondino1.github.io/boardgame/

## Comandos

**Correr la web en local:**
```bash
cd docs && python3 -m http.server 8765
```
Y abrir `http://localhost:8765`.

**Actualizar los datos de la web** (después de tocar algo en `data/01_data_understanding/`, o para traer juegos/rankings nuevos de BGG) — una sola línea, corre todo el pipeline y lo manda a producción (commit + push + PR + merge a `main`):
```bash
./sync_data.sh
```

 Nota: Sino esperar a los 1º de cada mes que se corre la cronjob local que creé. Corre el ./sync_data.sh

**Agregar un juego nuevo al catálogo:**
```bash
python3 01_data_understanding/collect_initial_data/search_new_game.py --add "Nombre o bgg_id" --estado "Own"
```
`--estado` es opcional — sin él, el juego queda como Watchlist implícito (ver "Un juego sin fila no es un juego sin datos" en `DATA_PLAYBOOK.md`).

**Cambiar el estado de un juego** (Own, Want to buy, Prev. owned) **o tu puntaje:** se hace en BGG, en tu colección; después corré `refresh_bgg_data.py` (o `./sync_data.sh`) y lo trae solo. Un juego que no marcás en BGG queda como Watchlist.

**Rechequear links de Cazagangas** (de a tandas, no bloquea el resto):
```bash
python3 01_data_understanding/collect_initial_data/cazagangas/check_cazagangas_links.py --limit 100
```

## Páginas

- `index.html` — **Landing**: presenta el sitio y lleva a las otras tres páginas; muestra algunos números de la colección (juegos en casa, para comprar, mejor ranking) leídos de `data.json`.
- `ludoteca.html` — **Mi ludoteca**: los juegos con Estado Own o Prev. owned (lo que tenés o tuviste), buscador, filtros y orden. Watchlist no se navega acá, solo en ¿Cuál comprar?.
- `hoy.html` — **¿Qué jugamos hoy?**: elegís cuántos son y te muestra qué podés jugar de lo que ya tenés (Estado = Own), ordenado por Ranking BGG por default. El toggle "incluir Watchlist" extiende la búsqueda a lo que no tenés todavía, y el toggle "buscar por cantidad ideal (best)" cambia el filtro de jugadores de Jug. mín/máx a Jug Best min/máx.
- `comprar.html` — **¿Cuál comprar?**: solo Watchlist, con sliders de duración máxima y complejidad máxima, el mismo filtro de jugadores, y (cuando están cargados/relevados) link a la tienda, costo y relación precio/calidad en cada tarjeta, con opción de ordenar por estos dos últimos. Incluye una sección colapsable "Comparar dos juegos" (tabla lado a lado con todos los campos relevantes, resaltando quién gana cada fila) — antes era una página aparte (`comparar.html`), se fusionó acá porque se usa siempre junto con esta página.

## Archivos

- `docs/` — el sitio tal cual lo sirve GitHub Pages (**Deploy from branch** `main`, carpeta `/docs`):
  - `docs/index.html` / `docs/ludoteca.html` / `docs/hoy.html` / `docs/comprar.html` — las 4 páginas.
  - `docs/css/pages/comparar.css` — estilos de la sección "Comparar dos juegos" dentro de `comprar.html` (ver arriba).
  - `docs/js/shared.js` — helpers comunes a las 4 páginas (carga de datos, armado de las tarjetas, nav, Google Analytics, etc.).
  - `docs/css/` (`components/` + `pages/`) / `docs/js/landing.js` / `ludoteca.js` / `hoy.js` / `comprar.js` — estilos y lógica de cada página.
  - `docs/data/data.json` — el universo de juegos, con las columnas derivadas ya calculadas. Se regenera solo, ver abajo.
- `data/01_data_understanding/bgg_collection.jsonl` — tu colección en BGG, cruda y con los nombres de BGG (`own`, `prevowned`, `wanttobuy`, `rating`…). Es de donde salen `estado` y `mi_puntaje`. Se regenera con `refresh_bgg_data.py`; ya no hay archivo manual de ludoteca.
- `data/01_data_understanding/bgg_data.jsonl` — **el universo de juegos**: datos de BGG **crudos**, con los mismos nombres de campo que BGG (`yearpublished`, `minplayers`, `suggested_num_players`, `average`…), una fila por juego. No se calcula nada acá: las columnas derivadas (nombre, grupo, rango de jugadores de la comunidad, best, precio de referencia…) se construyen en `02_data_preparation/construct_data.py`. Un juego nuevo se suma con `search_new_game.py --add`; los datos que cambian (ranking, puntaje, votos, marketplace) se actualizan con `refresh_bgg_data.py`. Gitignored, ver `DATA_PLAYBOOK.md`.
- `data/01_data_understanding/cazagangas_data.jsonl` — `bgg_id`, `link_cazagangas` y código HTTP real (verificado) de ese link; el link vive solo acá. Lo llena `search_new_game.py --add` y lo re-verifica `check_cazagangas_links.py` (ver abajo).
- `01_data_understanding/collect_initial_data/bgg/` — `bgg_common.py` (librería: API de BGG, dataset de Hugging Face y lectura/escritura de los `.jsonl`), `initialize_bgg_data.py` (bootstrap único, no se vuelve a correr) y `refresh_bgg_data.py` (actualiza desde la API los campos que cambian, con `--dry-run`; necesita `BGG_TOKEN` en `.env`).
- `01_data_understanding/collect_initial_data/cazagangas/` — `cazagangas_common.py` (slug best-effort + verificación HTTP) y `check_cazagangas_links.py` (re-verifica masivamente los links ya cargados, manual).
- `01_data_understanding/collect_initial_data/search_new_game.py` — vive afuera de `bgg/`/`cazagangas/` porque orquesta las dos: con `--add <id o nombre>` suma un juego nuevo a `bgg_data.jsonl` + `cazagangas_data.jsonl` (si el slug verifica 200). Ver el README de `01_data_understanding/`.
- `01_data_understanding/collect_initial_data/cazagangas/check_cazagangas_links.py` — verifica con un HEAD real los links ya guardados en `cazagangas_data.jsonl` (no arma ninguna URL) y guarda el código HTTP (`200`/`404`/`error`). Corre a mano (`--limit N` para ir de a tandas), no está en `sync_data.sh` — ver `DATA_PLAYBOOK.md`.
- `02_data_preparation/integrate_data.py` — junta `bgg_data.jsonl` (base) + `bgg_collection.jsonl`/`cazagangas_data.jsonl` (por `bgg_id`) en un solo archivo (`data/02_data_preparation/integrated_data.jsonl`, gitignored: es un intermedio del build, se regenera siempre). Solo integra, no calcula nada.
- `02_data_preparation/construct_data.py` — lee `data/02_data_preparation/integrated_data.jsonl`, calcula las columnas derivadas (`duracion`, `modo`, `puntaje_ajust_bgg`, `precio_calidad` — ver "Columnas calculadas" abajo) y escribe `docs/data/data.json`. `transportable`/`bgg_url`/`link_cazagangas`/`grupo`/`cazagangas_status` no se calculan acá, pasan de largo tal cual vienen (`transportable` es 100% manual, ver `01_data_understanding/README.md`; los otros cuatro ya vienen resueltos de `integrate_data.py`).
- `02_data_preparation/select_data.py` — corre después de `construct_data.py`, sobre `docs/data/data.json`: recorta los candidatos con `estado = "Watchlist"` (nunca los curados — `Own`/`Prev. owned`/`Want to buy`/`Descartado` siempre quedan) descartando los que están por debajo del percentil `MIN_REVIEWS_PERCENTILE` de reviews en BGG (calculado sobre el propio Watchlist de cada corrida, no un número fijo) y quedándose con los `TOP_N_WATCHLIST` mejor puntuados del resto. Pensado para que "¿Cuál comprar?" no tenga que lidiar con miles de tarjetas de baja calidad de dato/interés.
- `sync_data.sh` — una sola línea para actualizar todo y mandarlo a la web: corre `search_new_game.py` + `integrate_data.py` + `construct_data.py` + `select_data.py`, y si `docs/data/data.json` cambió, lo commitea, pushea `staging`, abre un PR a `main` y lo mergea (GitHub Pages sirve directo de `main:/docs`, así que el merge dispara el redeploy). `check_cazagangas_links.py` no corre acá (ver arriba).
- `scripts/cron_sync_data.sh` + `scripts/sync_launcher.c` — automatizan `sync_data.sh` **local** (no en CI: desde que `data/01_data_understanding/` es gitignored, CI no tiene de dónde leer esos archivos — ver DATA_PLAYBOOK.md, "Gitignorear toda la fuente cruda"). Un LaunchAgent de macOS (`~/Library/LaunchAgents/com.nachomondino.boardgame-sync.plist`, no versionado, es config de esta máquina) dispara `sync_launcher.c` compilado (`~/cronjobs/boardgame-sync/`) el día 1 de cada mes y en cada login, que a su vez corre `cron_sync_data.sh` (chequea que no haya corrido hace menos de ~25 días, y si no, llama a `sync_data.sh`). El binario compilado existe para darle Full Disk Access (macOS protege `~/Documents` de procesos en background) acotado a esta automatización puntual, en vez de dárselo a `/bin/bash` en general.
- `01_data_understanding/collect_initial_data/bosque_ludico/` — **[PAUSADO]** precio en la tienda. Los scripts existen (`resolve_bosque_links.py`/`collect_bosque_precios.py`) pero nada los corre activamente, y a diferencia de `cazagangas_data.jsonl` su salida ni siquiera está commiteada (ver `.gitignore`) — integrarla a `integrate_data.py` es trabajo futuro, ver `01_data_understanding/README.md` y `DATA_PLAYBOOK.md`.
- `03_modeling/`, `04_evaluation/`, `05_deployment/` — estructura tipo CRISP-DM que le dimos al repo (ver el README de cada carpeta); `03_modeling/`/`04_evaluation/` son placeholders (no hay predicción, del dato recolectado se pasa directo a construir lo que consume el sitio).

### Links a BGG

Cada juego linkea directo a `https://boardgamegeek.com/boardgame/<bgg_id>` — el `bgg_id` sale del ranking de BGG para los candidatos, o se resuelve por búsqueda (`geeksearch.php?...&q=<nombre>`) en el bootstrap para tus propios juegos sin link exacto cargado (`BGG_SEARCH_OVERRIDES`/`BGG_SKIP` en `initialize_bgg_data.py`, mismo patrón que antes — "Misterio (Ruibal)" → busca "Misterio", etc.). BGG cerró el acceso sin auth a su API XML (401), así que no hay forma automática de resolver el id exacto para esos casos de búsqueda; ya no aplica: el catálogo es `bgg_data.jsonl` y todo juego trae su `bgg_id`; la URL se arma en `construct_data.py`.

### De dónde salen los datos de BGG

`search_new_game.py`/`initialize_bgg_data.py` completan `descripcion`, `disenador`, `edad_min`, `jug_min/max`, `jug_best_min/max`, `duracion_min/max`, `complejidad`, `puntaje_bgg`, `reviews_bgg`, `ranking_bgg`, `mecanicas`, `categorias`, `imagen` (URL del thumbnail, CDN de BGG) para los juegos que tienen un link exacto a BGG. `imagen` se muestra como miniatura en cada tarjeta (`docs/js/shared.js`, `cardTemplate`); si falta (juego sin match en el dataset), la tarjeta se ve igual sin ella.

**Hoy corre en `--mode dummy` (default), un placeholder temporal:** la vía oficial (`--mode api`, `xmlapi2/thing`) sigue bloqueada (401 sin auth hasta que BGG apruebe la aplicación registrada), y scrapear la página normal está descartado (Cloudflare la protege con un challenge que no se evade ni con cookies de una sesión ya autenticada — se probó explícito, ver `DATA_PLAYBOOK.md`). En cambio, `--mode dummy` usa un dataset público de terceros con un **snapshot de BGG de 2025** (`games_detailed_info2025.csv` de `mmpa/board_game_analysis` en Hugging Face, ~28.000 juegos, sin auth) — cubre ~98% del universo. No trae precio (BGG no lo trackea; Amazon tampoco se consultó — ver "Pendiente" abajo). Un juego que no esté en ese snapshot no tiene match — sin error, sin dato inventado, esos campos quedan en `null` hasta que BGG apruebe la app.

Cuando eso pase, correr `python3 01_data_understanding/collect_initial_data/search_new_game.py --mode api` y actualizar `sync_data.sh` para que use `--mode api` en vez de dejar el default.

### Columnas calculadas

Ninguna de estas cinco viene directo de una fuente: `02_data_preparation/construct_data.py` las deriva de otras columnas ya integradas.

- `puntaje_ajust_bgg = puntaje_bgg - 3 × 1.4 / √reviews_bgg` — penaliza puntajes altos con pocas reviews. La fórmula viene del Sheet original antes de simplificarlo (se leyó la celda real antes de borrar la columna, no se reinventó — ver el docstring de `construct_data.py`, incluida una inconsistencia que había entre filas y cuál de las dos variantes quedó como oficial).
- `precio_calidad = promedio( -zscore(costo), zscore(puntaje_ajust_bgg) )` — más barato y mejor puntaje ajustado, mejor relación. Hoy da `null` para todos: `costo` depende de la integración con Bosque Lúdico, que todavía no existe (ver "Pendiente").
- `duracion` — promedio de `duracion_min`/`duracion_max` (ambos de BGG); si falta uno de los dos, el que haya.
- `modo` (`Competitivo`/`Cooperativo`/`Equipos`/`Cooperativo y competitivo`) — derivado 100% de las mecánicas/categorías de BGG (`Cooperative Game`, `Team-Based Game`, `Semi-Cooperative Game`, `infer_modo` en `bgg_common.py`); sin mecánicas/categorías, queda en `null` en vez de asumir "Competitivo" a ciegas. No vive en ninguna fuente curada a mano.


## Qué tiene

- Buscador instantáneo por nombre (Mi ludoteca).
- Filtro "¿cuántos jugadores somos?" (usa Jug. mín/máx, y marca con un tag verde "Best con N" si N coincide con Jug Best mín/máx).
- Filtros por Estado en Mi ludoteca (Own / Prev. owned).
- Orden por Ranking BGG, Puntaje BGG, Mi puntaje, Complejidad o Duración.
- Toggle "Según mi gusto" (duración ≤60 min, complejidad ≤2.5), tomado de la sección "Mi gusto" de la pestaña Resumen.
- Complejidad con color (verde→rojo), como el formato condicional del Sheet.
- Link directo a BGG en el título de cada tarjeta.
- "¿Qué jugamos hoy?": filtra por N jugadores dentro de Jug mín/máx (o solo Jug Best mín/máx con "Solo si es el mejor número"), ordenado por Ranking BGG por default (antes había un recomendador heurístico propio en `shared.js::recommendationScore`, sacado por confuso — ver git log, 2026-10-28).
- "¿Cuál comprar?": Watchlist (hasta ~1000 candidatos del top N de BGG + lo que no es tuyo) filtrada por tipo (modo), duración, complejidad y jugadores, con link a la tienda y costo cuando están cargados/relevados, y relación precio/calidad calculada (ver "Columnas calculadas"). El ~2% de candidatos sin match en el dataset placeholder de BGG no tiene duración/complejidad/jugadores/modo — las tarjetas lo muestran como "?" en vez de ocultarse. Variantes/expansiones del mismo sistema de juego (ej. las cajas de Unmatched) se colapsan en una sola tarjeta, con el resto desplegable (el grupo se deriva de las familias de BGG en `construct_data.py`). Link a la ficha real en [Cazagangas](https://www.cazagangas.com.ar) cuando `check_cazagangas_links.py` confirmó que existe (código 200) — ver `data/01_data_understanding/cazagangas_data.jsonl`. Resultados paginados (60 a la vez, "Mostrar más") y los sliders/el buscador debounced — renderizar hasta ~1000 tarjetas en cada cambio de filtro se sentía lento, sobre todo en mobile.

## Pendiente si esto vale la pena
- Piso de puntaje mínimo en "¿Cuál comprar?" (hoy existe paginación — "Mostrar más", 60 a la vez — pero no un filtro para sacar directamente los candidatos peor puntuados).
- Integrar `bosque_data.csv` en `integrate_data.py` (mismo patrón que `cazagangas_data.jsonl`), para que `costo`/`link_tienda`/`precio_calidad` dejen de ser `null`. Los scripts de recolección ya existen y funcionan (`01_data_understanding/collect_initial_data/bosque_ludico/`), falta sumarlos al merge.
- Precio de Amazon (u otra tienda más allá de Bosque Lúdico): no se investigó todavía una fuente sin auth/bot-detection para eso; sería un caso igual al de Bosque Lúdico, nunca scrapear Amazon directo sin chequear antes su robots.txt y bot-detection.
- Ampliar `check_cazagangas_links.py` a scraper real de Cazagangas: hoy solo confirma que el link existe (código HTTP). Pendiente sumar precio, stock/disponibilidad y en qué tienda(s) de Argentina se puede comprar cada juego (Cazagangas agrega varias tiendas por juego) — mismo patrón que `costo`/`link_tienda`/`precio_calidad` ya tienen pensado para Bosque Lúdico (ver el bullet de arriba), pero con Cazagangas como fuente en vez de (o además de) Bosque Lúdico.
- Cuando BGG apruebe la app: `search_new_game.py --mode api` reemplaza el placeholder sin tocar nada más del pipeline.
- Premio Spiel des Jahres (Ganador/Shortlist/Recomendado): no está en el dataset placeholder de BGG (se chequeó el header, no trae esa columna) ni en la API oficial. Falta decidir la fuente (¿scraping del sitio oficial de Spiel des Jahres, o carga manual una vez al año ya que la lista es chica y estable?) y cómo cargarla — probablemente como un archivo propio chico en `data/01_data_understanding/`, nunca enriquecimiento automático de BGG.
- Describe data / Explore data (CRISP-DM 2 y 3): contar nulos, correlaciones entre variables, etc. — no existen todavía.
