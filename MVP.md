# MVP multiusuario (branch `mvp`)

Documento de directrices. Lo que se construya en esta branch tiene que poder justificarse con algo de acá; si hay que cambiar el plan, se cambia primero este archivo. Contexto y riesgos en `escalabilidad.md` (branch `staging`/`main`).

## 1. Objetivo

Que cualquier persona abra una URL, diga qué juegos tiene (con su usuario de BGG o marcándolos a mano) y vea **Mi ludoteca**, **¿Qué jugamos hoy?** y **¿Cuál comprar?** con el diseño y las reglas de este proyecto, sobre el catálogo de ~28.000 juegos.

Objetivos reales, en orden:
1. **Aprender a armar y desplegar un MVP** (branch propia + hosting) para repetirlo en otros proyectos.
2. Que 2 o 3 personas lo prueben con su usuario.

No es un producto: sin login, sin cuentas, sin cobro.

## 2. Alcance

**Dentro**
- Entrada por **username de BGG** (trae `own`, `prevowned`, `wanttobuy`, `rating`).
- Entrada **manual**: marcar juegos sobre el catálogo, guardado en el navegador. No usa la API de BGG.
- Las tres páginas existentes, con `estado` y `mi_puntaje` calculados en el navegador.
- Buscador por nombre sobre los ~28.000 juegos.
- Logo "Powered by BGG" con link, visible.

**Fuera (no se construye)**
- Login, cuentas, contraseñas, base de datos de usuarios.
- Registro de partidas, grupos, social, mapa de tiendas.
- Cobro, publicidad, licencia comercial de BGG.
- Cambios en `main`, GitHub Pages o el flujo de `sync_data.sh` actual.

## 3. Arquitectura

```
Navegador (páginas estáticas de docs/)
   ├── names.json        buscador por nombre
   ├── index.json        filtros, orden y tarjetas (todos los juegos)
   ├── games/NN.json     fichas completas, por tramos de ids
   ├── localStorage      colección del visitante
   └── /api/collection?user=X   ← función (Cloudflare Pages Function)
                                     └── BGG xmlapi2/collection (con BGG_TOKEN, solo en el servidor)
```

- **Hosting:** Cloudflare Pages, rama de producción `mvp`, directorio de salida `docs/`, funciones en `functions/` (raíz del repo). Plan gratis; revisar sus límites actuales antes de compartir la URL.
- **Una sola función**, la de la colección. Las fichas **no** pasan por función: son archivos estáticos (decisión, ver sección 4).
- El token de BGG se carga como secreto en el panel de Cloudflare (`BGG_TOKEN`). Nunca en el repo ni en el navegador. Para desarrollo local, un archivo ignorado por git.

## 4. Datos

Generados en local por el pipeline de siempre y commiteados en la branch (Cloudflare no tiene acceso a `data/01_data_understanding/`, que es gitignored).

| Archivo | Contenido | Tamaño medido (gzip) |
|---|---|---|
| `docs/data/names.json` | `[bgg_id, nombre]` de todos los juegos | ~0,4 MB |
| `docs/data/index.json` | campos para filtrar/ordenar/mostrar tarjeta (ver abajo), como listas | ~1,0 MB |
| `docs/data/games/NNN.json` | ficha completa (todos los campos salvo `estado`/`mi_puntaje`), 500 juegos por archivo, **ordenados por ranking BGG** (los sin ranking al final, por reviews) | ~80 KB c/u, ~56 archivos |

Campos de `index.json`: `bgg_id, nombre, jug_min, jug_max, jug_best_min, jug_best_max, duracion, complejidad, puntaje_bgg, reviews_bgg, ranking_bgg, grupo, anio, modo, puntaje_ajust_bgg`, más una referencia al tramo de la ficha. Los nombres de columnas van en un encabezado del archivo.

**Por qué fichas estáticas y no función:** una función que lea el catálogo completo (24 MB) en cada pedido es lenta y frágil; una base (D1/KV) agrega carga y mantenimiento que el MVP no necesita. Los tramos son pocos archivos, se cachean en el navegador y no requieren servidor. Ordenarlos por ranking hace que una página de 60 tarjetas ordenadas por ranking caiga en uno o dos tramos (medido en M2: 1 tramo en ¿Cuál comprar?). Contra: cada sync regenera todos los tramos y suma peso al historial de git. Se acepta para un MVP; si molesta, se pasa a base de datos (D1) sin cambiar lo que ve el usuario.

No existe un `catalog.json` completo: `build_catalog.py` escribe los tres archivos directamente desde `build_games()` (el completo pesaba 24 MB y no hace falta publicarlo). Los tramos suman ~24,7 MB sin comprimir en el repo (medido en M1).

**Regla de estado (se calcula en el navegador, igual que `estado_de()` en `construct_data.py`):**
Own > Prev. owned > Want to buy > Watchlist (cualquier juego sin marca). `mi_puntaje` = `rating` de la colección (vacío si no puntuó).

