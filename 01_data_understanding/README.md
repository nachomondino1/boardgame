# 01 — Data understanding

La fuente de datos es el Google Sheet "Juegos_de_mesa" (pestaña "Juegos"), editado a mano por el usuario — no hay un dump local de datos crudos para explorar acá, el Sheet mismo es la fuente.

- Ver `../DATA_PLAYBOOK.md` para el detalle completo del esquema (`HEADER_RULES`), de dónde sale cada columna y qué decisiones se tomaron al diseñarlo.
- `SPREADSHEET_ID` y `GID` de la pestaña están hardcodeados en `../02_data_preparation/build_data.py`.

Si en algún momento hace falta explorar el Sheet crudo (ej. detectar filas con datos faltantes o inconsistentes antes de limpiar), ese análisis va acá.
