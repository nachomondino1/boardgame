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
- `comprar.html` — **¿Cuál comprar?**: solo Watchlist, con sliders de duración máxima y complejidad máxima, el mismo filtro de jugadores, y (cuando el Sheet los tiene cargados) link a la tienda, costo relevado y relación precio/calidad en cada tarjeta, con opción de ordenar por estos dos últimos.

## Archivos

- `docs/` — el sitio tal cual lo sirve GitHub Pages (**Deploy from branch** `main`, carpeta `/docs`):
  - `docs/index.html` / `docs/hoy.html` / `docs/comprar.html` — las 3 páginas.
  - `docs/js/shared.js` — helpers comunes a las 3 páginas (carga de datos, armado de las tarjetas, nav, etc.).
  - `docs/css/style.css` / `docs/js/app.js` / `docs/js/hoy.js` / `docs/js/comprar.js` — estilos y lógica de cada página.
  - `docs/data/data.json` — datos de la pestaña "Juegos" del Sheet (`Juegos_de_mesa` en Drive). Se regenera solo, ver abajo.
- `01_data_understanding/sheet/sheet_source.py` — la única pieza que le habla al Sheet: descarga la pestaña "Juegos" como CSV (export público, sin login) y resuelve el link a BGG de cada juego (hyperlink puesto a mano, o búsqueda por nombre). Mapea columnas por el texto del encabezado, no por posición, así que si agregás una columna nueva al Sheet no rompe nada (se ignora hasta que se agregue una regla para ella en `HEADER_RULES`). `load_games()` es el punto de entrada que usan tanto `integrate_data.py` como los scripts de Bosque Lúdico — nadie más vuelve a leer el Sheet por su cuenta.
- `02_data_preparation/integrate_data.py` — **solo integra**: `sheet_source.load_games()` (fuente de verdad) + el caché de BGG (`docs/data/cache/bgg/`) + el dataset de precios de Bosque Lúdico (`01_data_understanding/bosque_ludico/bosque_data.json`, si corrió), y escribe `docs/data/data.json`. El Sheet siempre tiene prioridad: BGG y Bosque Lúdico solo completan los campos que el Sheet dejó vacíos.
- `02_data_preparation/construct_data.py` — corre después, sobre el mismo `docs/data/data.json`: calcula `puntaje_ajust_bgg` y `precio_calidad`, que no vienen de ninguna fuente sino que se derivan de otras columnas ya integradas (ver "Columnas calculadas" abajo).
- `01_data_understanding/bgg/enrich_bgg.py` — arma `docs/data/cache/bgg/<id>.json` con datos de BGG (puntaje, reviews, ranking, complejidad, diseñador, edad mín., jugadores, duración) por juego. Paso manual, no corre en el cron (ver abajo por qué).
- `.github/workflows/sync-sheet.yml` — corre `integrate_data.py` y `construct_data.py` el día 1 de cada mes a las 12:00 UTC y en cada ejecución manual, y si `docs/data/data.json` cambió lo commitea y pushea a `main`. Eso dispara un redeploy automático de GitHub Pages. Si agregaste un juego y no querés esperar al mes, lo disparás a mano (ver abajo).
- `01_data_understanding/bosque_ludico/resolve_bosque_links.py` y `collect_bosque_precios.py` — resuelven el link a la ficha de cada juego en Watchlist en [El Bosque Lúdico](https://www.elbosqueludico.com.ar) y relevan su precio actual en `bosque_data.json` (ver el README de la carpeta). Paso manual; `integrate_data.py` lo toma como fallback de `costo`/`link_tienda` si corrió.
- `03_modeling/`, `04_evaluation/`, `05_deployment/` — estructura tipo CRISP-DM que le dimos al repo (ver el README de cada carpeta); son placeholders o apuntan a dónde vive cada cosa.

### Links a BGG

BGG cerró el acceso sin autenticación a su API XML (devuelve 401), así que no se puede resolver el ID exacto de cada juego en el build automático. En cambio, cada juego linkea a una búsqueda de BGG por título, usando la columna "Nombre ingles" del Sheet (no la traducción local) como término (`geeksearch.php?...&q=<nombre>`), que en la práctica cae directo en el juego correcto como primer resultado. Para ediciones locales o proxys (p. ej. "Misterio (Ruibal)" → busca "Misterio", "Memotest (Ruibal)" → busca "Memory"), el término de búsqueda correcto está hardcodeado en `BGG_SEARCH_OVERRIDES` dentro de `01_data_understanding/sheet/sheet_source.py`, tomado de las pistas que ya estaban en la columna Notas del Sheet. Los combos/puzzles sin ficha real en BGG (ajedrez+damas, el puzzle de 1000 piezas, etc.) están en `BGG_SKIP` y no muestran link.

### Enriquecer con datos de BGG

`01_data_understanding/bgg/enrich_bgg.py` completa `puntaje_bgg`, `reviews_bgg`, `ranking_bgg`, `complejidad`, `disenador`, `edad_min`, `jug_min/max`, `jug_best_min/max` y `duracion` para los juegos que tienen un link **exacto** a BGG (no sirve con el link de búsqueda genérico), usando `--mode api` (`xmlapi2/thing`, la vía oficial).

**Bloqueado hasta que BGG apruebe la aplicación registrada:** hoy `xmlapi2` devuelve 401 sin autenticación. El script tiene un `--mode html` pensado como alternativa (reusar en un script las cookies de una sesión de navegador que ya pasó el challenge de Cloudflare a mano), pero **se probó y no funciona**: el `cf_clearance` de Cloudflare queda atado al fingerprint completo de la conexión (TLS/JA3 + stack de headers real del navegador), no solo al valor del cookie — ni `curl` ni `urllib` lo pueden replicar aunque manden el cookie correcto y recién exportado, y Cloudflare devuelve 403 igual. Queda documentado en el código por si en algún momento vale la pena retomarlo de otra forma, pero **no uses `--mode html`, no sirve**.

No tiene sentido invertir en evadir ese fingerprinting (sería la misma clase de bypass de bot-detection que resolver el CAPTCHA a mano, solo que con más código) — así que el enriquecimiento queda pausado hasta que BGG apruebe la app. Ahí es correr:
```bash
python3 01_data_understanding/bgg/enrich_bgg.py --mode api
python3 02_data_preparation/integrate_data.py
```
y en ese punto el paso puede sumarse al cron sin problema (no requiere cookies ni challenge).

### Columnas calculadas

`puntaje_ajust_bgg` y `precio_calidad` ("Relación precio/calidad") no vienen del Sheet ni de ninguna fuente externa: antes vivían como fórmulas manuales en el Sheet, se sacaron de ahí (el Sheet solo deja datos que no son de BGG ni de Bosque Lúdico) y ahora las calcula `02_data_preparation/construct_data.py`:

- `puntaje_ajust_bgg = puntaje_bgg - 3 × 1.4 / √reviews_bgg` — penaliza puntajes altos con pocas reviews.
- `precio_calidad = promedio( -zscore(costo), zscore(puntaje_ajust_bgg) )` — más barato y mejor puntaje ajustado, mejor relación.

Las fórmulas se migraron leyendo las celdas reales del Sheet antes de borrar esas columnas, no se reinventaron (ver el docstring de `construct_data.py` para el detalle, incluida una inconsistencia que había entre filas y cuál de las dos variantes quedó como oficial).

### Sincronizar a mano

Si no querés esperar al cron, desde GitHub: Actions → "Sync data.json desde Google Sheet" → Run workflow. O localmente:
```bash
python3 02_data_preparation/integrate_data.py
python3 02_data_preparation/construct_data.py
```

### Sobre el Sheet público

La pestaña "Juegos" se lee vía el endpoint de export de Google Sheets (`.../export?format=csv&gid=...`), que ya es accesible sin login — no hace falta ninguna API key ni credencial guardada como secret. Si en algún momento el Sheet pasa a ser privado, hay que o volver a compartirlo "Cualquiera con el enlace: Lector", o migrar `sheet_source.py` a usar la API de Sheets con una service account.

## Qué tiene

- Buscador instantáneo por nombre (Mi ludoteca).
- Filtro "¿cuántos jugadores somos?" (usa Jug. mín/máx, y marca con un tag verde "Best con N" si N coincide con Jug Best mín/máx).
- Filtros por Estado en Mi ludoteca (Own / Prev. owned).
- Orden por Puntaje ajustado, Puntaje BGG, Mi puntaje, Complejidad o Duración.
- Toggle "Según mi gusto" (duración ≤60 min, complejidad ≤2.5), tomado de la sección "Mi gusto" de la pestaña Resumen.
- Complejidad con color (verde→rojo), como el formato condicional del Sheet.
- Link directo a BGG en el título de cada tarjeta.
- "¿Qué jugamos hoy?": recomendador simple (no toma nada del Sheet, es una heurística en `shared.js::recommendationScore` que combina Mi gusto + N jugadores dentro de Jug Best mín/máx + puntaje personal/BGG).
- "¿Cuál comprar?": Watchlist filtrada por duración, complejidad y jugadores, con link a la tienda y costo cuando están cargados, y relación precio/calidad calculada (ver "Columnas calculadas").

## Pendiente si esto vale la pena

- Comparar juegos lado a lado.
- Si en algún momento vale la pena el link exacto a BGG (no un search): habría que resolver el ID de cada juego a mano (la API quedó bloqueada) y guardarlo como columna en el Sheet.
