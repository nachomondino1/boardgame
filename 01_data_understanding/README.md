# 01 — Data understanding

Una carpeta por fuente. Cada una solo recolecta/resuelve datos de su fuente; integrarlas en un único `data.json` es trabajo de `../02_data_preparation/integrate_data.py`, nunca al revés — 02 puede importar de 01, 01 nunca depende de un output de 02.

- `ludoteca/ludoteca_source.py` + `ludoteca/mi_ludoteca.json` — lo que tenés o tuviste (Estado Own / Prev. owned), editado directo acá (a mano o pidiéndoselo a Claude) en vez de en un Google Sheet. Ver "ludoteca/" más abajo para el porqué.
- `bgg/collect_bgg_rankings.py` — descarga el top N (1000 por default) del ranking de BGG desde un dataset público de terceros en GitHub (no la API de BGG, bloqueada — ver abajo) y lo guarda **versionado** en `bgg/bgg_top1000.csv`. Es la base del universo de "candidatos a comprar" (ver `game_universe.py`).
- `bgg/enrich_bgg.py` — arma un caché de BGG (descripción, diseñador, edad mín., jugadores, jugadores ideal, duración mín./máx., complejidad, puntaje, reviews, ranking, mecánicas, categorías) por juego con link exacto a BGG, en `docs/data/cache/bgg/<id>.json` (un archivo por juego, no un único dataset: así un juego nuevo no repaga todas las requests). Hoy corre en modo `dummy` (un dataset placeholder de terceros, automático, ver abajo); el modo `api` (oficial) sigue bloqueado hasta que BGG apruebe la app. `02_data_preparation/construct_data.py` deriva `duracion`, `modo` y `transportable` a partir de estos campos — ver `../README.md`, "Columnas calculadas".
- `bosque_ludico/` — precio actual de cada juego en Watchlist en [El Bosque Lúdico](https://www.elbosqueludico.com.ar), en dos pasos (ver más abajo).
- `game_universe.py` — combina `ludoteca/` (lo tuyo) + `bgg/bgg_top1000.csv` (candidatos) en un único universo de juegos (ver más abajo). Vive en la raíz de `01_data_understanding/`, no adentro de una carpeta de fuente, porque es la única pieza que mira más de una a la vez.

## ludoteca/: lo que tenés o tuviste, en un JSON editado a mano

`mi_ludoteca.json` reemplaza al Google Sheet que usaba el proyecto originalmente. Por qué: el Sheet se justificaba cuando tenía ~70 columnas cargadas a mano fila por fila (los datos de BGG y de Bosque Lúdico). Una vez que esas dos fuentes se automatizaron (`bgg/`, `bosque_ludico/`) el Sheet quedó reducido a ~10 columnas de ~30 filas que cambian pocas veces al año — mantener el fetch a la API de Google (CSV + .xlsx para hyperlinks) para eso ya no se justificaba. Ahora es un archivo versionado en el repo: lo editás directo (vos a mano, o pidiéndoselo a Claude) y listo, sin depender de que el Sheet siga siendo público ni de ninguna API externa para esto.

Esquema de cada entrada (ver el docstring de `ludoteca_source.py` para el detalle completo): `nombre_en` y `estado` ("Own"/"Prev. owned") son obligatorios; `bgg_url` es opcional (si no lo tenés, se resuelve una búsqueda por nombre, mismo criterio que antes — `BGG_SEARCH_OVERRIDES`/`BGG_SKIP` en el mismo archivo); el resto (`nombre_es`, `modo`, `pros`, `cons`, `mi_puntaje`, `youtube`, `notas`) son opcionales.

`load_games()` es el punto de entrada — nadie más lee `mi_ludoteca.json` directo.

## game_universe.py: ludoteca + top N de BGG = el universo completo

`load_universe()` es el punto de entrada que usan tanto `integrate_data.py` como `bosque_ludico/resolve_bosque_links.py`:

1. `ludoteca/ludoteca_source.load_games()` — lo que tenés o tuviste.
2. `bgg/bgg_top1000.csv` — el top N de BGG. Cualquier juego de ahí que **no** sea ya tuyo (dedupe por id de BGG) entra como candidato con Estado `"Watchlist"`.
3. El resultado es tu ludoteca + candidatos, la ludoteca siempre primero y ganando ante cualquier duplicado.

Esto reemplaza lo que antes era la columna Watchlist del Sheet: en vez de cargar a mano qué juegos te interesan, el universo de candidatos es automáticamente "todo lo que está en el top N de BGG y no es tuyo todavía". `03_modeling/`/`04_evaluation/` no existen hoy (no hay predicción, el repo va directo de datos a la página), así que este es el único filtro/curación de candidatos que hay.

Si `bgg/bgg_top1000.csv` no corrió todavía, `load_universe()` devuelve solo lo de tu ludoteca (no bloquea el resto del pipeline).

## bgg/enrich_bgg.py: modo dummy mientras la API está bloqueada

BGG cerró el acceso sin auth a `xmlapi2` (401 hasta que aprueben la app registrada) y su página normal exige pasar un challenge de Cloudflare — scrapearla está descartado (ver `DATA_PLAYBOOK.md`, "Decisiones clave"). Mientras tanto, `enrich_bgg.py --mode dummy` (default) usa como placeholder un dataset público de terceros con un snapshot de BGG de **2025** (`games_detailed_info2025.csv` de `mmpa/board_game_analysis` en Hugging Face, ~28.000 juegos, sin auth; probablemente armado corriendo `xmlapi2` contra la lista completa de BGG — no es la fuente oficial, pero no le pega a BGG en absoluto). Cubre ~98% del universo actual (999/1020 ids) — trae casi todo lo que trae la API oficial: descripción, diseñador, el poll de "mejor cantidad de jugadores" (`jug_best_min/max`), duración mín./máx. separadas. No trae precio (BGG no lo trackea). Un juego que no esté en el snapshot simplemente no tiene match — sin error, sin dato inventado, queda en `null` en `data.json`. `--mode api` reemplaza el placeholder sin tocar nada más del pipeline en cuanto esté disponible.

Dos quirks del dataset que el script ya filtra, por si hace falta debuggear algo raro: algunos campos vienen como el repr de Python de una lista/dict (p. ej. `boardgamedesigner`), se parsean con `ast.literal_eval` (nunca ejecuta código, solo literales); y `minplaytime`/`maxplaytime`/`minage` usan `0` como sentinel de "sin dato" en vez de dejar la celda vacía — el script lo trata como `null`, no como un valor real (un juego con "0 min" de duración sería un bug, no un dato).

## bosque_ludico/: recolección de precios

Para la página "¿Cuál comprar?" interesa el precio actual de cada juego en Watchlist (ahora puede ser un universo grande — hasta ~1000 candidatos del top N de BGG, no una lista chica cargada a mano). El link a BGG ya sale de `game_universe.load_universe()`; estos dos scripts resuelven el link a la ficha de cada juego en la tienda y relevan el precio, en dos pasos separados porque cambian a ritmos distintos (el link a una ficha es estable; el precio no):

1. `resolve_bosque_links.py` — llama a `game_universe.load_universe()`, filtra `estado == "Watchlist"`, y matchea cada nombre contra el listado completo de productos de la tienda (su `sitemap.xml.gz`, no `/search/`: ver el por qué en el docstring del script). Guarda `links.json`: por juego, nombre + link a BGG + link a la tienda (o `null` si no hay match confiable).
2. `collect_bosque_precios.py` — lee `links.json` y le pega a cada ficha de producto para sacar precio, disponibilidad y stock del momento. Guarda `bosque_data.json`. Acepta `--limit N` para relevar de a tandas (a 5s de intervalo, 1000 juegos son ~85 minutos) — los resultados de corridas anteriores no se pisan, se mergea por nombre.

**Por qué no se usa el buscador de la tienda (`/search/?q=...`):** su `robots.txt` lo bloquea explícitamente (`Disallow: /search/`). En cambio se descarga una sola vez el sitemap público (pensado para ser indexado) y se matchea por texto localmente — ni un solo request a una ruta disallowed.

**Si un match sale mal o no aparece ninguno:** revisar `match_score` en `links.json` y, si hace falta, agregar el juego a `BOSQUE_SEARCH_OVERRIDES` (para forzar el término de búsqueda) o `BOSQUE_SKIP` (si la tienda no lo vende) dentro de `resolve_bosque_links.py` — mismo patrón que `BGG_SEARCH_OVERRIDES`/`BGG_SKIP` en `ludoteca/ludoteca_source.py`.

`links.json` y `bosque_data.json` son locales (gitignored, igual que el caché de BGG). `../02_data_preparation/integrate_data.py` toma `bosque_data.json` como **fallback** de `costo`/`link_tienda`: completa esos campos solo si quedaron vacíos, nunca pisa un valor ya cargado a mano en `mi_ludoteca.json`. Si no corriste estos scripts, `integrate_data.py` sigue funcionando igual (el fallback se salta en silencio).

## Correr todo el pipeline de 01 a mano

```bash
python3 01_data_understanding/bgg/collect_bgg_rankings.py        # refresca el top N de BGG
python3 01_data_understanding/bgg/enrich_bgg.py                   # modo dummy (default) o --mode api
python3 01_data_understanding/bosque_ludico/resolve_bosque_links.py
python3 01_data_understanding/bosque_ludico/collect_bosque_precios.py --limit 100
python3 02_data_preparation/integrate_data.py
python3 02_data_preparation/construct_data.py
```

`.github/workflows/sync-data.yml` corre los primeros cuatro pasos (sin `bosque_ludico/`, que queda manual por el costo en tiempo/requests) el día 1 de cada mes.
