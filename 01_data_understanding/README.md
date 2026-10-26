# 01 — Data understanding

Acá vive **collect_initial_data**: recolectar, sin integrar nada todavía (eso es trabajo de `02_data_preparation/`, y 02 puede importar de 01, nunca al revés).

- `collect_initial_data/collect_bgg_data.py` — produce dos archivos de `../data/`: `mis_datos.jsonl` (EL universo de juegos: identidad + Estado + todo lo que cargás a mano) y `bgg_data.jsonl` (caché 100% regenerable de datos de BGG, join por `bgg_id`). Ver más abajo.
- `collect_initial_data/cazagangas/check_cazagangas_links.py` — chequea si el link a la ficha de cada juego en [Cazagangas](https://www.cazagangas.com.ar) existe de verdad (código HTTP real, no un slug armado a ciegas). Produce `../data/cazagangas_data.jsonl`. A diferencia de Bosque Lúdico, esta fuente sí se integra activamente (ver `02_data_preparation/integrate_data.py`) — lo único que no corre solo es el chequeo de red en sí (manual, por volumen).
- `collect_initial_data/bosque_ludico/` — **[PAUSADO]** precio en [El Bosque Lúdico](https://www.elbosqueludico.com.ar). Los scripts existen y funcionan solos, pero nada los corre activamente ni integra su salida todavía — ver más abajo.

- `verify_data_quality.py` — chequeos de integridad sobre `mis_datos.jsonl` y `bgg_data.jsonl` (bgg_id único, estado/modo válidos, min ≤ max, rangos numéricos, etc.), no modifica nada, solo reporta. Ver más abajo.

Describe data / Explore data (contar nulos, correlaciones, etc.) — en un futuro, no existen todavía.

## verify_data_quality.py: Verify Data Quality (CRISP-DM)

Corre standalone sobre `mis_datos.jsonl` + `bgg_data.jsonl`, en cualquier momento (después de un `--add`, una corrección manual, o un refresh):

```bash
python3 01_data_understanding/verify_data_quality.py
```

Reporta cada problema como `ERROR` (sale con exit code 1: datos rotos que convendría arreglar — ej. `bgg_id` repetido, un min mayor que su max, un `estado` que no es ninguno de los válidos) o `WARNING` (exit code 0: algo para revisar pero no necesariamente un error — ej. un `modo` con una variante legacy, dos juegos con el mismo nombre pero `bgg_id` distinto, o un `bgg_id` en `mis_datos.jsonl` que todavía no tiene fila en `bgg_data.jsonl`). No corrige nada solo: si encuentra un duplicado real, hay que sacarlo a mano (o pedírselo a Claude).

## collect_initial_data/collect_bgg_data.py: el universo de juegos (`mis_datos.jsonl`) + su caché de BGG (`bgg_data.jsonl`)

Dos archivos, cada uno con una sola fuente de verdad (ver `DATA_PLAYBOOK.md`, "Las columnas que no vienen de BGG viven en su propio archivo"):

- **`../data/mis_datos.jsonl`** — identidad + Estado + todo lo que cargás a mano. `collect_bgg_data.py` **nunca** lo pisa salvo que se lo pidas explícito (`--add`, `--set-estado`): un refresh normal ni lo abre para escribir. Si se borra, se pierde tu trabajo — no es regenerable de ninguna fuente externa.
- **`../data/bgg_data.jsonl`** — caché de BGG (rating, duración, etc.), un juego por línea para cada `bgg_id` no vacío de `mis_datos.jsonl`. Se reescribe entero en cada refresh. Si se borra, el próximo refresh la reconstruye sola — no se pierde nada.

`bgg_id` es la primera columna de ambos, para poder integrar fácil (ver `02_data_preparation/integrate_data.py`).

**El orden de las filas de cada tabla de abajo es el orden real de los campos dentro de cada línea** (`MIS_DATOS_FIELDS`/`BGG_CACHE_FIELDS` en `collect_bgg_data.py`): primero los campos cortos/estructurados (longitud parecida entre juegos), al final los de texto libre o longitud muy variable — así, al editar un `.jsonl` a mano, un campo largo en un juego puntual no hace más difícil ubicar los campos que lo preceden en otra fila.

### `data/mis_datos.jsonl`

| Columna | Valores típicos | Descripción | Notas |
|---|---|---|---|
| `bgg_id` | id numérico de BGG, o vacío | Identificador del juego en BGG. | Clave de join con `bgg_data.jsonl` y con otras fuentes (ver `bosque_ludico/`, `cazagangas/`). Vacío cuando el juego no tiene ficha en BGG. |
| `nombre` | texto | Nombre del juego. | En inglés tal como figura en BGG, no traducido. |
| `estado` | `Own`, `Prev. owned`, `Watchlist`, `Want to buy`, `Descartado` | En qué situación está el juego respecto a vos. | `Want to buy` es una shortlist *dentro* de la watchlist (juegos que se quieren comprar pronto, no solo "interesa"). `Descartado` está reservado (badge y CSS ya existen) pero sin uso real todavía. |
| `bgg_url` | URL a `boardgamegeek.com/boardgame/<id>` | Link a la ficha de BGG. | Se arma sola al agregar el juego. |
| `modo` | `Competitivo`, `Cooperativo`, `Equipos`, `Cooperativo y competitivo`, o vacío | Tipo de juego para el filtro "Tipo" de ¿Cuál comprar?. | Estos 4 son los que espera `docs/js/comprar.js`; hay alguna fila legacy con variantes sueltas (`Ambos`, `A confirmar`) que convendría normalizar en algún momento. Se completa a mano, nunca se infiere de BGG. |
| `transportable` | `Sí`, `No`, `Más o menos`, o vacío | Si el juego entra en una mochila/bolso para llevarlo a otro lado, según el tamaño de la caja. | 100% manual — BGG no trackea esto, nunca se completa solo ni se investiga. Valores iniciales cargados desde una planilla personal del usuario (2026-10-26). |
| `mi_puntaje` | 1–10, o vacío | Tu puntaje personal. | Opinión personal — nunca investigar ni inventar, se deja en blanco hasta que el usuario lo cargue. Casi siempre vacío: solo se completa para juegos `Own`/`Prev. owned` que ya jugaste. |
| `pros` / `cons` | texto libre, o vacío | Lo que te gusta / no te gusta del juego. | Igual que `mi_puntaje`: a mano, casi siempre vacío. |
| `notas` | texto libre | Comentarios sueltos que no entran en otra columna. | También el lugar donde se documentan discrepancias entre fuentes o correcciones manuales a columnas de BGG (ver ejemplo de `jug_min`/`complejidad` abajo). |

### `data/bgg_data.jsonl`

| Columna | Valores típicos | Descripción | Notas |
|---|---|---|---|
| `bgg_id` | id numérico de BGG | Clave de join con `mis_datos.jsonl`. | Toda fila de este archivo tiene un `bgg_id` no vacío (si no hay match en BGG, directamente no hay fila). |
| `anio` | año | Año de publicación. | — |
| `edad_min` | entero, o vacío | Edad mínima recomendada. | El dataset usa `0` como sentinel de "sin dato" en vez de vacío; el script ya lo trata como `null`. |
| `jug_min` / `jug_max` | rango de jugadores | Cantidad de jugadores que soporta el juego. | **Regla fija: siempre priorizar el rango "Community" de la ficha de BGG por sobre el de caja.** El dataset placeholder trae `minplayers`/`maxplayers` (caja, ej. 2–5), que no siempre coincide con lo que la comunidad recomienda (ej. Bomb Busters: caja 2–5, Community 3–5). Si se tiene o se puede chequear el dato de Community, usar ese; si no está disponible y se carga el de caja por default, **dejar nota explícita en `mis_datos.jsonl::notas` aclarando que es el valor de caja, no el de Community** (para que quede claro que puede no reflejar lo recomendado). Un refresh futuro sin `--mode api` va a volver a pisar una corrección manual con el valor del dataset — la nota ayuda a detectarlo. |
| `jug_best_min` / `jug_best_max` | rango "mejor cantidad" | Con cuántos jugadores funciona mejor, según la comunidad. | Sale del poll `suggested_num_players` de BGG (voto "Best" con más votos), no es una columna editorial. |
| `duracion_min` / `duracion_max` | minutos | Duración de una partida. | Mismo sentinel `0` = sin dato que `edad_min`. |
| `complejidad` | 1.0–5.0 | Qué tan complejo es el juego ("peso"). | Promedio de "weight" de BGG. El dataset placeholder puede traer un promedio con pocos votos o desactualizado respecto a la ficha actual (mismo caso que `jug_min`/`jug_max`) — preferir el de la ficha de BGG si difiere notoriamente y el usuario lo pasa. |
| `puntaje_bgg` | 1.0–10.0 | Qué tan bien puntuado está en BGG. | Promedio BGG (`average`), no el Geek Rating/bayesaverage. |
| `reviews_bgg` | entero | Cuánta gente lo puntuó. | Cantidad de votos (`usersrated`). |
| `ranking_bgg` | entero | Posición en el ranking general de BGG. | "Board Game Rank". |
| `disenador` | nombre(s), separados por coma | Quién diseñó el juego. | — |
| `mecanicas` | array JSON de texto | Mecánicas de juego (ej. Deduction, Cooperative Game). | — |
| `categorias` | array JSON de texto | Categorías temáticas (ej. Animals, Spies / Secret Agents). | — |
| `descripcion` | texto (inglés) | Descripción oficial del juego, tal como figura en la ficha de BGG. | Es el texto de marketing/reglas de BGG, no un resumen propio — no confundir con `mis_datos.jsonl::notas`, que es lo que vos escribís. El campo más largo y de longitud más variable de todos, por eso va último. |

**`mis_datos.jsonl` se commitea porque no es regenerable sin pérdida** (sobre todo `mi_puntaje`/`pros`/`cons`/`notas`, cargadas a mano, igual que antes el Sheet). **`bgg_data.jsonl` también se commitea** (para no depender de la red en cada build — el sitio lee `docs/data/data.json`, no esto directo), pero a diferencia de `mis_datos.jsonl` sí es 100% regenerable: `collect_bgg_data.py` la reconstruye entera a partir de los `bgg_id` de `mis_datos.jsonl`.

### Cómo se usa, de cuatro formas

1. **Bootstrap** (la primera vez, cuando `mis_datos.jsonl` todavía no existe): arma el universo con el top N (1000 por default) del ranking de BGG + tus propios juegos. Esto último lo hace leyendo `ludoteca/mi_ludoteca.json` **una sola vez**, para taguear qué juegos son `Own`/`Prev. owned` (el resto queda `Watchlist`) — después de este bootstrap, `mi_ludoteca.json` ya se puede borrar, no se vuelve a leer nunca más (así quedó: el bootstrap para este repo ya corrió y la carpeta `ludoteca/` no existe más).
2. **Refresh** (default una vez que `mis_datos.jsonl` ya existe, sin `--add`/`--set-estado`): re-descarga el dataset de BGG y reconstruye `bgg_data.jsonl` entero a partir de los `bgg_id` que ya están en `mis_datos.jsonl`. Nunca toca `mis_datos.jsonl` — es lo que corre el cron.
3. **Agregar un juego puntual** (`--add`): así es como se amplía el universo de acá en más — `mis_datos.jsonl` no se regenera solo con juegos nuevos, se le pide explícitamente.
   ```bash
   python3 01_data_understanding/collect_initial_data/collect_bgg_data.py --add 174430                    # por bgg_id (Gloomhaven)
   python3 01_data_understanding/collect_initial_data/collect_bgg_data.py --add "Wingspan" --estado Own    # por nombre, y le decís el Estado (default Watchlist)
   ```
4. **Cambiar el estado de un juego ya cargado** (`--set-estado`): edita `mis_datos.jsonl` nomás, no toca ni descarga nada de BGG.
   ```bash
   python3 01_data_understanding/collect_initial_data/collect_bgg_data.py --set-estado "Sky Team" "Want to buy"
   ```

### De dónde sale el dato de BGG

BGG cerró el acceso sin auth a `xmlapi2` (401 hasta que aprueben la aplicación registrada) y su página normal exige pasar un challenge de Cloudflare — scrapearla está descartado (ver `DATA_PLAYBOOK.md`, "Decisiones clave"). Mientras tanto (`--mode dummy`, default), se usa como placeholder un dataset público de terceros con un snapshot de BGG de **2025** (`games_detailed_info2025.csv` de `mmpa/board_game_analysis` en Hugging Face, ~28.000 juegos, sin auth): trae tanto el ranking completo (columna "Board Game Rank") como los detalles por juego en un solo archivo — un único dataset, no dos combinados como antes. Cubre ~98% del universo actual. Un juego que no esté en el snapshot simplemente no tiene match — sin error, sin dato inventado, esa fila directamente no aparece en `bgg_data.jsonl`. `--mode api` reemplaza el placeholder por `xmlapi2/thing` oficial sin tocar nada más del pipeline en cuanto BGG apruebe la app.

Dos quirks del dataset que el script ya filtra, por si hace falta debuggear algo raro: algunos campos vienen como el repr de Python de una lista (p. ej. `boardgamedesigner`), se parsean con `ast.literal_eval` (nunca ejecuta código, solo literales); y `minplaytime`/`maxplaytime`/`minage` usan `0` como sentinel de "sin dato" en vez de dejar la celda vacía — el script lo trata como `null`, no como un valor real.

## collect_initial_data/bosque_ludico/: [PAUSADO] precio en la tienda

**Pausado.** La idea es que algún día `bosque_data.csv` (mismo criterio: `bgg_id` como primera columna) se integre en `02_data_preparation/integrate_data.py`, mismo patrón que `cazagangas_data.jsonl`. Hoy esa integración no existe — nada corre estos scripts de forma activa ni los wire-ea al resto del pipeline, quedan documentados y funcionando por su cuenta para cuando se retome:

1. `resolve_bosque_links.py` — lee `mis_datos.jsonl`, filtra `estado == "Watchlist"`, y matchea cada nombre contra el listado completo de productos de la tienda (su `sitemap.xml.gz`, no `/search/`: ver el por qué en el docstring del script — bloqueado por `robots.txt`). Guarda `links.json` (gitignored): por juego, `bgg_id` + nombre + link a la tienda.
2. `collect_bosque_precios.py` — lee `links.json` y le pega a cada ficha de producto para sacar precio, disponibilidad y stock del momento. Guarda `bosque_data.json` (gitignored). Acepta `--limit N` para relevar de a tandas.

## Correr todo el pipeline de 01 a mano

```bash
python3 01_data_understanding/collect_initial_data/collect_bgg_data.py   # refresca mis_datos.jsonl/bgg_data.jsonl (o --add para sumar un juego)
python3 02_data_preparation/integrate_data.py             # ver 02_data_preparation/README.md
python3 02_data_preparation/construct_data.py              # ver 02_data_preparation/README.md
```

`.github/workflows/sync-data.yml` corre estos tres pasos el día 1 de cada mes.
