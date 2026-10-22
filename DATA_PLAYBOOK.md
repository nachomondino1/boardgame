# Playbook de flujo de datos

Guía del patrón de datos usado en este proyecto (catálogo de juegos de mesa), pensada para pegar en un `CLAUDE.md` o en el prompt inicial de un proyecto nuevo que necesite algo parecido: un sitio estático, sin backend propio, cuyo contenido integra varias fuentes (una curada a mano, otras automatizadas).

**Nota sobre el Google Sheet:** este proyecto arrancó con un Sheet como fuente de verdad (la sección "Cómo adaptarlo a un proyecto nuevo" más abajo sigue siendo la guía genérica para eso, vale para otro proyecto que sí lo necesite). Acá se abandonó: una vez que BGG y Bosque Lúdico se automatizaron, lo que quedaba en el Sheet era ~10 columnas de ~30 filas que cambian pocas veces al año — mantener el fetch a la API de Google (CSV + .xlsx para hyperlinks) para eso dejó de valer la pena. Hoy esa fuente es `01_data_understanding/ludoteca/mi_ludoteca.json`, un archivo versionado en el repo que se edita directo. Ver "Cuándo un Sheet deja de valer la pena" en Decisiones clave.

## Filosofía

- **La fuente de verdad la edita un humano**, no en código ni en un admin panel — hoy un JSON versionado en el repo (`mi_ludoteca.json`); en otro proyecto, o en este al principio, puede ser un Google Sheet. Cero backend, cero base de datos propia.
- **El sitio nunca le pega a una API externa en runtime.** Hay un paso de build async (CI) que junta las fuentes y las convierte en un JSON estático, que es lo que el sitio realmente consume.
- **Cada sync es un commit.** El JSON vive versionado en el repo, así que un cambio en cualquier fuente se ve como un diff normal de git, y un dato roto se puede `git revert`.
- **El build es tolerante a cambios en la forma de la fuente curada a mano** (agregar/reordenar columnas o campos) pero intolerante a fallar en silencio (si algo sale muy mal, el script explota en vez de commitear datos vacíos o truncados).

## Arquitectura / flujo de datos

```
mi_ludoteca.json (lo que tenés o tuviste)    GitHub público de un tercero (ranking de BGG)
  editado a mano en el repo                   beefsack/bgg-ranking-historicals
        │                                          │  CSV diario, sin auth
        ▼                                          ▼
01_data_understanding/ludoteca/        01_data_understanding/bgg/
  ludoteca_source.py (load_games())      collect_bgg_rankings.py
  resuelve bgg_url + bgg_id              → bgg/bgg_top1000.csv (versionado,
        │                                   ya trae bgg_id por fila)
        └──────────────────┬───────────────────────┘
                            ▼
        01_data_understanding/game_universe.py (load_universe())
          ludoteca (Own/Prev. owned) + candidatos del top N que
          no sean ya tuyos (dedupe por bgg_id) → Estado "Watchlist"
                            │
        ┌───────────────────┼────────────────────────────────────┐
        ▼                                                         ▼
02_data_preparation/integrate_data.py        01_data_understanding/bosque_ludico/resolve_bosque_links.py
   integra:                                     + collect_bosque_precios.py
   universo + caché BGG + dataset Bosque          (juegos Watchlist: link a la
   Lúdico (ambos solo rellenan huecos,            tienda + precio actual, ver
   la ludoteca siempre manda sobre lo suyo)       el README de la carpeta)
        │                                                     │
        │◄──── docs/data/cache/bgg/<bgg_id>.json ◄── 01_data_understanding/bgg/enrich_bgg.py (modo dummy, automático)
        │◄──── 01_data_understanding/bosque_ludico/bosque_data.json (manual) ──┘
        ▼
02_data_preparation/construct_data.py
   calcula puntaje_ajust_bgg y precio_calidad
   (derivadas de otras columnas ya integradas,
   no vienen de ninguna fuente — ver más abajo)
        ▼
data/data.json   (commiteado al repo, fuente de verdad del sitio)
        ▲
        │  .github/workflows/sync-data.yml: cron mensual + workflow_dispatch manual
        │  corre collect_bgg_rankings.py + enrich_bgg.py + integrate_data.py + construct_data.py,
        │  commitea lo que cambió, pushea a main
        │  (mensaje de commit con "[skip ci]" para no re-triggerear otros workflows)
        ▼
push a main → redeploy automático de GitHub Pages
        ▼
Frontend vanilla JS: <link rel="preload" href="data/data.json" as="fetch" crossorigin>
                      + fetch("data/data.json") al cargar la página
```

