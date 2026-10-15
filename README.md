# Juegos de mesa

Prototipo de página estática para buscar y filtrar la colección de juegos de mesa (sin build system: HTML + CSS + JS vanilla).

## Correr local

```bash
python3 -m http.server 8765
```

Y abrir `http://localhost:8765`.

Vivo en: https://nachomondino1.github.io/boardgame/

## Páginas

- `index.html` — **Catálogo**: los juegos del Sheet, buscador, filtros y orden.
- `hoy.html` — **¿Qué jugamos hoy?**: elegís cuántos son y te muestra qué podés jugar de lo que ya tenés (Estado = Own), ordenado por una heurística de qué tan bueno es cada juego para hoy. El toggle "incluir Watchlist" extiende la búsqueda a lo que no tenés todavía, y el toggle "buscar por cantidad ideal (best)" cambia el filtro de jugadores de Jug. mín/máx a Jug Best min/máx.
- `comprar.html` — **¿Cuál comprar?**: solo Watchlist, con sliders de duración máxima y complejidad máxima, el mismo filtro de jugadores, y (cuando el Sheet los tiene cargados) link a la tienda, costo relevado y relación precio/calidad en cada tarjeta, con opción de ordenar por estos dos últimos.

## Archivos

- `index.html` / `hoy.html` / `comprar.html` — las 3 páginas, en la raíz (las sirve GitHub Pages directo desde ahí).
- `js/shared.js` — helpers comunes a las 3 páginas (carga de datos, armado de las tarjetas, nav, etc.).
- `css/style.css` / `js/app.js` / `js/hoy.js` / `js/comprar.js` — estilos y lógica de cada página.
- `data/data.json` — datos de la pestaña "Juegos" del Sheet (`Juegos_de_mesa` en Drive). Se regenera solo, ver abajo.
- `scripts/build_data.py` — descarga la pestaña "Juegos" como CSV (export público, sin login), regenera `data/data.json` y arma el link a BGG de cada juego. Mapea columnas por el texto del encabezado, no por posición, así que si agregás una columna nueva al Sheet no rompe nada (esa columna nueva se ignora hasta que se agregue una regla para ella en `HEADER_RULES`).
- `.github/workflows/sync-sheet.yml` — corre `build_data.py` el día 1 de cada mes a las 12:00 UTC y en cada ejecución manual, y si `data/data.json` cambió lo commitea y pushea a `main`. Eso dispara un redeploy automático de GitHub Pages. Si agregaste un juego y no querés esperar al mes, lo disparás a mano (ver abajo).

### Links a BGG

BGG cerró el acceso sin autenticación a su API XML (devuelve 401), así que no se puede resolver el ID exacto de cada juego en el build automático. En cambio, cada juego linkea a una búsqueda de BGG por título, usando la columna "Nombre ingles" del Sheet (no la traducción local) como término (`geeksearch.php?...&q=<nombre>`), que en la práctica cae directo en el juego correcto como primer resultado. Para ediciones locales o proxys (p. ej. "Misterio (Ruibal)" → busca "Misterio", "Memotest (Ruibal)" → busca "Memory"), el término de búsqueda correcto está hardcodeado en `BGG_SEARCH_OVERRIDES` dentro de `scripts/build_data.py`, tomado de las pistas que ya estaban en la columna Notas del Sheet. Los combos/puzzles sin ficha real en BGG (ajedrez+damas, el puzzle de 1000 piezas, etc.) están en `BGG_SKIP` y no muestran link.

### Sincronizar a mano

Si no querés esperar al cron, desde GitHub: Actions → "Sync data.json desde Google Sheet" → Run workflow. O localmente: `python3 scripts/build_data.py`.

### Sobre el Sheet público

La pestaña "Juegos" se lee vía el endpoint de export de Google Sheets (`.../export?format=csv&gid=...`), que ya es accesible sin login — no hace falta ninguna API key ni credencial guardada como secret. Si en algún momento el Sheet pasa a ser privado, hay que o volver a compartirlo "Cualquiera con el enlace: Lector", o migrar `build_data.py` a usar la API de Sheets con una service account.

## Qué tiene

- Buscador instantáneo por nombre (Catálogo).
- Filtro "¿cuántos jugadores somos?" (usa Jug. mín/máx, y marca con un tag verde "Best con N" si N coincide con Jug Best mín/máx).
- Filtros por Estado (Own / Watchlist / Descartado).
- Orden por Puntaje ajustado, Puntaje BGG, Mi puntaje, Complejidad o Duración.
- Toggle "Según mi gusto" (duración ≤60 min, complejidad ≤2.5), tomado de la sección "Mi gusto" de la pestaña Resumen.
- Complejidad con color (verde→rojo), como el formato condicional del Sheet.
- Link directo a BGG en el título de cada tarjeta.
- "¿Qué jugamos hoy?": recomendador simple (no toma nada del Sheet, es una heurística en `shared.js::recommendationScore` que combina Mi gusto + N jugadores dentro de Jug Best mín/máx + puntaje personal/BGG).
- "¿Cuál comprar?": Watchlist filtrada por duración, complejidad y jugadores, con link a la tienda, costo relevado y relación precio/calidad cuando están cargados en el Sheet.

## Pendiente si esto vale la pena

- Comparar juegos lado a lado.
- Si en algún momento vale la pena el link exacto a BGG (no un search): habría que resolver el ID de cada juego a mano (la API quedó bloqueada) y guardarlo como columna en el Sheet.
