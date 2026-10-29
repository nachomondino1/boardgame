# 01 — Data understanding

Acá vive **collect_initial_data**: recolectar, sin integrar nada todavía (eso es trabajo de `02_data_preparation/`, y 02 puede importar de 01, nunca al revés).

**Regla:** los datos se guardan **crudos, con los mismos nombres de campo que la fuente** y sin calcular nada. Toda columna derivada (nombre, estado, grupo, jugadores best/recomendados, precio de referencia…) se construye en `02_data_preparation/construct_data.py`.

## Archivos de datos (`../data/01_data_understanding/`, gitignored)

- `bgg_data.jsonl` — **el universo de juegos**: una fila por juego, datos de BGG crudos (ver tabla abajo). Todo juego con fila acá existe para el repo.
- `bgg_collection.jsonl` — tu colección en BGG, cruda (`own`, `prevowned`, `wanttobuy`, `rating`…). De acá salen `estado` y `mi_puntaje`.
- `cazagangas_data.jsonl` — `bgg_id`, `link_cazagangas`, `status_http`, `fecha_chequeado`. El link a Cazagangas vive solo acá.

## Scripts

- `collect_initial_data/bgg/bgg_common.py` — librería: requests a la API de BGG (con `BGG_TOKEN` de `.env`) y al dataset de Hugging Face, y lectura/escritura de los `.jsonl`. No se corre directo.
- `collect_initial_data/bgg/initialize_bgg_data.py` — bootstrap único de `bgg_data.jsonl` (top N del ranking de BGG, desde Hugging Face). Ya corrió; no se vuelve a correr salvo para reiniciar el catálogo (`--force`).
- `collect_initial_data/bgg/refresh_bgg_data.py` — trae tu colección (`bgg_collection.jsonl`) y actualiza desde la API los datos que cambian (puntaje, ranking, votos, marketplace) de esos juegos; agrega los de tu colección que no estén en el catálogo. Con `--dry-run` muestra el diff sin escribir; `--fields all` trae todos los campos; `--scope all` recorre todo el catálogo (miles de requests, ~5s por lote de 20). Necesita `BGG_TOKEN` y `BGG_USERNAME` en `.env`.
- `collect_initial_data/search_new_game.py` — `--add <id o nombre>` suma un juego a `bgg_data.jsonl` y, si el slug verifica 200, a `cazagangas_data.jsonl`. Vive afuera de `bgg/` y `cazagangas/` porque orquesta las dos.
- `collect_initial_data/cazagangas/` — `cazagangas_common.py` (slug best-effort + verificación HTTP) y `check_cazagangas_links.py` (re-verifica con un HEAD real los links ya guardados; manual, con `--limit N`/`--refresh`).
- `verify_data_quality.py` — chequeos de integridad sobre los tres archivos (schema, `bgg_id` único, min ≤ max, rangos, listas, ranking repetido). No modifica nada. `ERROR` sale con exit code 1; `WARNING` con 0.

```bash
python3 01_data_understanding/verify_data_quality.py
python3 01_data_understanding/collect_initial_data/bgg/refresh_bgg_data.py --dry-run
```

## `bgg_data.jsonl`: campos crudos

Nombres y valores tal cual los trae BGG (la API y el dataset de Hugging Face llenan la misma forma): strings para los escalares, listas para los `link` y los polls. `0` en edad/duración/peso/puntaje es el "sin dato" de BGG, no un valor real. El orden de la tabla es el de cada línea (`BGG_CACHE_FIELDS` en `bgg_common.py`): primero los cortos, al final los largos.

| Campo | Qué es |
|---|---|
| `bgg_id` | id del juego en BGG; clave de join con los otros archivos |
| `yearpublished`, `minage` | año de publicación; edad mínima de la caja |
| `minplayers`, `maxplayers` | rango de jugadores **de la caja** |
| `playingtime`, `minplaytime`, `maxplaytime` | duración en minutos |
| `usersrated`, `average`, `bayesaverage` | cantidad de votos; puntaje promedio; puntaje ajustado (el del ranking) |
| `Board Game Rank` | posición en el ranking general |
| `averageweight`, `owned`, `wishing` | complejidad (1–5); cuántos lo tienen; cuántos lo desean |
| `boardgamedesigner`, `boardgamepublisher`, `boardgamemechanic`, `boardgamecategory`, `boardgamefamily` | listas de links de BGG (el primer publisher suele ser el original) |
| `name`, `alternate` | nombre principal y nombres alternativos (otros idiomas) |
| `thumbnail` | miniatura |
| `suggested_num_players`, `poll_summary` | votos Best/Recommended/Not Recommended por cantidad de jugadores; y el resumen ("Best with 3–4 players") ya calculado por BGG (solo la API lo trae) |
| `suggested_playerage`, `suggested_language_dependence` | votos de edad y de dependencia del idioma |
| `marketplacelistings` | publicaciones de venta recientes (solo la API, solo cuando se pide) |
| `description` | descripción de BGG (la más larga, va última) |

`bgg_collection.jsonl` y `cazagangas_data.jsonl` son más simples: ver `COLLECTION_FIELDS` en `bgg_common.py` y `cazagangas_common.py`.

## De dónde sale el dato de BGG

La API oficial (`xmlapi2`) exige un token Bearer desde que se aprobó la aplicación registrada; se pide por lotes de 20 ids, respetando el `Crawl-delay` de 5s del `robots.txt`. El bootstrap inicial usó un dataset público de terceros (`games_detailed_info2025.csv` de `mmpa/board_game_analysis`, Hugging Face), con un snapshot de BGG de **2025**; `refresh_bgg_data.py` lo va actualizando desde la API. Scrapear la página normal está descartado (challenge de Cloudflare, ver `DATA_PLAYBOOK.md`).

Quirk del dataset: varias columnas vienen como el repr de Python de una lista y se parsean con `ast.literal_eval` (nunca ejecuta código, solo literales).

## Correr todo el pipeline de 01 a mano

```bash
python3 01_data_understanding/collect_initial_data/bgg/refresh_bgg_data.py   # colección + datos que cambian
python3 02_data_preparation/integrate_data.py                                # ver 02_data_preparation/README.md
python3 02_data_preparation/construct_data.py
python3 02_data_preparation/select_data.py
```
