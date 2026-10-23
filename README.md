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
  - `docs/data/data.json` — el universo de juegos, con las columnas derivadas ya calculadas. Se regenera solo, ver abajo.
- `01_data_understanding/collect_initial_data/bgg/bgg_data.csv` — **el universo de juegos**: identidad + Estado (`Own`/`Prev. owned`/`Watchlist`) + todos los datos de BGG, en un único CSV, `bgg_id` como primera columna. Se commitea (no se gitignorea): las columnas propias (`nombre`, `estado`, `modo`, `mi_puntaje`, `pros`, `cons`, `youtube`, `notas`) las cargaste vos a mano o se las pediste a Claude. Ver el README de `01_data_understanding/` para el detalle completo.
- `01_data_understanding/collect_initial_data/bgg/collect_bgg_data.py` — arma/refresca `bgg_data.csv`. La primera vez (bootstrap) arma el universo con el top N del ranking de BGG; de ahí en más solo refresca los datos de BGG de lo que ya está — agregar un juego nuevo es explícito, con `--add` (ver el README de la carpeta).
- `02_data_preparation/construct_data.py` — lee `bgg_data.csv`, calcula las columnas derivadas (`duracion`, `modo`, `transportable`, `puntaje_ajust_bgg`, `precio_calidad` — ver "Columnas calculadas" abajo) y escribe `docs/data/data.json`.
- `.github/workflows/sync-data.yml` — corre `collect_bgg_data.py` y `construct_data.py` el día 1 de cada mes a las 12:00 UTC y en cada ejecución manual, y si algo cambió lo commitea y pushea a `main`. Eso dispara un redeploy automático de GitHub Pages. Si agregaste un juego y no querés esperar al mes, lo disparás a mano (ver abajo).
- `01_data_understanding/collect_initial_data/bosque_ludico/` — **[EN UN FUTURO]** precio en la tienda. Los scripts existen (`resolve_bosque_links.py`/`collect_bosque_precios.py`) pero están pausados: nada los corre activamente ni integra su salida con `bgg_data.csv` todavía (esa integración, por nombre de juego, es trabajo futuro — ver `01_data_understanding/README.md` y `DATA_PLAYBOOK.md`).
- `03_modeling/`, `04_evaluation/`, `05_deployment/` — estructura tipo CRISP-DM que le dimos al repo (ver el README de cada carpeta); `03_modeling/`/`04_evaluation/` son placeholders (no hay predicción, del dato recolectado se pasa directo a construir lo que consume el sitio).

### Links a BGG

Cada juego linkea directo a `https://boardgamegeek.com/boardgame/<bgg_id>` — el `bgg_id` sale del ranking de BGG para los candidatos, o se resuelve por búsqueda (`geeksearch.php?...&q=<nombre>`) en el bootstrap para tus propios juegos sin link exacto cargado (`BGG_SEARCH_OVERRIDES`/`BGG_SKIP` en `collect_bgg_data.py`, mismo patrón que antes — "Misterio (Ruibal)" → busca "Misterio", etc.). BGG cerró el acceso sin auth a su API XML (401), así que no hay forma automática de resolver el id exacto para esos casos de búsqueda; se arregla a mano agregando `bgg_id` o `bgg_url` directo en la fila de `bgg_data.csv`.

### De dónde salen los datos de BGG

`collect_bgg_data.py` completa `descripcion`, `disenador`, `edad_min`, `jug_min/max`, `jug_best_min/max`, `duracion_min/max`, `complejidad`, `puntaje_bgg`, `reviews_bgg`, `ranking_bgg`, `mecanicas`, `categorias` para los juegos que tienen un link exacto a BGG.

**Hoy corre en `--mode dummy` (default), un placeholder temporal:** la vía oficial (`--mode api`, `xmlapi2/thing`) sigue bloqueada (401 sin auth hasta que BGG apruebe la aplicación registrada), y scrapear la página normal está descartado (Cloudflare la protege con un challenge que no se evade ni con cookies de una sesión ya autenticada — se probó explícito, ver `DATA_PLAYBOOK.md`). En cambio, `--mode dummy` usa un dataset público de terceros con un **snapshot de BGG de 2025** (`games_detailed_info2025.csv` de `mmpa/board_game_analysis` en Hugging Face, ~28.000 juegos, sin auth) — cubre ~98% del universo. No trae precio (BGG no lo trackea; Amazon tampoco se consultó — ver "Pendiente" abajo). Un juego que no esté en ese snapshot no tiene match — sin error, sin dato inventado, esos campos quedan en `null` hasta que BGG apruebe la app.

Cuando eso pase, correr `python3 01_data_understanding/collect_initial_data/bgg/collect_bgg_data.py --mode api` y reemplazar el paso del cron (`sync-data.yml`) para que use `--mode api` en vez de dejar el default.

### Columnas calculadas

Ninguna de estas cinco viene directo de una fuente: `02_data_preparation/construct_data.py` las deriva de otras columnas ya integradas.

- `puntaje_ajust_bgg = puntaje_bgg - 3 × 1.4 / √reviews_bgg` — penaliza puntajes altos con pocas reviews. La fórmula viene del Sheet original antes de simplificarlo (se leyó la celda real antes de borrar la columna, no se reinventó — ver el docstring de `construct_data.py`, incluida una inconsistencia que había entre filas y cuál de las dos variantes quedó como oficial).
- `precio_calidad = promedio( -zscore(costo), zscore(puntaje_ajust_bgg) )` — más barato y mejor puntaje ajustado, mejor relación. Hoy da `null` para todos: `costo` depende de la integración con Bosque Lúdico, que todavía no existe (ver "Pendiente").
- `duracion` — promedio de `duracion_min`/`duracion_max` (ambos de BGG); si falta uno de los dos, el que haya.
- `modo` (`Competitivo`/`Cooperativo`/`Equipos`/`Cooperativo y competitivo`) — derivado de las mecánicas/categorías de BGG (`Cooperative Game`, `Team-Based Game`, `Semi-Cooperative Game`) **solo si no está ya cargado a mano** en `bgg_data.csv`; sin mecánicas/categorías, queda en `null` en vez de asumir "Competitivo" a ciegas.
- `transportable` (`Sí`/`Más o menos`/`No`, qué tan fácil es llevar la caja) — BGG no trackea tamaño de caja en ningún campo; como proxy se usa complejidad + duración (calibrado contra Pistas Cruzadas/La Isla Prohibida/Catan, los únicos tres casos de referencia disponibles). Es una estimación, no un dato medido — sin complejidad o duración, `null`.

### Sincronizar a mano

Si no querés esperar al cron, desde GitHub: Actions → "Sync data.json" → Run workflow. O localmente:
```bash
python3 01_data_understanding/collect_initial_data/bgg/collect_bgg_data.py
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
- Integrar `bosque_data.csv` con `bgg_data.csv` por nombre de juego (`02_data_preparation/`), para que `costo`/`link_tienda`/`precio_calidad` dejen de ser `null`. Los scripts de recolección ya existen y funcionan (`01_data_understanding/collect_initial_data/bosque_ludico/`), falta el paso de integración.
- Precio de Amazon (u otra tienda más allá de Bosque Lúdico): no se investigó todavía una fuente sin auth/bot-detection para eso; sería un caso igual al de Bosque Lúdico, nunca scrapear Amazon directo sin chequear antes su robots.txt y bot-detection.
- Cuando BGG apruebe la app: `collect_bgg_data.py --mode api` reemplaza el placeholder sin tocar nada más del pipeline.
- Describe data / Explore data (CRISP-DM 2 y 3): contar nulos, correlaciones entre variables, etc. — no existen todavía.
