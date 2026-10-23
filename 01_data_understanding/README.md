# 01 — Data understanding

Acá vive **collect_initial_data**: recolectar, sin integrar nada todavía (eso es trabajo de `02_data_preparation/`, y 02 puede importar de 01, nunca al revés).

- `bgg/` — el universo de juegos completo. `collect_bgg_data.py` produce `bgg_data.csv`: identidad + Estado + todos los datos de BGG, en un solo archivo, `bgg_id` como primera columna. Ver más abajo.
- `bosque_ludico/` — **[EN UN FUTURO]** precio en [El Bosque Lúdico](https://www.elbosqueludico.com.ar). Los scripts existen y funcionan solos, pero nada los corre activamente ni integra su salida todavía — ver más abajo.

Describe data / Explore data (contar nulos, correlaciones, etc.) — en un futuro, no existen todavía.

## bgg/: el universo de juegos + sus datos de BGG, en un único CSV

`bgg_data.csv` es a la vez el "universo de juegos" (qué juegos existen, con qué Estado) y sus datos de BGG (rating, duración, etc.) — reemplaza lo que antes eran tres piezas separadas (un ranking, un merge con la ludoteca, y un caché de enriquecimiento por id). `bgg_id` es la primera columna, para poder integrar fácil con lo que salga de otras fuentes el día que eso exista (ver "bosque_ludico/" abajo).

**Columnas propias — `collect_bgg_data.py` nunca las pisa:** `bgg_id`, `nombre`, `estado` (`Own`/`Prev. owned`/`Watchlist`), `bgg_url`, `modo`, `mi_puntaje`, `pros`, `cons`, `youtube`, `notas`.
**Columnas de BGG — se refrescan en cada corrida:** `anio`, `descripcion`, `disenador`, `edad_min`, `jug_min`/`jug_max`, `jug_best_min`/`jug_best_max`, `duracion_min`/`duracion_max`, `complejidad`, `puntaje_bgg`, `reviews_bgg`, `ranking_bgg`, `mecanicas`, `categorias` (estas dos últimas, listas separadas por `|`).

**`bgg_data.csv` se commitea** (no es un derivado regenerable sin pérdida: las columnas propias —sobre todo `mi_puntaje`/`pros`/`cons`/`notas`— las cargaste vos a mano, igual que antes el Sheet).

### Cómo se usa, de tres formas

1. **Bootstrap** (la primera vez, cuando `bgg_data.csv` todavía no existe): arma el universo con el top N (1000 por default) del ranking de BGG + tus propios juegos. Esto último lo hace leyendo `ludoteca/mi_ludoteca.json` **una sola vez**, para taguear qué juegos son `Own`/`Prev. owned` (el resto queda `Watchlist`) — después de este bootstrap, `mi_ludoteca.json` ya se puede borrar, no se vuelve a leer nunca más (así quedó: el bootstrap para este repo ya corrió y la carpeta `ludoteca/` no existe más).
2. **Refresh** (default una vez que `bgg_data.csv` ya existe, sin `--add`): re-descarga el dataset de BGG y actualiza las columnas de BGG de los juegos que **ya** están en el archivo. Nunca agrega ni saca filas — es lo que corre el cron.
3. **Agregar un juego puntual** (`--add`): así es como se amplía el universo de acá en más — `bgg_data.csv` no se regenera solo con juegos nuevos, se le pide explícitamente.
   ```bash
   python3 01_data_understanding/bgg/collect_bgg_data.py --add 174430                    # por bgg_id (Gloomhaven)
   python3 01_data_understanding/bgg/collect_bgg_data.py --add "Wingspan" --estado Own    # por nombre, y le decís el Estado (default Watchlist)
   ```

### De dónde sale el dato de BGG

BGG cerró el acceso sin auth a `xmlapi2` (401 hasta que aprueben la aplicación registrada) y su página normal exige pasar un challenge de Cloudflare — scrapearla está descartado (ver `DATA_PLAYBOOK.md`, "Decisiones clave"). Mientras tanto (`--mode dummy`, default), se usa como placeholder un dataset público de terceros con un snapshot de BGG de **2025** (`games_detailed_info2025.csv` de `mmpa/board_game_analysis` en Hugging Face, ~28.000 juegos, sin auth): trae tanto el ranking completo (columna "Board Game Rank") como los detalles por juego en un solo archivo — un único dataset, no dos combinados como antes. Cubre ~98% del universo actual. Un juego que no esté en el snapshot simplemente no tiene match — sin error, sin dato inventado, esos campos quedan en `null`. `--mode api` reemplaza el placeholder por `xmlapi2/thing` oficial sin tocar nada más del pipeline en cuanto BGG apruebe la app.

Dos quirks del dataset que el script ya filtra, por si hace falta debuggear algo raro: algunos campos vienen como el repr de Python de una lista (p. ej. `boardgamedesigner`), se parsean con `ast.literal_eval` (nunca ejecuta código, solo literales); y `minplaytime`/`maxplaytime`/`minage` usan `0` como sentinel de "sin dato" en vez de dejar la celda vacía — el script lo trata como `null`, no como un valor real.

## bosque_ludico/: [EN UN FUTURO] precio en la tienda

**Pausado.** La idea es que algún día `bosque_data.csv` (mismo criterio: `bgg_id` como primera columna) se integre con `bgg_data.csv` haciendo match por nombre, en `02_data_preparation/`. Hoy esa integración no existe — nada corre estos scripts de forma activa ni los wire-ea al resto del pipeline, quedan documentados y funcionando por su cuenta para cuando se retome:

1. `resolve_bosque_links.py` — lee `bgg_data.csv`, filtra `estado == "Watchlist"`, y matchea cada nombre contra el listado completo de productos de la tienda (su `sitemap.xml.gz`, no `/search/`: ver el por qué en el docstring del script — bloqueado por `robots.txt`). Guarda `links.json` (gitignored): por juego, `bgg_id` + nombre + link a la tienda.
2. `collect_bosque_precios.py` — lee `links.json` y le pega a cada ficha de producto para sacar precio, disponibilidad y stock del momento. Guarda `bosque_data.json` (gitignored). Acepta `--limit N` para relevar de a tandas.

## Correr todo el pipeline de 01 a mano

```bash
python3 01_data_understanding/bgg/collect_bgg_data.py   # refresca bgg_data.csv (o --add para sumar un juego)
python3 02_data_preparation/construct_data.py            # ver 02_data_preparation/README.md
```

`.github/workflows/sync-data.yml` corre estos dos pasos el día 1 de cada mes.
