# 01 — Data understanding

Acá vive **collect_initial_data**: recolectar, sin integrar nada todavía (eso es trabajo de `02_data_preparation/`, y 02 puede importar de 01, nunca al revés).

- `collect_initial_data/bgg/` — el universo de juegos completo. `collect_bgg_data.py` produce `bgg_data.jsonl`: identidad + Estado + todos los datos de BGG, en un solo archivo, `bgg_id` como primera columna. Ver más abajo.
- `collect_initial_data/bosque_ludico/` — **[EN UN FUTURO]** precio en [El Bosque Lúdico](https://www.elbosqueludico.com.ar). Los scripts existen y funcionan solos, pero nada los corre activamente ni integra su salida todavía — ver más abajo.

- `verify_data_quality.py` — chequeos de integridad sobre `bgg_data.jsonl` (bgg_id único, estado/modo válidos, min ≤ max, rangos numéricos, etc.), no modifica nada, solo reporta. Ver más abajo.

Describe data / Explore data (contar nulos, correlaciones, etc.) — en un futuro, no existen todavía.

## verify_data_quality.py: Verify Data Quality (CRISP-DM)

Corre standalone sobre `bgg_data.jsonl`, en cualquier momento (después de un `--add`, una corrección manual, o un refresh):

```bash
python3 01_data_understanding/verify_data_quality.py
```

Reporta cada problema como `ERROR` (sale con exit code 1: datos rotos que convendría arreglar — ej. `bgg_id` repetido, un min mayor que su max, un `estado` que no es ninguno de los válidos) o `WARNING` (exit code 0: algo para revisar pero no necesariamente un error — ej. un `modo` con una variante legacy, o dos juegos con el mismo nombre pero `bgg_id` distinto, que puede ser una edición/reimplementación legítima o un duplicado real cargado por error). No corrige nada solo: si encuentra un duplicado real, hay que sacarlo a mano (o pedírselo a Claude).

## collect_initial_data/bgg/: el universo de juegos + sus datos de BGG, en un único CSV

`bgg_data.jsonl` es a la vez el "universo de juegos" (qué juegos existen, con qué Estado) y sus datos de BGG (rating, duración, etc.) — reemplaza lo que antes eran tres piezas separadas (un ranking, un merge con la ludoteca, y un caché de enriquecimiento por id). `bgg_id` es la primera columna, para poder integrar fácil con lo que salga de otras fuentes el día que eso exista (ver "collect_initial_data/bosque_ludico/" abajo).

**Columnas propias — `collect_bgg_data.py` nunca las pisa** (se cargan a mano o con `--set-estado`) **vs. columnas de BGG — se refrescan en cada corrida** (vienen del dataset de terceros o, con `--mode api`, de BGG directo):

**El orden de las filas de esta tabla es el mismo orden real de los campos dentro de cada línea de `bgg_data.jsonl`** (ver `ALL_FIELDS` en `collect_bgg_data.py`): primero los campos cortos/estructurados (longitud parecida entre juegos), al final los de texto libre o longitud muy variable — así, al editar el `.jsonl` a mano, un campo largo en un juego puntual no hace más difícil ubicar los campos que lo preceden en otra fila.

| Columna | Tipo | Valores típicos | Descripción | Notas |
|---|---|---|---|---|
| `bgg_id` | propia | id numérico de BGG, o vacío | Identificador del juego en BGG. | Clave para cruzar con otras fuentes (ver `bosque_ludico/`). Vacío cuando el juego no tiene ficha en BGG. |
| `nombre` | propia | texto | Nombre del juego. | En inglés tal como figura en BGG, no traducido. |
| `estado` | propia | `Own`, `Prev. owned`, `Watchlist`, `Want to buy`, `Descartado` | En qué situación está el juego respecto a vos. | `Want to buy` es una shortlist *dentro* de la watchlist (juegos que se quieren comprar pronto, no solo "interesa"). `Descartado` está reservado (badge y CSS ya existen) pero sin uso real todavía. |
| `bgg_url` | propia | URL a `boardgamegeek.com/boardgame/<id>` | Link a la ficha de BGG. | Se arma sola al agregar el juego. |
| `modo` | propia | `Competitivo`, `Cooperativo`, `Equipos`, `Cooperativo y competitivo`, o vacío | Tipo de juego para el filtro "Tipo" de ¿Cuál comprar?. | Estos 4 son los que espera `docs/js/comprar.js`; hay alguna fila legacy con variantes sueltas (`Ambos`, `A confirmar`) que convendría normalizar en algún momento. Se completa a mano, nunca se infiere de BGG. |
| `anio` | BGG | año | Año de publicación. | — |
| `edad_min` | BGG | entero, o vacío | Edad mínima recomendada. | El dataset usa `0` como sentinel de "sin dato" en vez de vacío; el script ya lo trata como `null`. |
| `jug_min` / `jug_max` | BGG | rango de jugadores | Cantidad de jugadores que soporta el juego. | **Regla fija: siempre priorizar el rango "Community" de la ficha de BGG por sobre el de caja.** El dataset placeholder trae `minplayers`/`maxplayers` (caja, ej. 2–5), que no siempre coincide con lo que la comunidad recomienda (ej. Bomb Busters: caja 2–5, Community 3–5). Si se tiene o se puede chequear el dato de Community, usar ese; si no está disponible y se carga el de caja por default, **dejar nota explícita en `notas` aclarando que es el valor de caja, no el de Community** (para que quede claro que puede no reflejar lo recomendado). Un refresh futuro sin `--mode api` va a volver a pisar una corrección manual con el valor del dataset — la nota ayuda a detectarlo. |
| `jug_best_min` / `jug_best_max` | BGG | rango "mejor cantidad" | Con cuántos jugadores funciona mejor, según la comunidad. | Sale del poll `suggested_num_players` de BGG (voto "Best" con más votos), no es una columna editorial. |
| `duracion_min` / `duracion_max` | BGG | minutos | Duración de una partida. | Mismo sentinel `0` = sin dato que `edad_min`. |
| `complejidad` | BGG | 1.0–5.0 | Qué tan complejo es el juego ("peso"). | Promedio de "weight" de BGG. El dataset placeholder puede traer un promedio con pocos votos o desactualizado respecto a la ficha actual (mismo caso que `jug_min`/`jug_max`) — preferir el de la ficha de BGG si difiere notoriamente y el usuario lo pasa. |
| `puntaje_bgg` | BGG | 1.0–10.0 | Qué tan bien puntuado está en BGG. | Promedio BGG (`average`), no el Geek Rating/bayesaverage. |
| `reviews_bgg` | BGG | entero | Cuánta gente lo puntuó. | Cantidad de votos (`usersrated`). |
| `ranking_bgg` | BGG | entero | Posición en el ranking general de BGG. | "Board Game Rank". |
| `disenador` | BGG | nombre(s), separados por coma | Quién diseñó el juego. | — |
| `mecanicas` | BGG | array JSON de texto | Mecánicas de juego (ej. Deduction, Cooperative Game). | — |
| `categorias` | BGG | array JSON de texto | Categorías temáticas (ej. Animals, Spies / Secret Agents). | — |
| `mi_puntaje` | propia | 1–10, o vacío | Tu puntaje personal. | Opinión personal — nunca investigar ni inventar, se deja en blanco hasta que el usuario lo cargue. Casi siempre vacío: solo se completa para juegos `Own`/`Prev. owned` que ya jugaste. |
| `pros` / `cons` | propia | texto libre, o vacío | Lo que te gusta / no te gusta del juego. | Igual que `mi_puntaje`: a mano, casi siempre vacío. |
| `notas` | propia | texto libre | Comentarios sueltos que no entran en otra columna. | También el lugar donde se documentan discrepancias entre fuentes o correcciones manuales a columnas de BGG (ver ejemplo de `jug_min`/`complejidad` más abajo). |
| `descripcion` | BGG | texto (inglés) | Descripción oficial del juego, tal como figura en la ficha de BGG. | Es el texto de marketing/reglas de BGG, no un resumen propio — no confundir con `notas`, que es lo que vos escribís. El campo más largo y de longitud más variable de todos, por eso va último. |

**`bgg_data.jsonl` se commitea** (no es un derivado regenerable sin pérdida: las columnas propias —sobre todo `mi_puntaje`/`pros`/`cons`/`notas`— las cargaste vos a mano, igual que antes el Sheet).

### Cómo se usa, de tres formas

1. **Bootstrap** (la primera vez, cuando `bgg_data.jsonl` todavía no existe): arma el universo con el top N (1000 por default) del ranking de BGG + tus propios juegos. Esto último lo hace leyendo `ludoteca/mi_ludoteca.json` **una sola vez**, para taguear qué juegos son `Own`/`Prev. owned` (el resto queda `Watchlist`) — después de este bootstrap, `mi_ludoteca.json` ya se puede borrar, no se vuelve a leer nunca más (así quedó: el bootstrap para este repo ya corrió y la carpeta `ludoteca/` no existe más).
2. **Refresh** (default una vez que `bgg_data.jsonl` ya existe, sin `--add`): re-descarga el dataset de BGG y actualiza las columnas de BGG de los juegos que **ya** están en el archivo. Nunca agrega ni saca filas — es lo que corre el cron.
3. **Agregar un juego puntual** (`--add`): así es como se amplía el universo de acá en más — `bgg_data.jsonl` no se regenera solo con juegos nuevos, se le pide explícitamente.
   ```bash
   python3 01_data_understanding/collect_initial_data/bgg/collect_bgg_data.py --add 174430                    # por bgg_id (Gloomhaven)
   python3 01_data_understanding/collect_initial_data/bgg/collect_bgg_data.py --add "Wingspan" --estado Own    # por nombre, y le decís el Estado (default Watchlist)
   ```

### De dónde sale el dato de BGG

BGG cerró el acceso sin auth a `xmlapi2` (401 hasta que aprueben la aplicación registrada) y su página normal exige pasar un challenge de Cloudflare — scrapearla está descartado (ver `DATA_PLAYBOOK.md`, "Decisiones clave"). Mientras tanto (`--mode dummy`, default), se usa como placeholder un dataset público de terceros con un snapshot de BGG de **2025** (`games_detailed_info2025.csv` de `mmpa/board_game_analysis` en Hugging Face, ~28.000 juegos, sin auth): trae tanto el ranking completo (columna "Board Game Rank") como los detalles por juego en un solo archivo — un único dataset, no dos combinados como antes. Cubre ~98% del universo actual. Un juego que no esté en el snapshot simplemente no tiene match — sin error, sin dato inventado, esos campos quedan en `null`. `--mode api` reemplaza el placeholder por `xmlapi2/thing` oficial sin tocar nada más del pipeline en cuanto BGG apruebe la app.

Dos quirks del dataset que el script ya filtra, por si hace falta debuggear algo raro: algunos campos vienen como el repr de Python de una lista (p. ej. `boardgamedesigner`), se parsean con `ast.literal_eval` (nunca ejecuta código, solo literales); y `minplaytime`/`maxplaytime`/`minage` usan `0` como sentinel de "sin dato" en vez de dejar la celda vacía — el script lo trata como `null`, no como un valor real.

## collect_initial_data/bosque_ludico/: [EN UN FUTURO] precio en la tienda

**Pausado.** La idea es que algún día `bosque_data.csv` (mismo criterio: `bgg_id` como primera columna) se integre con `bgg_data.jsonl` haciendo match por nombre, en `02_data_preparation/`. Hoy esa integración no existe — nada corre estos scripts de forma activa ni los wire-ea al resto del pipeline, quedan documentados y funcionando por su cuenta para cuando se retome:

1. `resolve_bosque_links.py` — lee `bgg_data.jsonl`, filtra `estado == "Watchlist"`, y matchea cada nombre contra el listado completo de productos de la tienda (su `sitemap.xml.gz`, no `/search/`: ver el por qué en el docstring del script — bloqueado por `robots.txt`). Guarda `links.json` (gitignored): por juego, `bgg_id` + nombre + link a la tienda.
2. `collect_bosque_precios.py` — lee `links.json` y le pega a cada ficha de producto para sacar precio, disponibilidad y stock del momento. Guarda `bosque_data.json` (gitignored). Acepta `--limit N` para relevar de a tandas.

## Correr todo el pipeline de 01 a mano

```bash
python3 01_data_understanding/collect_initial_data/bgg/collect_bgg_data.py   # refresca bgg_data.jsonl (o --add para sumar un juego)
python3 02_data_preparation/construct_data.py            # ver 02_data_preparation/README.md
```

`.github/workflows/sync-data.yml` corre estos dos pasos el día 1 de cada mes.
