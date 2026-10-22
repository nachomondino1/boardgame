# 01 — Data understanding

Una carpeta por fuente. Cada una solo recolecta/resuelve datos de su fuente; integrarlas en un único `data.json` es trabajo de `../02_data_preparation/integrate_data.py`, nunca al revés — 02 puede importar de 01, 01 nunca depende de un output de 02.

- `sheet/sheet_source.py` — la **única** pieza del repo que le habla al Google Sheet "Juegos_de_mesa" (pestaña "Juegos"), editado a mano por el usuario: lo descarga como CSV (export público, sin login) y lo normaliza a una lista de juegos con su Estado y el link a BGG ya resuelto. `load_games()` es el punto de entrada que usan tanto `integrate_data.py` como `bosque_ludico/resolve_bosque_links.py` — nadie más vuelve a leer el Sheet por su cuenta.
  - Ver `../DATA_PLAYBOOK.md` para el detalle completo del esquema (`HEADER_RULES`), de dónde sale cada columna y qué decisiones se tomaron al diseñarlo.
  - `SPREADSHEET_ID` y `GID` de la pestaña están hardcodeados ahí.
  - Correr `python3 01_data_understanding/sheet/sheet_source.py` solo imprime un resumen de cuántos juegos hay por Estado — útil para chequear rápido que el Sheet se está leyendo bien sin correr todo el pipeline.
- `bgg/enrich_bgg.py` — arma un caché de BGG (puntaje, reviews, ranking, complejidad, diseñador, edad mín., jugadores, duración) por juego con link exacto a BGG, en `docs/data/cache/bgg/<id>.json` (un archivo por juego, no un único dataset: así un juego nuevo no repaga todas las requests). Paso manual, **bloqueado**: BGG devuelve 401 sin auth en `xmlapi2` hasta que aprueben la app registrada (ver docstring del script).
- `bosque_ludico/` — precio actual de cada juego en Watchlist en [El Bosque Lúdico](https://www.elbosqueludico.com.ar), en dos pasos (ver más abajo).

Si en algún momento hace falta explorar el Sheet crudo (ej. detectar filas con datos faltantes o inconsistentes antes de limpiar), ese análisis va en `sheet/`.

## bosque_ludico/: recolección de precios

Para la página "¿Cuál comprar?" interesa el precio actual de cada juego en Watchlist (los que no tenés, candidatos a comprar — nunca los que ya están Own/Prev. owned). El link a BGG ya sale de `sheet_source.load_games()`; estos dos scripts resuelven el link a la ficha de cada juego en la tienda y relevan el precio, en dos pasos separados porque cambian a ritmos distintos (el link a una ficha es estable; el precio no):

1. `resolve_bosque_links.py` — llama a `sheet_source.load_games()`, filtra `estado == "Watchlist"`, y matchea cada nombre contra el listado completo de productos de la tienda (su `sitemap.xml.gz`, no `/search/`: ver el por qué en el docstring del script). Guarda `links.json`: por juego, nombre + link a BGG + link a la tienda (o `null` si no hay match confiable).
2. `collect_bosque_precios.py` — lee `links.json` y le pega a cada ficha de producto para sacar precio, disponibilidad y stock del momento. Guarda `bosque_data.json`.

**Por qué no se usa el buscador de la tienda (`/search/?q=...`):** su `robots.txt` lo bloquea explícitamente (`Disallow: /search/`). En cambio se descarga una sola vez el sitemap público (pensado para ser indexado) y se matchea por texto localmente — ni un solo request a una ruta disallowed.

**Si un match sale mal o no aparece ninguno:** revisar `match_score` en `links.json` y, si hace falta, agregar el juego a `BOSQUE_SEARCH_OVERRIDES` (para forzar el término de búsqueda) o `BOSQUE_SKIP` (si la tienda no lo vende) dentro de `resolve_bosque_links.py` — mismo patrón que `BGG_SEARCH_OVERRIDES`/`BGG_SKIP` en `sheet/sheet_source.py`.

Ambos archivos de salida son locales (gitignored, igual que el caché de BGG). `../02_data_preparation/integrate_data.py` toma `bosque_data.json` como **fallback** de `costo`/`link_tienda`: completa esos campos solo si el Sheet los dejó vacíos, nunca pisa un valor ya cargado a mano. Si no corriste estos scripts, `integrate_data.py` sigue funcionando igual (el fallback se salta en silencio). Correr a mano cuando haga falta un precio actualizado:

```bash
python3 01_data_understanding/bosque_ludico/resolve_bosque_links.py
python3 01_data_understanding/bosque_ludico/collect_bosque_precios.py
python3 02_data_preparation/integrate_data.py   # para que data.json tome los precios nuevos
```