Nadie en el camino del usuario final toca ninguna API externa: para quien visita el sitio, `data/data.json` es un archivo estático más, servido por GitHub Pages.

**01 (entender/recolectar) nunca depende de un output de 02 (integrar).** `integrate_data.py` y los scripts de Bosque Lúdico importan `game_universe.load_universe()`, nunca al revés — 02 puede depender de 01, no al contrario. Dentro de 01, una carpeta por fuente (`ludoteca/`, `bgg/`, `bosque_ludico/`), cada una solo sabe de la suya, más `game_universe.py` en la raíz (la única pieza que combina más de una fuente). El sitio sigue consumiendo un único `data.json`: la separación 01/02 es interna del pipeline, no se traduce en más fetches para el frontend.

**El universo de candidatos ya no lo cura una persona a mano (la vieja columna Watchlist del Sheet): lo arma automáticamente "top N de un ranking público menos lo que ya tenés".** Esto es deliberado — mantener a mano una lista de "juegos que me interesan" no escala a miles de candidatos, y el ranking de BGG ya hace ese trabajo de curación/orden. El costo es volumen (el "¿Cuál comprar?" del sitio puede mostrar hasta ~1000 tarjetas); los datos por candidato están casi completos (~98%, `enrich_bgg.py` contra un dataset placeholder de 2025 — ver "Decisiones clave"), salvo precio, que sigue dependiendo de Bosque Lúdico corrido a mano.

**Un identificador compartido por todas las fuentes (`bgg_id`, el id de BGG) en vez de matchear por nombre.** Cada juego del universo lleva `bgg_id` como campo de primera clase, calculado una sola vez (`ludoteca_source.extract_bgg_id` para tu ludoteca, directo de la columna del CSV para los candidatos del top N) y propagado tal cual por el resto del pipeline — `integrate_data.py` lo usa para encontrar el caché de BGG, `game_universe.py` para el dedupe. Antes cada módulo re-derivaba el id con su propia regex sobre `bgg_url`; centralizarlo evita que una de esas copias se desincronice y rompe menos si mañana se agrega una fuente que no tenga URL pero sí el id directo.

## Decisiones clave (y por qué)

