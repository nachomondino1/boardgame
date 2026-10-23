# Playbook de flujo de datos

Guía del patrón de datos usado en este proyecto (catálogo de juegos de mesa), pensada para pegar en un `CLAUDE.md` o en el prompt inicial de un proyecto nuevo que necesite algo parecido: un sitio estático, sin backend propio, cuyo contenido integra varias fuentes (una curada a mano, otras automatizadas).

**Nota sobre el Google Sheet:** este proyecto arrancó con un Sheet como fuente de verdad (la sección "Cómo adaptarlo a un proyecto nuevo" más abajo sigue siendo la guía genérica para eso, vale para otro proyecto que sí lo necesite). Acá se abandonó dos veces: primero el Sheet se reemplazó por un JSON (`mi_ludoteca.json`, ver "Cuándo un Sheet deja de valer la pena" en Decisiones clave), y después ese JSON se fusionó directo dentro de `01_data_understanding/bgg/bgg_data.csv` — el universo de juegos entero (identidad + Estado + datos de BGG) vive hoy en un único CSV, con columnas propias (editadas a mano o pidiéndoselo a Claude) y columnas de BGG (se refrescan solas) conviviendo en la misma fila.

## Filosofía

- **La fuente de verdad la edita un humano**, no en código ni en un admin panel — hoy un CSV versionado en el repo (`bgg_data.csv`, columnas propias dentro de él); en otro proyecto, o en este al principio, puede ser un Google Sheet o un JSON aparte. Cero backend, cero base de datos propia.
- **El sitio nunca le pega a una API externa en runtime.** Hay un paso de build async (CI) que junta las fuentes y las convierte en un JSON estático, que es lo que el sitio realmente consume.
- **Cada sync es un commit.** El JSON vive versionado en el repo, así que un cambio en cualquier fuente se ve como un diff normal de git, y un dato roto se puede `git revert`.
- **El build es tolerante a cambios en la forma de la fuente curada a mano** (agregar/reordenar columnas o campos) pero intolerante a fallar en silencio (si algo sale muy mal, el script explota en vez de commitear datos vacíos o truncados).

## Arquitectura / flujo de datos

```
01_data_understanding/bgg/collect_bgg_data.py
  dataset público de terceros, Hugging Face (ver "Decisiones clave")
  Bootstrap (bgg_data.csv no existe): top N del ranking + ludoteca (una
  sola vez, para taguear Own/Prev. owned) → el resto queda Watchlist.
  Refresh (ya existe): re-completa las columnas de BGG de lo que ya está.
  --add <id o nombre>: suma un juego puntual (así crece el universo).
                            │
                            ▼
      01_data_understanding/bgg/bgg_data.csv   (commiteado, bgg_id primera columna)
        columnas propias (nombre, estado, modo, mi_puntaje, pros, cons,
        youtube, notas) + columnas de BGG (descripcion, disenador,
        edad_min, jug_min/max, jug_best_min/max, duracion_min/max,
        complejidad, puntaje_bgg, reviews_bgg, ranking_bgg, mecanicas,
        categorias) — un humano manda sobre las primeras, BGG sobre las
        segundas, nunca se pisan entre sí.
                            │
                            ▼
      02_data_preparation/construct_data.py
        calcula duracion, modo, transportable, puntaje_ajust_bgg,
        precio_calidad (derivadas, no vienen de ninguna fuente — ver
        README.md "Columnas calculadas")
                            ▼
      data/data.json   (commiteado al repo, fuente de verdad del sitio)
                            ▲
        │  .github/workflows/sync-data.yml: cron mensual + workflow_dispatch manual
        │  corre collect_bgg_data.py + construct_data.py, commitea lo que
        │  cambió, pushea a main ("[skip ci]" para no re-triggerear otros workflows)
                            ▼
      push a main → redeploy automático de GitHub Pages
                            ▼
      Frontend vanilla JS: <link rel="preload" href="data/data.json" as="fetch" crossorigin>
                            + fetch("data/data.json") al cargar la página

[EN UN FUTURO] 01_data_understanding/bosque_ludico/: resolve_bosque_links.py
+ collect_bosque_precios.py ya funcionan (bgg_data.csv → links.json →
bosque_data.json, primera columna bgg_id) pero nada los corre activamente
ni los integra con bgg_data.csv todavía — ver "Qué evitar"/Pendiente.
```