**Juegos de la colección que no están en el catálogo:** no se muestran; se informa "N juegos no encontrados".

## 5. Función `/api/collection`

- `GET /api/collection?user=<bgg_username>`
- Respuesta 200: `{ user, fetchedAt, games: [{ id, own, prevowned, wanttobuy, rating }] }`
- BGG a veces responde 202 ("preparando la colección"): la función reintenta unas veces con espera corta; si no está lista, responde 202 al navegador, que reintenta.
- Errores claros para: usuario inexistente, colección vacía u oculta, límite de BGG (429/503), token inválido.
- Respetar el `Crawl-delay` de 5 s de BGG y los reintentos de `bgg_common.py` como referencia.
- Caché en el servidor (Cache API de Cloudflare) de unas horas por usuario, para no gastar la cuota del token compartido.
- Valida el username (largo y caracteres) antes de llamar a BGG. No guarda nada más.

## 6. Colección en el navegador

`localStorage`, con `try/catch` en cada acceso (puede fallar en ventana privada):

```
mvp.collection = { source: "bgg" | "manual", user, savedAt, games: { "<bgg_id>": { own, prevowned, wanttobuy, rating } } }
```

- Entrada manual: buscar un juego por nombre y marcar Own / Want to buy (y opcionalmente puntaje).
- Con username: se baja la colección y se guarda; se refresca si pasaron más de unas horas o con un botón.
- Botón "borrar mis datos".

## 7. Páginas

Mismas que hoy, copiadas de `docs/` y adaptadas:
- **Entrada** (`index.html`): campo de username de BGG, opción "cargar a mano", explicación de una línea.
- **Mi ludoteca**: Own y Prev. owned de la colección del visitante.
- **¿Qué jugamos hoy?**: elige cantidad de jugadores; muestra lo que tiene, ordenado por ranking.
- **¿Cuál comprar?**: Watchlist del catálogo más Want to buy, con paginación y filtros sobre el índice.
- Buscador por nombre en la barra, que usa `names.json` y abre la ficha del tramo.

Diseño: el de `DESIGN_PLAYBOOK.md`. Sin cambios visuales salvo la entrada y el logo de BGG.

## 8. Reglas y restricciones

- **BGG:** uso no comercial, app registrada, "Powered by BGG" visible, nada de entrenar IA con los datos. Si algún día se cobra, hace falta licencia comercial (ver `escalabilidad.md`).
- **Cazagangas / precios en USD:** son de Argentina; se dejan porque el público objetivo es Argentina.
- **Privacidad:** no se guarda ninguna colección en el servidor más allá del caché temporal.
- **Datos y secretos:** el token y los datos crudos no se commitean.

## 9. Orden de construcción

| Hito | Qué | Hecho cuando |
|---|---|---|
| M0 | Branch `mvp` y primer catálogo de prueba | ✅ hecho |
| M1 | `build_catalog.py` genera `names.json`, `index.json` y `games/NNN.json` | ✅ hecho: 27.796 juegos, 56 tramos, índice y fichas coherentes |
| M2 | Páginas funcionando en local con **entrada manual** y estado/puntaje calculados en el navegador | ✅ hecho: marqué 3 juegos en `coleccion.html` y aparecen bien en Mi ludoteca, ¿Qué jugamos hoy? y la landing; ¿Cuál comprar? excluye los marcados Own |
| M3 | Función `/api/collection` y entrada por username, en local con `wrangler` | Mi username carga mi colección real y coincide con `data.json` |
| M4 | Deploy en Cloudflare Pages desde `mvp`, token como secreto | La URL pública funciona con mi username |
| M5 | Lo prueban 2 o 3 personas con su usuario | Anoto qué falla y qué piden |

Cada hito se commitea aparte en `mvp`.

## 10. Criterios de aceptación del MVP

- Con un username válido y colección pública, se ve la ludoteca en menos de ~10 s (la primera vez).
- Con username inexistente u oculto, hay un mensaje claro.
- Sin username, la entrada manual alcanza para usar las tres páginas.
- La primera carga de datos no supera ~2 MB comprimidos (nombres + índice + una ficha).
- Nada de `main` ni de GitHub Pages cambió.

## 11. Decisiones abiertas

- El comparador de ¿Cuál comprar? usa un `<datalist>` con ~27.000 nombres; funciona pero es pesado en mobile. Cambiarlo por un buscador que consulte `names.json` por tramos de texto.

- Si el catálogo publicado debe incluir todos los juegos o solo los que pasen un corte de calidad (hoy: todos).
- Cuántos juegos por tramo de ficha (hoy 500).
- Si "¿Cuál comprar?" pagina del lado del cliente sobre el índice (previsto) o hace falta algo más.
- Qué hacer con los juegos de la colección que no están en el catálogo (hoy: solo avisar).
