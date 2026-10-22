# 02 — Data preparation

Dos pasos, en orden, los dos sobre `../docs/data/data.json`:

1. `integrate_data.py` — **solo integra**, no le pega a ninguna fuente externa: toma `sheet_source.load_games()` (`../01_data_understanding/sheet/`, fuente de verdad) + el caché de BGG (`../docs/data/cache/bgg/`) + el dataset de precios de Bosque Lúdico (`../01_data_understanding/bosque_ludico/bosque_data.json`, si corrió) y regenera `../docs/data/data.json` (dentro de `docs/` porque ahí vive el sitio que sirve GitHub Pages, ver `../05_deployment/README.md`). El Sheet siempre gana; BGG y Bosque Lúdico solo completan lo que quedó vacío. Ver `../README.md` y `../DATA_PLAYBOOK.md` para el detalle.
2. `construct_data.py` — calcula `puntaje_ajust_bgg` y `precio_calidad`, columnas que no vienen de ninguna fuente sino que se construyen a partir de otras ya integradas (`puntaje_bgg`+`reviews_bgg`, y `costo`+`puntaje_ajust_bgg`). Las fórmulas se migraron desde las celdas del Sheet (ver docstring del script) el día que esas dos columnas se sacaron de ahí — el Sheet ya no las tiene.

La recolección cruda de cada fuente (Sheet, BGG, Bosque Lúdico) vive en `../01_data_understanding/` — ver el README de esa carpeta.

Ambos scripts asumen que se corren desde la raíz del repo, en orden, tal como lo hace `../.github/workflows/sync-sheet.yml`:

```bash
python3 02_data_preparation/integrate_data.py
python3 02_data_preparation/construct_data.py
```