Nadie en el camino del usuario final toca ninguna API externa: para quien visita el sitio, `data/data.json` es un archivo estático más, servido por GitHub Pages.

**01 (entender/recolectar) nunca depende de un output de 02 (integrar).** `construct_data.py` lee `bgg_data.csv` directo (un output de 01), nunca al revés. Hoy 01 es más simple que antes: una sola fuente activa (`bgg/`), ya no hace falta una capa que combine varias (no existía integración de Bosque Lúdico todavía) — si en el futuro se suma esa segunda fuente, la integración (por nombre) va en `02_data_preparation/`, nunca en 01.

**El universo de candidatos ya no lo cura una persona a mano (la vieja columna Watchlist del Sheet): lo arma automáticamente "top N de un ranking público menos lo que ya tenés", con la opción de sumar juegos puntuales con `--add`.** Esto es deliberado — mantener a mano una lista de "juegos que me interesan" no escala a miles de candidatos, y el ranking de BGG ya hace ese trabajo de curación/orden inicial; `--add` cubre el caso puntual ("quiero este juego en el análisis aunque no esté en el top N"). El costo es volumen (el "¿Cuál comprar?" del sitio puede mostrar hasta ~1000 tarjetas); los datos por candidato están casi completos (~98%, contra un dataset placeholder de 2025 — ver "Decisiones clave"), salvo precio, que depende de una integración con Bosque Lúdico que todavía no existe.

**Identidad + enriquecimiento externo en un único archivo, no en piezas separadas que haya que combinar en cada build.** Versiones anteriores de este pipeline separaban "quién tenés" (un JSON/Sheet aparte) de "qué sabe BGG de cada uno" (un caché por id, regenerado en el build). Fusionarlos en un solo CSV con columnas propias vs. columnas de fuente externa (nunca se pisan entre sí, ver más arriba) simplifica el pipeline a un solo archivo de identidad, al costo de que ese archivo mezcle dato curado y dato automático en la misma fila — aceptable acá porque las columnas están claramente separadas y documentadas, y el archivo entero se versiona (un diff de git muestra tanto "agregué un juego" como "BGG actualizó el rating", pero eso es información real, no ruido).

**Un identificador compartido por todas las fuentes (`bgg_id`, el id de BGG) en vez de matchear por nombre.** Cada fila de `bgg_data.csv` lleva `bgg_id` como primera columna — calculado una sola vez en el bootstrap (`extract_bgg_id` sobre `bgg_url` para la ludoteca, directo de la columna del dataset para los candidatos del top N) y nunca vuelto a derivar. La futura integración con `bosque_data.csv` (por nombre, no por id — Bosque Lúdico no expone un id de BGG) sigue este mismo criterio: `bosque_data.csv` también lleva `bgg_id` como primera columna aunque el join real sea por nombre, para que cualquier análisis posterior pueda cruzar ambos archivos sin tener que volver a resolver el id.

## Decisiones clave (y por qué)

