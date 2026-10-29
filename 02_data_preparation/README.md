# 02 — Data preparation

Dos pasos, en orden (ver `../DATA_PLAYBOOK.md`, diagrama de arquitectura):

- `integrate_data.py` — base `../data/01_data_understanding/bgg_data.jsonl` (EL catálogo completo, crudo), suma `bgg_collection.jsonl` (tu colección en BGG) y `cazagangas_data.jsonl` por `bgg_id`, todo en un solo archivo (`../data/02_data_preparation/integrated_data.jsonl`, gitignored: es un intermedio del build, siempre regenerable). Solo integra (join), no tipa ni calcula nada — eso es trabajo de `construct_data.py`. Las dos últimas fuentes son opcionales: si no existen, los campos que aportan quedan en `null`.
- `construct_data.py` — lee `../data/02_data_preparation/integrated_data.jsonl`, construye todo lo que usa el sitio a partir de los campos crudos de BGG (`nombre`, `bgg_url`, `estado` y `mi_puntaje` desde tu colección, `grupo` desde las familias de BGG, `jug_min/max` y `jug_best_*` desde los polls, `duracion`, `modo`, `puntaje_ajust_bgg`, `precio_calidad`, `publisher_principal`, `dependencia_idioma`, `edad_comunidad`, `precio_ref_usd` — ver el docstring de cada función) y escribe `../docs/data/data.json` (dentro de `docs/` porque ahí vive el sitio que sirve GitHub Pages, ver `../05_deployment/README.md`). Ver `../README.md`, "Columnas calculadas", y `../DATA_PLAYBOOK.md` para el detalle.

La recolección cruda de cada fuente (BGG, Cazagangas, Bosque Lúdico) vive en `../01_data_understanding/` — ver el README de esa carpeta.

```bash
python3 02_data_preparation/integrate_data.py
python3 02_data_preparation/construct_data.py
```

`../.github/workflows/sync-data.yml` corre `01_data_understanding/collect_initial_data/search_new_game.py` y después estos dos, en ese orden, el día 1 de cada mes. El chequeo de links de Cazagangas (`check_cazagangas_links.py`) no corre acá — es manual, ver `../01_data_understanding/README.md`.