- **JSON commiteado en vez de fetch a la API de Sheets en cada visita.** Sin esto: latencia extra en cada carga, sin rate limits propios (los de Google sí existen), sin API key/credential que guardar, y funciona en un host 100% estático (GitHub Pages no tiene backend). El costo es que el dato puede estar hasta un mes desactualizado — aceptable para un catálogo que no cambia todos los días; si hiciera falta más tiempo real, bajar el cron, no volver al fetch en vivo.
- **CSV export público en vez de la API oficial de Sheets.** Mientras el Sheet esté compartido "cualquiera con el enlace: lector", `.../export?format=csv&gid=...` no pide ninguna credencial. Si el Sheet pasara a ser privado, la alternativa es la API de Sheets con una service account (más setup, un secret que guardar en el repo).
- **Mapeo de columnas por texto del encabezado, no por posición/índice.** Agregar o reordenar una columna en el Sheet no rompe el build; una columna nueva sin regla se ignora en silencio (ver "Qué evitar" sobre el costo de ese silencio).
- **Falla ruidosa ante datos sospechosos.** El script corta con `sys.exit(1)` si parsea muy pocas filas o no encuentra la columna esperada, en vez de commitear un JSON vacío o a medio llenar. Un build que "funciona" pero pisa datos buenos con basura es peor que un build que no corre.
- **Lógica de enriquecimiento específica del dominio vive en el script, como constantes documentadas**, no desparramada en el frontend. En este proyecto es la resolución de links a BGG (`BGG_SEARCH_OVERRIDES`, `BGG_SKIP`): cada entrada tiene al lado, en un comentario, de dónde salió el override (en este caso, pistas que ya estaban a mano en la columna "Notas" del Sheet).
- **Enriquecimiento externo con caché por id estable, y la fuente curada a mano siempre gana.** `01_data_understanding/bgg/enrich_bgg.py` arma `docs/data/cache/bgg/<bgg_id>.json` (gitignored, un archivo por juego) y `integrate_data.py` lo usa solo como **fallback**: completa un campo (`puntaje_bgg`, `complejidad`, etc.) únicamente si quedó vacío, nunca pisa un valor ya cargado a mano. La vía oficial (`--mode api`, `xmlapi2/thing`) está **bloqueada** hasta que BGG apruebe la aplicación registrada (hoy devuelve 401); mientras tanto corre automático contra un dataset placeholder de terceros (`--mode dummy`, default — ver el bullet de abajo sobre datasets públicos).
- **Reusar cookies de una sesión de navegador en un script aparte no es una alternativa real cuando el bot-detection correlaciona fingerprint de conexión, no solo el cookie.** Se probó explícitamente contra la página normal de BGG (reusando cookies de una sesión ya autenticada): aunque el `cf_clearance` se exportara recién pasado el challenge, `curl`/`urllib` seguían recibiendo un challenge nuevo (403) — Cloudflare lo ata al TLS/JA3 y al stack de headers real del navegador que lo generó, no solo al valor de la cookie. Antes de asumir que "cookies + requests" alcanza para reusar una sesión ya autenticada contra un anti-bot serio, probarlo con un caso real primero; si falla, no vale la pena perseguir evasión más sofisticada (spoof de fingerprint, etc.) — es la misma línea que no resolver CAPTCHAs, solo que con más ingeniería. Esa vía quedó descartada (no está ni en el código): la opción que sí funciona sin evadir nada es un dataset público de un tercero (ver abajo).
- **Columnas calculadas que antes eran fórmulas del Sheet se migran leyendo la fórmula real de la celda, nunca reinventándola.** Al sacar `puntaje_ajust_bgg` y `precio_calidad` del Sheet (para que solo queden ahí los datos que no son de BGG/Bosque Lúdico) se usó la API de Sheets (`get_spreadsheet` con `includeGridData` + `fields: ["...userEnteredValue.formulaValue"]`) para leer la fórmula tal cual estaba en varias celdas, no se adivinó "a ojo" mirando los valores. Esto destapó que el Sheet tenía **dos variantes de la misma fórmula conviviendo** (una con una constante hardcodeada en 53 filas, otra que recalculaba un desvío estándar en vivo en 6 filas, más 3 filas con el valor pegado a mano sin fórmula) — una inconsistencia invisible si solo se mira el resultado. Verificar el resultado del script nuevo contra el valor real de varias filas del Sheet (no solo "corre sin error") antes de darlo por bueno.
- **Ante una fórmula inconsistente entre filas de un Sheet, no elegir una variante en silencio: mostrarle las dos al usuario con el conteo real de filas de cada una y dejar que elija cuál es la oficial.** Es una decisión de negocio (qué constante usar), no una de implementación.
- **Cuando la fuente oficial de un dato está bloqueada (API que exige auth, sitio con bot-detection serio), buscar un dataset público de un tercero que ya hizo ese scraping/sync antes de resignarse a esperar o de evadir el bloqueo.** El top N de BGG sale de `github.com/beefsack/bgg-ranking-historicals`: un CSV diario, público, sin auth, mantenido por un tercero — no le pega a BGG en absoluto. Verificar que de verdad esté vivo (último commit reciente, no un repo abandonado) antes de depender de él, y documentar explícitamente que es una fuente de terceros, no la oficial, para que quede claro si algún día hay que migrar.
- **Al combinar "lo que el usuario cargó a mano" con "un dataset externo grande", el externo nunca duplica una entidad que ya está en el de mano: se deduplica por id estable (acá, el id de BGG extraído de la URL), nunca por nombre.** Dos títulos pueden diferir en mayúsculas/acentos/edición y el nombre nunca es una clave confiable para dedupe entre fuentes distintas.
- **Cuándo un Sheet deja de valer la pena como fuente de lo curado a mano: cuando lo que queda ahí es chico y cambia poco.** Acá el Sheet original tenía ~70 columnas pobladas por BGG/Bosque Lúdico fila por fila; una vez que esas dos fuentes se automatizaron, quedó reducido a ~10 columnas de ~30 filas que el usuario cambia pocas veces al año. En ese punto, mantener el fetch a la API de Google (CSV + `.xlsx` para hyperlinks, parseo de columnas) ya no se paga a sí mismo — un JSON versionado en el repo, editado directo, es estrictamente más simple y no depende de que el Sheet siga siendo público. La señal para hacer el cambio no es "¿el Sheet es incómodo?" sino "¿lo que queda en el Sheet todavía justifica el costo de ir a buscarlo por HTTP?".