- **JSON commiteado en vez de fetch a la API de Sheets en cada visita.** Sin esto: latencia extra en cada carga, sin rate limits propios (los de Google sí existen), sin API key/credential que guardar, y funciona en un host 100% estático (GitHub Pages no tiene backend). El costo es que el dato puede estar hasta un mes desactualizado — aceptable para un catálogo que no cambia todos los días; si hiciera falta más tiempo real, bajar el cron, no volver al fetch en vivo.
- **CSV export público en vez de la API oficial de Sheets.** Mientras el Sheet esté compartido "cualquiera con el enlace: lector", `.../export?format=csv&gid=...` no pide ninguna credencial. Si el Sheet pasara a ser privado, la alternativa es la API de Sheets con una service account (más setup, un secret que guardar en el repo).
- **Mapeo de columnas por texto del encabezado, no por posición/índice.** Agregar o reordenar una columna en el Sheet no rompe el build; una columna nueva sin regla se ignora en silencio (ver "Qué evitar" sobre el costo de ese silencio).
- **Falla ruidosa ante datos sospechosos.** El script corta con `sys.exit(1)` si parsea muy pocas filas o no encuentra la columna esperada, en vez de commitear un JSON vacío o a medio llenar. Un build que "funciona" pero pisa datos buenos con basura es peor que un build que no corre.
- **Lógica de enriquecimiento específica del dominio vive en el script, como constantes documentadas**, no desparramada en el frontend. En este proyecto es la resolución de links a BGG (`BGG_SEARCH_OVERRIDES`, `BGG_SKIP`): cada entrada tiene al lado, en un comentario, de dónde salió el override (en este caso, pistas que ya estaban a mano en la columna "Notas" del Sheet).
- **Enriquecimiento externo con columnas propias vs. de BGG en el mismo archivo, nunca mezcladas, y las propias siempre ganan.** `01_data_understanding/bgg/collect_bgg_data.py` solo pisa las columnas de BGG de cada fila (`puntaje_bgg`, `complejidad`, etc.); las columnas propias (`nombre`, `estado`, `modo`, `mi_puntaje`, `pros`, `cons`, `notas`) nunca se tocan en un refresh. La vía oficial (`--mode api`, `xmlapi2/thing`) está **bloqueada** hasta que BGG apruebe la aplicación registrada (hoy devuelve 401); mientras tanto corre automático contra un dataset placeholder de terceros (`--mode dummy`, default — ver el bullet de abajo sobre datasets públicos).
- **Reusar cookies de una sesión de navegador en un script aparte no es una alternativa real cuando el bot-detection correlaciona fingerprint de conexión, no solo el cookie.** Se probó explícitamente contra la página normal de BGG (reusando cookies de una sesión ya autenticada): aunque el `cf_clearance` se exportara recién pasado el challenge, `curl`/`urllib` seguían recibiendo un challenge nuevo (403) — Cloudflare lo ata al TLS/JA3 y al stack de headers real del navegador que lo generó, no solo al valor de la cookie. Antes de asumir que "cookies + requests" alcanza para reusar una sesión ya autenticada contra un anti-bot serio, probarlo con un caso real primero; si falla, no vale la pena perseguir evasión más sofisticada (spoof de fingerprint, etc.) — es la misma línea que no resolver CAPTCHAs, solo que con más ingeniería. Esa vía quedó descartada (no está ni en el código): la opción que sí funciona sin evadir nada es un dataset público de un tercero (ver abajo).
- **Columnas calculadas que antes eran fórmulas del Sheet se migran leyendo la fórmula real de la celda, nunca reinventándola.** Al sacar `puntaje_ajust_bgg` y `precio_calidad` del Sheet (para que solo queden ahí los datos que no son de BGG/Bosque Lúdico) se usó la API de Sheets (`get_spreadsheet` con `includeGridData` + `fields: ["...userEnteredValue.formulaValue"]`) para leer la fórmula tal cual estaba en varias celdas, no se adivinó "a ojo" mirando los valores. Esto destapó que el Sheet tenía **dos variantes de la misma fórmula conviviendo** (una con una constante hardcodeada en 53 filas, otra que recalculaba un desvío estándar en vivo en 6 filas, más 3 filas con el valor pegado a mano sin fórmula) — una inconsistencia invisible si solo se mira el resultado. Verificar el resultado del script nuevo contra el valor real de varias filas del Sheet (no solo "corre sin error") antes de darlo por bueno.
- **Ante una fórmula inconsistente entre filas de un Sheet, no elegir una variante en silencio: mostrarle las dos al usuario con el conteo real de filas de cada una y dejar que elija cuál es la oficial.** Es una decisión de negocio (qué constante usar), no una de implementación.
- **Cuando la fuente oficial de un dato está bloqueada (API que exige auth, sitio con bot-detection serio), buscar un dataset público de un tercero que ya hizo ese scraping/sync antes de resignarse a esperar o de evadir el bloqueo.** El top N de BGG sale de `github.com/beefsack/bgg-ranking-historicals`: un CSV diario, público, sin auth, mantenido por un tercero — no le pega a BGG en absoluto. Verificar que de verdad esté vivo (último commit reciente, no un repo abandonado) antes de depender de él, y documentar explícitamente que es una fuente de terceros, no la oficial, para que quede claro si algún día hay que migrar.
- **Al combinar "lo que el usuario cargó a mano" con "un dataset externo grande", el externo nunca duplica una entidad que ya está en el de mano: se deduplica por id estable (acá, el id de BGG extraído de la URL), nunca por nombre.** Dos títulos pueden diferir en mayúsculas/acentos/edición y el nombre nunca es una clave confiable para dedupe entre fuentes distintas.
- **Cuando una columna pedida no tiene una variable real en ninguna fuente disponible (acá, tamaño de caja: BGG no lo trackea en ningún campo, ni el dataset placeholder ni la API oficial), no inventar el dato ni dejar la columna vacía sin más: proponer un proxy a partir de variables que sí existen, calibrarlo contra casos de referencia reales conocidos, y declarar explícitamente que es una estimación, no un dato medido.** `transportable` se deriva de complejidad + duración (más reglas/partidas más largas → más componentes → caja más grande), con los umbrales ajustados a mano contra 3 juegos cuyo valor correcto ya se sabía de antemano (Pistas Cruzadas, La Isla Prohibida, Catan) — no se inventaron los umbrales a ojo, se resolvieron para que esos 3 casos dieran el resultado esperado. Sin las variables de entrada (acá, complejidad o duración ausentes), el proxy no tiene base: mejor `null` que una estimación sin fundamento.
- **Una columna categórica derivada que ya existe como campo editable a mano en la fuente curada (acá, `modo`) nunca se pisa: se deriva solo para las filas que lo tienen vacío.** Mismo principio que el fallback de enriquecimiento externo (más arriba), aplicado a una columna *calculada*, no solo a una que viene de otra fuente externa — la regla es "¿el humano ya decidió esto?", no "¿de dónde viene el valor nuevo?".
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

