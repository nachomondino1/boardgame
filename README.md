# Juegos de mesa

Prototipo de página estática para buscar y filtrar la colección de juegos de mesa (sin build system: HTML + CSS + JS vanilla).

## Correr local

```bash
python3 -m http.server 8765
```

Y abrir `http://localhost:8765`.

Vivo en: https://nachomondino1.github.io/boardgame/

## Archivos

- `index.html` / `style.css` / `app.js` — la página.
- `data.json` — datos de la pestaña "Juegos" del Sheet (`Juegos_de_mesa` en Drive). Se regenera solo, ver abajo.
- `scripts/build_data.py` — descarga la pestaña "Juegos" como CSV (export público, sin login) y regenera `data.json`. Mapea columnas por el texto del encabezado, no por posición, así que si agregás una columna nueva al Sheet no rompe nada (esa columna nueva se ignora hasta que se agregue una regla para ella en `HEADER_RULES`).
- `.github/workflows/sync-sheet.yml` — corre `build_data.py` todos los días a las 12:00 UTC y en cada ejecución manual, y si `data.json` cambió lo commitea y pushea a `main`. Eso dispara un redeploy automático de GitHub Pages.

### Sincronizar a mano

Si no querés esperar al cron, desde GitHub: Actions → "Sync data.json desde Google Sheet" → Run workflow. O localmente: `python3 scripts/build_data.py`.

### Sobre el Sheet público

La pestaña "Juegos" se lee vía el endpoint de export de Google Sheets (`.../export?format=csv&gid=...`), que ya es accesible sin login — no hace falta ninguna API key ni credencial guardada como secret. Si en algún momento el Sheet pasa a ser privado, hay que o volver a compartirlo "Cualquiera con el enlace: Lector", o migrar `build_data.py` a usar la API de Sheets con una service account.

## Qué tiene

- Buscador instantáneo por nombre.
- Filtro "¿cuántos jugadores somos?" (usa Jug. mín/máx, y marca "Ideal para hoy" si coincide con Jug. Best).
- Filtros por Estado (Own / Want to buy / Watchlist / Descartado) y Ocasión ideal.
- Orden por Puntaje ajustado (P×r), Puntaje BGG, Mi puntaje, Complejidad o Duración.
- Toggle "Según mi gusto" (duración ≤60 min, complejidad ≤2.5), tomado de la sección "Mi gusto" de la pestaña Resumen.
- Complejidad con color (verde→rojo), como el formato condicional del Sheet.

## Pendiente si esto vale la pena

- Botón "agregar a mi gusto" / recomendador más elaborado que el toggle actual.
- Comparar juegos lado a lado.
