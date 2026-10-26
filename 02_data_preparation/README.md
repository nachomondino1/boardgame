# 02 — Data preparation

Dos pasos, en orden (ver `../DATA_PLAYBOOK.md`, diagrama de arquitectura):

- `integrate_data.py` — base `../data/01_data_understanding/mis_datos.jsonl` (lo que cargás a mano), suma `../data/01_data_understanding/universo_juegos.jsonl`/`../data/01_data_understanding/bgg_data.jsonl` por `bgg_id` (con `nombre` como fallback) y `../data/01_data_understanding/grupos.json`/`../data/01_data_understanding/cazagangas_data.jsonl` por nombre de juego, todo en un solo archivo (`../data/02_data_preparation/integrated_data.jsonl`, gitignored: es un intermedio del build, siempre regenerable desde archivos ya commiteados). Solo integra (join), no tipa ni calcula nada — eso es trabajo de `construct_data.py`. Las últimas cuatro fuentes son opcionales: si no existen, los campos que aportan quedan en `null` para todos (un juego sin match en BGG simplemente no tiene fila en `bgg_data.jsonl`, no es un error).
- `construct_data.py` — lee `../data/02_data_preparation/integrated_data.jsonl`, calcula las columnas derivadas (`duracion`, `modo`, `transportable`, `puntaje_ajust_bgg`, `precio_calidad` — ver el docstring de cada función para el criterio de cada una) y escribe `../docs/data/data.json` (dentro de `docs/` porque ahí vive el sitio que sirve GitHub Pages, ver `../05_deployment/README.md`). `transportable`/`bgg_url`/`link_cazagangas`/`grupo`/`cazagangas_status` ya vienen resueltos de `integrate_data.py`, acá solo pasan de largo. Ver `../README.md`, "Columnas calculadas", y `../DATA_PLAYBOOK.md` para el detalle.

La recolección cruda de cada fuente (BGG, Cazagangas, Bosque Lúdico) vive en `../01_data_understanding/` — ver el README de esa carpeta.

```bash
python3 02_data_preparation/integrate_data.py
python3 02_data_preparation/construct_data.py
```

`../.github/workflows/sync-data.yml` corre `01_data_understanding/collect_initial_data/search_new_game.py` y después estos dos, en ese orden, el día 1 de cada mes. El chequeo de links de Cazagangas (`check_cazagangas_links.py`) no corre acá — es manual, ver `../01_data_understanding/README.md`.