## Cómo adaptarlo a un proyecto nuevo

Esta sección asume que la fuente curada a mano va a ser un Google Sheet (el patrón más común). Si en cambio va a ser un JSON editado directo en el repo (ver el punto de arriba sobre cuándo conviene eso), se simplifica: nada de `SPREADSHEET_ID`/CSV export/`.xlsx`, solo leer el archivo y validar el esquema mínimo.

1. Compartir el Sheet fuente como "Cualquiera con el enlace: Lector" y anotar su `SPREADSHEET_ID` y el `GID` de la pestaña a leer (ambos están en la URL cuando tenés esa pestaña abierta).
2. Escribir el mapeo de columnas (`HEADER_RULES` o equivalente) en base al **texto** de los headers reales del Sheet, nunca a su posición. Dejar explícito qué pasa con una columna que no matchea ninguna regla (en este proyecto: se ignora).
3. Separar los campos en numéricos vs. texto, con cuidado si el Sheet usa coma decimal (es-AR/es-ES) — no asumir `parseFloat` directo sobre `"3,5"`.
4. Si necesitás algo que el export CSV no expone (hyperlinks puestos a mano, formato condicional, etc.), exportar como `.xlsx` y parsear el XML del paquete OOXML: workbook.xml → rels → hoja → `<hyperlinks>`.
5. Hacer que el script sea prolijo ante fallos parciales: si el request a Google falla o devuelve algo inesperado, cortar con un mensaje claro en vez de seguir con datos parciales.
6. Crear el workflow de GitHub Actions: `schedule` (cron) + `workflow_dispatch` (para forzar el sync a mano sin esperar), `permissions: contents: write`, y commitear **solo si `git diff --cached` tiene algo** — si no, el job no debe ensuciar el historial con commits vacíos.
7. En el frontend: `<link rel="preload" as="fetch" crossorigin>` del JSON en el `<head>` de cada página que lo necesita (arranca la descarga en paralelo al parseo del HTML), `fetch()` simple en el JS, y un estado de error visible en el DOM si el fetch falla — nunca fallar en silencio dejando la página en blanco.
8. Documentar en el README: dónde vive la fuente curada a mano, cómo correr el sync a mano (Actions → Run workflow, o el script local), y qué hacer el día que esa fuente cambie de forma (deje de ser pública, o se reemplace por un JSON como acá).

## Resolver un link a producto en un sitio con buscador bloqueado por robots.txt

Para relevar precios de El Bosque Lúdico (`01_data_understanding/bosque_ludico/resolve_bosque_links.py`) hizo falta encontrar la ficha de producto de cada juego sin usar su buscador: su `robots.txt` tiene `Disallow: /search/` explícito. La solución, generalizable a cualquier sitio en la misma situación:

