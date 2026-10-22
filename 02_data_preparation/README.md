# 02 — Data preparation

- `build_data.py` — descarga la pestaña "Juegos" del Sheet como CSV, mapea columnas por texto de encabezado y regenera `../docs/data/data.json` (dentro de `docs/` porque ahí vive el sitio que sirve GitHub Pages, ver `../05_deployment/README.md`). Ver `../README.md` y `../DATA_PLAYBOOK.md` para el detalle.
- `enrich_bgg.py` — paso manual que completa, vía caché local (`../docs/data/cache/bgg/`), los campos que el Sheet dejó vacíos para juegos con link exacto a BGG. El Sheet siempre gana; esto solo llena huecos.

Ambos scripts asumen que se corren desde la raíz del repo (`python3 02_data_preparation/build_data.py`), tal como lo hace `../.github/workflows/sync-sheet.yml`.
