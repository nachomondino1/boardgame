# 02 — Data preparation

Hoy un solo paso real (la integración con una segunda fuente es trabajo futuro — ver `../01_data_understanding/collect_initial_data/bosque_ludico/`):

- **[EN UN FUTURO] Integración** — cuando `bosque_data.csv` exista, mergear `../01_data_understanding/collect_initial_data/bgg/bgg_data.jsonl` con `bosque_data.csv` por nombre de juego. No existe todavía.
- `construct_data.py` — lee `../01_data_understanding/collect_initial_data/bgg/bgg_data.jsonl` directo (hoy es la única fuente — no hay nada que integrar), calcula las columnas derivadas (`duracion`, `modo`, `transportable`, `puntaje_ajust_bgg`, `precio_calidad` — ver el docstring de cada función para el criterio de cada una) y escribe `../docs/data/data.json` (dentro de `docs/` porque ahí vive el sitio que sirve GitHub Pages, ver `../05_deployment/README.md`). Ver `../README.md`, "Columnas calculadas", y `../DATA_PLAYBOOK.md` para el detalle.

La recolección cruda de cada fuente (BGG, Bosque Lúdico) vive en `../01_data_understanding/` — ver el README de esa carpeta.

```bash
python3 02_data_preparation/construct_data.py
```

`../.github/workflows/sync-data.yml` corre `01_data_understanding/collect_initial_data/bgg/collect_bgg_data.py` y después esto, en ese orden, el día 1 de cada mes.