- **Usar el sitemap del sitio (`sitemap.xml` / `sitemap.xml.gz`, declarado en `robots.txt` bajo `Sitemap:`) como listado completo, en vez del buscador.** El sitemap está pensado para ser indexado — nunca está en `Disallow` — y en un solo request trae todas las URLs de producto, que después se matchean por texto en el propio script, sin tocarle más al sitio.
- **Matchear por contención de palabras completas, no por ratio de caracteres (`difflib.SequenceMatcher` crudo).** Un ratio de similitud de string completo da falsos positivos fuertes con nombres cortos (p. ej. "Codenames" vs. slug "cometas" salía con ratio 0.62): dos nombres cortos comparten letras por azar. La regla que funcionó: normalizar y partir en palabras, exigir que (casi) todas las palabras del término buscado aparezcan como palabra completa en el slug candidato (no como substring de letras), y recién ahí aceptar el match. Tiendanube (y seguramente otras plataformas) le agrega un sufijo random de pocos caracteres a los slugs que colisionan (p. ej. `ark-nova-v2ui5`): conviene detectar y descartar ese sufijo (último token corto con al menos un dígito) antes de normalizar, para no ensuciar el matching.
- Mismo patrón que la resolución de links a BGG: un override a mano (`BOSQUE_SEARCH_OVERRIDES`/`BOSQUE_SKIP`, análogo a `BGG_SEARCH_OVERRIDES`/`BGG_SKIP`) para los casos que el matching automático no resuelve bien, documentado con un comentario de por qué.
- Si un sitio no público bloquea agresivamente (Cloudflare challenge, 401 sin app aprobada, etc.) y no tiene sitemap ni vía oficial, aplica lo mismo que ya está documentado para BGG en "Decisiones clave": no vale la pena perseguir evasión de bot-detection, es la misma familia de problema que resolver un CAPTCHA a mano.

## Separar recolección cruda (01) de transformación final (02), una carpeta por fuente

Cuando se suma una fuente externa nueva (no la fuente curada a mano principal), el script que la recolecta/matchea va en `01_data_understanding/<fuente>/` (estructura CRISP-DM del repo: `ludoteca/`, `bgg/`, `bosque_ludico/`), separado de `02_data_preparation/integrate_data.py` que arma el `data.json` final integrando todas. Generalizable: si una fuente cambia a un ritmo distinto de otra (en este proyecto, el *link* a una ficha de producto es estable pero el *precio* cambia seguido), conviene separarlas en dos scripts/pasos en vez de uno solo que recalcule todo cada vez — así un re-relevamiento de precio no vuelve a pagar el costo de resolver matches.

**Nombrar los datasets por la fuente, no por lo que hace el script que los generó:** `bosque_data.json` (no `bosque_ludico_precios.json`), `bgg_data.json` si en algún momento BGG produce un único dataset consolidado en vez de caché por id. El nombre del archivo le dice a quien lo abre de dónde salió el dato sin tener que leer el script; el nombre del script le dice qué hace (`collect_bosque_precios.py`, `resolve_bosque_links.py`). Mismo criterio para el script que solo integra: si lo único que hace es combinar fuentes ya recolectadas, se llama `integrate_data.py` (o similar), no `build_data.py` — "build" es ambiguo sobre si también recolecta.

## Qué evitar

- Pegarle a la API de Google (o hacer `fetch` al Sheet) desde el cliente en cada visita — expone el id/gid del Sheet de forma prominente, agrega latencia, y si el Sheet se pone privado rompe el sitio en producción en vez de romper el próximo sync en CI.
- Mapear columnas por índice/posición: cualquier edición inocente del Sheet (reordenar, insertar una columna) corrompe silenciosamente los datos.
- Mezclar lógica de negocio hardcodeada (overrides, excepciones puntuales) sin un comentario que diga de dónde salió el dato — a los seis meses nadie se acuerda por qué "Memotest (Ruibal)" busca "Memory".
- Commitear igual aunque no haya cambios (ensucia el historial) o commitear datos a medias cuando el build detecta algo raro (preferir cortar con `exit 1` y dejar el `data.json` viejo tal cual).
- Que el frontend asuma que el fetch siempre funciona: sin un `.catch` que muestre algo legible, un `data.json` roto o un typo en la ruta deja la página en blanco sin pista de qué pasó.
