# 01 — Data understanding

Acá vive **collect_initial_data**: recolectar, sin integrar nada todavía (eso es trabajo de `02_data_preparation/`, y 02 puede importar de 01, nunca al revés).

- `collect_initial_data/bgg/bgg_common.py` — librería compartida (fetch del dataset/API, lectura/escritura de `universo_juegos.jsonl`/`bgg_data.jsonl`), no se corre directo.
- `collect_initial_data/bgg/initialize_bgg_data.py` — bootstrap único de `universo_juegos.jsonl` + `bgg_data.jsonl` (top N del ranking de BGG + ludoteca propia). Ya corrió una vez; no se vuelve a correr salvo que se quiera reiniciar el catálogo desde cero (ver `--force` en su docstring).
- `collect_initial_data/search_new_game.py` — con `--add <id o nombre>`, agrega un juego puntual a las cuatro fuentes a la vez (`universo_juegos.jsonl`, `bgg_data.jsonl`, `cazagangas_data.jsonl`/`link_cazagangas` si el slug verifica 200, fila stub en `mis_datos.jsonl`). Sin `--add`, completa en `bgg_data.jsonl` los `bgg_id` de `universo_juegos.jsonl` que todavía no tienen fila — nunca reescribe una fila que ya existe (reemplaza al viejo "refresh"). Ver más abajo.
- `collect_initial_data/bgg/modify_values.py` — edita a mano uno o más campos de un juego puntual ya cacheado en `bgg_data.jsonl` (ej. pisar `jug_min`/`jug_max` con el dato de Community en vez del de caja), sin tocar el resto del archivo.
- `collect_initial_data/bgg/extract_new_fields.py` — suma una columna nueva a todas las filas ya cacheadas de `bgg_data.jsonl`. Ninguno de los tres scripts de `bgg/` toca `mis_datos.jsonl` ni `cazagangas_data.jsonl` — eso es trabajo de `search_new_game.py`, que vive un nivel arriba porque orquesta ambas carpetas (ver más abajo).
- `collect_initial_data/cazagangas/cazagangas_common.py` — librería compartida (slug best-effort + verificación HTTP), usada por `check_cazagangas_links.py` y por `search_new_game.py --add`.
- `collect_initial_data/cazagangas/check_cazagangas_links.py` — re-verifica con un HEAD real los `link_cazagangas` ya cargados en `universo_juegos.jsonl` (no arma URLs nuevas — eso lo hace `search_new_game.py --add` al agregar un juego). Produce `../data/01_data_understanding/cazagangas_data.jsonl`. A diferencia de Bosque Lúdico, esta fuente sí se integra activamente (ver `02_data_preparation/integrate_data.py`) — lo único que no corre solo es el re-chequeo masivo en sí (manual, por volumen).
- `collect_initial_data/bosque_ludico/` — **[PAUSADO]** precio en [El Bosque Lúdico](https://www.elbosqueludico.com.ar). Los scripts existen y funcionan solos, pero nada los corre activamente ni integra su salida todavía — ver más abajo.

- `../data/01_data_understanding/mis_datos.jsonl` — 100% manual, lo cargás vos: Estado, modo, transportable, tu puntaje/pros/cons/notas. Ningún script de esta carpeta lo escribe.

- `verify_data_quality.py` — chequeos de integridad sobre `mis_datos.jsonl`, `universo_juegos.jsonl` y `bgg_data.jsonl` (bgg_id único, estado/modo válidos, min ≤ max, rangos numéricos, etc.), no modifica nada, solo reporta. Ver más abajo.

Describe data / Explore data (contar nulos, correlaciones, etc.) — en un futuro, no existen todavía.

## verify_data_quality.py: Verify Data Quality (CRISP-DM)

Corre standalone sobre los tres archivos de `data/01_data_understanding/`, en cualquier momento (después de un `search_new_game.py --add`, una edición a mano de `mis_datos.jsonl`, o un `search_new_game.py`/`modify_values.py`):

```bash
python3 01_data_understanding/verify_data_quality.py
```

Reporta cada problema como `ERROR` (sale con exit code 1: datos rotos que convendría arreglar — ej. `bgg_id` repetido, un min mayor que su max, un `estado` que no es ninguno de los válidos y tampoco está vacío) o `WARNING` (exit code 0: algo para revisar pero no necesariamente un error — ej. un `modo` con una variante legacy, dos juegos con el mismo nombre pero `bgg_id` distinto, un `bgg_id` en `universo_juegos.jsonl` que todavía no tiene fila en `bgg_data.jsonl`, un juego de `mis_datos.jsonl` que todavía no está en `universo_juegos.jsonl`, uno de `universo_juegos.jsonl` que todavía no está en `mis_datos.jsonl` — típicamente una fila stub recién creada por `search_new_game.py --add`, ver más abajo —, o un `estado` vacío esperando que lo completes a mano). No corrige nada solo: si encuentra un duplicado real, hay que sacarlo a mano (o pedírselo a Claude).

## Tres archivos, cada uno con una sola fuente de verdad

Ver `DATA_PLAYBOOK.md`, "Las columnas que no vienen de BGG viven en su propio archivo", para el porqué de esta separación:

- **`../data/01_data_understanding/universo_juegos.jsonl`** — catálogo de identidad, "qué juegos conoce este repo". `initialize_bgg_data.py` lo escribe en el bootstrap; `search_new_game.py --add` suma filas nuevas después, con `bgg_id`/`nombre`/`bgg_url` resueltos automático contra el dataset de BGG — `link_cazagangas` se carga a mano (la ficha real en cazagangas.com.ar/juego/...).
- **`../data/01_data_understanding/mis_datos.jsonl`** — tu opinión/estado sobre cada juego. 100% manual: la única excepción es `search_new_game.py --add`, que agrega una fila stub (`bgg_id`/`nombre` nomás) para un juego nuevo, sin completar ningún campo de opinión — el resto de los scripts de `01_data_understanding/` no lo tocan. Si se borra, se pierde tu trabajo — no es regenerable de ninguna fuente externa.
- **`../data/01_data_understanding/bgg_data.jsonl`** — caché de BGG (rating, duración, etc.), un juego por línea para cada `bgg_id` no vacío de `universo_juegos.jsonl`. Si se borra entero, `initialize_bgg_data.py --force` la reconstruye — pero en uso normal solo se le agregan filas (`search_new_game.py`) o se editan campos puntuales (`modify_values.py`/`extract_new_fields.py`), nunca se reescribe entera, así una edición a mano (ej. community players) no se pierde.

`bgg_id` es la primera columna de los tres, para poder integrar fácil (ver `02_data_preparation/integrate_data.py`); `mis_datos.jsonl` también guarda `nombre` (además de `bgg_id`) para que una fila se entienda sin tener que cruzar con `universo_juegos.jsonl`, y como respaldo de join para los pocos juegos sin `bgg_id`.

**El orden de las filas de cada tabla de abajo es el orden real de los campos dentro de cada línea** (`UNIVERSO_FIELDS`/`BGG_CACHE_FIELDS` en `bgg_common.py`, `MIS_DATOS_FIELDS` en `verify_data_quality.py`): primero los campos cortos/estructurados (longitud parecida entre juegos), al final los de texto libre o longitud muy variable — así, al editar un `.jsonl` a mano, un campo largo en un juego puntual no hace más difícil ubicar los campos que lo preceden en otra fila.

### `data/01_data_understanding/universo_juegos.jsonl`

| Columna | Valores típicos | Descripción | Notas |
|---|---|---|---|
| `bgg_id` | id numérico de BGG, o vacío | Identificador del juego en BGG. | Clave de join con `bgg_data.jsonl`, `mis_datos.jsonl` y otras fuentes (ver `bosque_ludico/`, `cazagangas/`). Vacío cuando el juego no tiene ficha en BGG. |
| `nombre` | texto | Nombre del juego. | En inglés tal como figura en BGG, no traducido. |
| `bgg_url` | URL a `boardgamegeek.com/boardgame/<id>` | Link a la ficha de BGG. | Se arma sola al agregar el juego (`search_new_game.py --add`). |
| `link_cazagangas` | URL a `cazagangas.com.ar/juego/<slug>`, o vacío | Link a la ficha del juego en Cazagangas. | **100% manual** — ni este script ni el frontend lo arman solos. Vacío hasta que lo cargás a mano; `check_cazagangas_links.py` lo verifica (no lo genera). |

### `data/01_data_understanding/mis_datos.jsonl`

| Columna | Valores típicos | Descripción | Notas |
|---|---|---|---|
| `bgg_id` | id numérico de BGG, o vacío | Mismo valor que en `universo_juegos.jsonl` — clave de join principal. | Vacío para juegos sin ficha en BGG (ahí `nombre` hace de respaldo). |
| `nombre` | texto | Nombre del juego. | Duplicado a propósito de `universo_juegos.jsonl`, para que la fila se lea sola y sirva de respaldo de join. |
| `estado` | `Own`, `Prev. owned`, `Watchlist`, `Want to buy`, `Descartado` | En qué situación está el juego respecto a vos. | `Want to buy` es una shortlist *dentro* de la watchlist (juegos que se quieren comprar pronto, no solo "interesa"). `Descartado` está reservado (badge y CSS ya existen) pero sin uso real todavía. |
| `modo` | `Competitivo`, `Cooperativo`, `Equipos`, `Cooperativo y competitivo`, o vacío | Tipo de juego para el filtro "Tipo" de ¿Cuál comprar?. | Estos 4 son los que espera `docs/js/comprar.js`; hay alguna fila legacy con variantes sueltas (`Ambos`, `A confirmar`) que convendría normalizar en algún momento. Se completa a mano, nunca se infiere de BGG. |
| `transportable` | `Sí`, `No`, `Más o menos`, o vacío | Si el juego entra en una mochila/bolso para llevarlo a otro lado, según el tamaño de la caja. | 100% manual — BGG no trackea esto, nunca se completa solo ni se investiga. Valores iniciales cargados desde una planilla personal del usuario (2026-10-26). |
| `mi_puntaje` | 1–10, o vacío | Tu puntaje personal. | Opinión personal — nunca investigar ni inventar, se deja en blanco hasta que el usuario lo cargue. Casi siempre vacío: solo se completa para juegos `Own`/`Prev. owned` que ya jugaste. |
| `pros` / `cons` | texto libre, o vacío | Lo que te gusta / no te gusta del juego. | Igual que `mi_puntaje`: a mano, casi siempre vacío. |
| `notas` | texto libre | Comentarios sueltos que no entran en otra columna. | También el lugar donde se documentan discrepancias entre fuentes o correcciones manuales a columnas de BGG (ver ejemplo de `jug_min`/`complejidad` abajo). |

### `data/01_data_understanding/bgg_data.jsonl`

| Columna | Valores típicos | Descripción | Notas |
|---|---|---|---|
| `bgg_id` | id numérico de BGG | Clave de join con `universo_juegos.jsonl`/`mis_datos.jsonl`. | Toda fila de este archivo tiene un `bgg_id` no vacío (si no hay match en BGG, directamente no hay fila). |
| `anio` | año | Año de publicación. | — |
| `edad_min` | entero, o vacío | Edad mínima recomendada. | El dataset usa `0` como sentinel de "sin dato" en vez de vacío; el script ya lo trata como `null`. |
| `jug_min` / `jug_max` | rango de jugadores | Cantidad de jugadores que soporta el juego. | **Regla fija: siempre priorizar el rango "Community" de la ficha de BGG por sobre el de caja.** El dataset placeholder trae `minplayers`/`maxplayers` (caja, ej. 2–5), que no siempre coincide con lo que la comunidad recomienda (ej. Bomb Busters: caja 2–5, Community 3–5). Si se tiene o se puede chequear el dato de Community, usar ese: `modify_values.py <bgg_id> jug_min=X jug_max=Y`, que no se pisa en corridas futuras (`search_new_game.py`/`extract_new_fields.py` nunca reescriben una fila ya existente a menos que se pida explícito). Si no está disponible y se carga el de caja por default, **dejar nota explícita en `mis_datos.jsonl::notas` aclarando que es el valor de caja, no el de Community**. |
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

**`universo_juegos.jsonl` y `mis_datos.jsonl` se commitean porque no son regenerables sin pérdida** (`link_cazagangas`/`mi_puntaje`/`pros`/`cons`/`notas`, cargadas a mano, igual que antes el Sheet). **`bgg_data.jsonl` también se commitea** (para no depender de la red en cada build — el sitio lee `docs/data/data.json`, no esto directo); a diferencia de los otros dos, una fila sin cargar todavía es 100% regenerable (si falta, `search_new_game.py` la completa) — pero a diferencia de cómo funcionaba antes, una fila que **ya existe** nunca se reescribe sola, así que una corrección manual (`modify_values.py`) es permanente.

### Los cuatro scripts de recolección: cuándo usar cada uno

1. **`initialize_bgg_data.py`** — bootstrap único (la primera vez, cuando `universo_juegos.jsonl` todavía no existe): arma el catálogo con el top N (1000 por default) del ranking de BGG + tus propios juegos. Esto último lo hace leyendo `ludoteca/mi_ludoteca.json` **una sola vez**, solo identidad — después de este bootstrap, `mi_ludoteca.json` ya se puede borrar, no se vuelve a leer nunca más (así quedó: el bootstrap para este repo ya corrió y la carpeta `ludoteca/` no existe más). No asigna ningún estado: eso lo cargás vos en `mis_datos.jsonl` aparte. **No correr de nuevo** salvo que se quiera reiniciar el catálogo desde cero a propósito (`--force`) — reescribe `bgg_data.jsonl` entero contra el dataset de origen, perdiendo cualquier edición manual.
2. **`search_new_game.py`** — el uso normal, de ahora en más. Sin `--add`: compara los `bgg_id` de `universo_juegos.jsonl` contra los que ya están en `bgg_data.jsonl` y agrega los que falten (nunca reescribe una fila existente) — es lo que corre el cron. Con `--add <id o nombre>`: resuelve `bgg_id`/`nombre`/`bgg_url` automático contra el dataset y agrega la fila a `universo_juegos.jsonl`, completa su fila en `bgg_data.jsonl`, **arma un slug best-effort para Cazagangas y lo verifica con un HEAD real** (`https://www.cazagangas.com.ar/juego/<slug-del-nombre>`) — si da 200, carga `link_cazagangas` y la fila en `cazagangas_data.jsonl` solo; si no, deja `link_cazagangas` vacío para cargarlo a mano (el juego puede existir en la tienda con otro slug) — y **agrega una fila stub a `mis_datos.jsonl`** (`bgg_id`/`nombre` nomás, el resto vacío: `estado`/`modo`/`mi_puntaje`/etc. siguen siendo 100% tu criterio, el script nunca los completa). `verify_data_quality.py` marca esas filas stub como `WARNING` ("estado vacío, pendiente de completar a mano"), no como error.
   ```bash
   python3 01_data_understanding/collect_initial_data/search_new_game.py --add 174430      # por bgg_id (Gloomhaven)
   python3 01_data_understanding/collect_initial_data/search_new_game.py --add "Wingspan"   # por nombre
   ```
   El chequeo de Cazagangas y el stub de `mis_datos.jsonl` solo pasan con `--add` (un juego a la vez) — la corrida sin argumentos (la que corre el cron) no recorre red contra Cazagangas para todo el catálogo; eso sigue siendo `check_cazagangas_links.py --limit N`, manual.
3. **`modify_values.py`** — editar a mano uno o más campos de un juego ya cacheado (ej. pisar `jug_min`/`jug_max` con el dato de Community), sin tocar el resto de la fila ni del archivo:
   ```bash
   python3 01_data_understanding/collect_initial_data/bgg/modify_values.py 409750 jug_min=2 jug_max=4
   ```
4. **`extract_new_fields.py`** — sumar una columna nueva a todas las filas ya cacheadas (después de declararla en `BGG_CACHE_FIELDS` en `bgg_common.py` y mapearla en `dataset_row_to_attributes`/`fetch_api_attributes`). Saltea las filas que ya tienen algo cargado en ese campo salvo `--force`.

### De dónde sale el dato de BGG

BGG cerró el acceso sin auth a `xmlapi2` (401 hasta que aprueben la aplicación registrada) y su página normal exige pasar un challenge de Cloudflare — scrapearla está descartado (ver `DATA_PLAYBOOK.md`, "Decisiones clave"). Mientras tanto (`--mode dummy`, default), se usa como placeholder un dataset público de terceros con un snapshot de BGG de **2025** (`games_detailed_info2025.csv` de `mmpa/board_game_analysis` en Hugging Face, ~28.000 juegos, sin auth): trae tanto el ranking completo (columna "Board Game Rank") como los detalles por juego en un solo archivo — un único dataset, no dos combinados como antes. Cubre ~98% del universo actual. Un juego que no esté en el snapshot simplemente no tiene match — sin error, sin dato inventado, esa fila directamente no aparece en `bgg_data.jsonl`. `--mode api` reemplaza el placeholder por `xmlapi2/thing` oficial sin tocar nada más del pipeline en cuanto BGG apruebe la app.

Dos quirks del dataset que el script ya filtra, por si hace falta debuggear algo raro: algunos campos vienen como el repr de Python de una lista (p. ej. `boardgamedesigner`), se parsean con `ast.literal_eval` (nunca ejecuta código, solo literales); y `minplaytime`/`maxplaytime`/`minage` usan `0` como sentinel de "sin dato" en vez de dejar la celda vacía — el script lo trata como `null`, no como un valor real.

## collect_initial_data/bosque_ludico/: [PAUSADO] precio en la tienda

**Pausado.** La idea es que algún día `bosque_data.csv` (mismo criterio: `bgg_id` como primera columna) se integre en `02_data_preparation/integrate_data.py`, mismo patrón que `cazagangas_data.jsonl`. Hoy esa integración no existe — nada corre estos scripts de forma activa ni los wire-ea al resto del pipeline, quedan documentados y funcionando por su cuenta para cuando se retome:

1. `resolve_bosque_links.py` — lee `mis_datos.jsonl`, filtra `estado == "Watchlist"`, y matchea cada nombre contra el listado completo de productos de la tienda (su `sitemap.xml.gz`, no `/search/`: ver el por qué en el docstring del script — bloqueado por `robots.txt`). Guarda `links.json` (gitignored): por juego, `bgg_id` + nombre + link a la tienda.
2. `collect_bosque_precios.py` — lee `links.json` y le pega a cada ficha de producto para sacar precio, disponibilidad y stock del momento. Guarda `bosque_data.json` (gitignored). Acepta `--limit N` para relevar de a tandas.

## Correr todo el pipeline de 01 a mano

```bash
python3 01_data_understanding/collect_initial_data/search_new_game.py   # completa bgg_data.jsonl con lo que falte (o --add para sumar un juego nuevo)
python3 02_data_preparation/integrate_data.py             # ver 02_data_preparation/README.md
python3 02_data_preparation/construct_data.py              # ver 02_data_preparation/README.md
```

`.github/workflows/sync-data.yml` corre estos tres pasos el día 1 de cada mes.