Cuando se suma una fuente externa nueva, el script que la recolecta/matchea va en `01_data_understanding/<fuente>/` (estructura CRISP-DM del repo: `bgg/`, `bosque_ludico/`), separado de `02_data_preparation/` que integra/construye. Generalizable: si una fuente cambia a un ritmo distinto de otra (en este proyecto, el *link* a una ficha de producto es estable pero el *precio* cambia seguido), conviene separarlas en dos scripts/pasos en vez de uno solo que recalcule todo cada vez — así un re-relevamiento de precio no vuelve a pagar el costo de resolver matches.

**Nombrar los datasets por la fuente, no por lo que hace el script que los generó:** `bosque_data.csv`/`bgg_data.csv` (no `bosque_ludico_precios.json` o similar). El nombre del archivo le dice a quien lo abre de dónde salió el dato sin tener que leer el script; el nombre del script le dice qué hace (`collect_bosque_precios.py`, `collect_bgg_data.py`). Mismo criterio para un script que solo integra fuentes ya recolectadas: se llama `integrate_data.py` (o similar), no `build_data.py` — "build" es ambiguo sobre si también recolecta. (Cuando una sola fuente activa ya trae todo lo que hace falta, como hoy acá, no existe ese script — `construct_data.py` lee la fuente directo; el día que haya una segunda fuente que integrar, ahí sí aparece.)

## Qué evitar

- Pegarle a la API de Google (o hacer `fetch` al Sheet) desde el cliente en cada visita — expone el id/gid del Sheet de forma prominente, agrega latencia, y si el Sheet se pone privado rompe el sitio en producción en vez de romper el próximo sync en CI.
- Mapear columnas por índice/posición: cualquier edición inocente del Sheet (reordenar, insertar una columna) corrompe silenciosamente los datos.
- Mezclar lógica de negocio hardcodeada (overrides, excepciones puntuales) sin un comentario que diga de dónde salió el dato — a los seis meses nadie se acuerda por qué "Memotest (Ruibal)" busca "Memory".
- Commitear igual aunque no haya cambios (ensucia el historial) o commitear datos a medias cuando el build detecta algo raro (preferir cortar con `exit 1` y dejar el `data.json` viejo tal cual).
- Que el frontend asuma que el fetch siempre funciona: sin un `.catch` que muestre algo legible, un `data.json` roto o un typo en la ruta deja la página en blanco sin pista de qué pasó.
