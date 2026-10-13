# Juegos de mesa

Prototipo de página estática para buscar y filtrar la colección de juegos de mesa (sin build system: HTML + CSS + JS vanilla).

## Correr local

```bash
python3 -m http.server 8765
```

Y abrir `http://localhost:8765`.

## Archivos

- `index.html` / `style.css` / `app.js` — la página.
- `data.json` — snapshot de la pestaña "Juegos" del Sheet (`Juegos_de_mesa` en Drive). **No se sincroniza solo**: por ahora es una foto del 2026-10-13. Para actualizarlo hay que volver a exportar la pestaña y regenerar este archivo.

## Qué tiene

- Buscador instantáneo por nombre.
- Filtro "¿cuántos jugadores somos?" (usa Jug. mín/máx, y marca "Ideal para hoy" si coincide con Jug. Best).
- Filtros por Estado (Own / Want to buy / Watchlist / Descartado) y Ocasión ideal.
- Orden por Puntaje ajustado (P×r), Puntaje BGG, Mi puntaje, Complejidad o Duración.
- Toggle "Según mi gusto" (duración ≤60 min, complejidad ≤2.5), tomado de la sección "Mi gusto" de la pestaña Resumen.
- Complejidad con color (verde→rojo), como el formato condicional del Sheet.

## Pendiente si esto vale la pena

- Automatizar la actualización de `data.json` desde el Sheet (publicar la pestaña a CSV o usar la API) en vez de regenerarlo a mano.
- Deploy a GitHub Pages.
