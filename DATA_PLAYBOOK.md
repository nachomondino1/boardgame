# Playbook de flujo de datos

Guía del patrón de datos usado en este proyecto (catálogo de juegos de mesa), pensada para pegar en un `CLAUDE.md` o en el prompt inicial de un proyecto nuevo que necesite algo parecido: un sitio estático, sin backend propio, cuyo contenido integra varias fuentes (una curada a mano, otras automatizadas).

**Nota sobre el Google Sheet:** este proyecto arrancó con un Sheet como fuente de verdad (la sección "Cómo adaptarlo a un proyecto nuevo" más abajo sigue siendo la guía genérica para eso, vale para otro proyecto que sí lo necesite). Acá se abandonó dos veces: primero el Sheet se reemplazó por un JSON (`mi_ludoteca.json`, ver "Cuándo un Sheet deja de valer la pena" en Decisiones clave), y ese JSON terminó en `data/01_data_understanding/mis_datos.jsonl` — el universo de juegos entero (identidad + Estado + lo que cargás vos a mano) vive hoy en un único archivo JSON Lines propio (un objeto por línea, ver "Decisiones clave" sobre por qué JSONL y no CSV), separado de `data/01_data_understanding/bgg_data.jsonl` (caché de BGG, 100% regenerable — ver "Las columnas que no vienen de BGG viven en su propio archivo").

## Filosofía

- **La fuente de verdad la edita un humano**, no en código ni en un admin panel — hoy `mis_datos.jsonl`, un archivo versionado en el repo que ningún script de refresh toca salvo que vos se lo pidas explícito; en otro proyecto, o en este al principio, puede ser un Google Sheet o un JSON aparte. Cero backend, cero base de datos propia.
- **El sitio nunca le pega a una API externa en runtime.** Hay un paso de build async (CI) que junta las fuentes y las convierte en un JSON estático, que es lo que el sitio realmente consume.
- **Cada sync es un commit.** El JSON vive versionado en el repo, así que un cambio en cualquier fuente se ve como un diff normal de git, y un dato roto se puede `git revert`.
- **El build es tolerante a cambios en la forma de la fuente curada a mano** (agregar/reordenar columnas o campos) pero intolerante a fallar en silencio (si algo sale muy mal, el script explota en vez de commitear datos vacíos o truncados).

## Arquitectura / flujo de datos

```
data/01_data_understanding/universo_juegos.jsonl   (commiteado, catálogo de identidad)
  bgg_id, nombre, bgg_url, link_cazagangas — "qué juegos conoce este
  repo", sin opinión tuya sobre ellos. Agregar un juego nuevo es: sumar
  una fila acá (a mano, o con search_new_game.py --add <id o nombre>,
  que resuelve bgg_id/nombre/bgg_url Y arma+verifica link_cazagangas
  solo — ver más abajo).
                            │
                            ▼  (bgg_id/nombre de cada fila)
01_data_understanding/collect_initial_data/
  search_new_game.py vive acá, un nivel arriba de bgg/ y cazagangas/,
  porque orquesta las dos carpetas — no es parte de ninguna.
  collect_initial_data/bgg/ (bgg_common.py + 3 scripts)
  dataset público de terceros, Hugging Face (ver "Decisiones clave")
  initialize_bgg_data.py: bootstrap único (universo_juegos.jsonl no
  existe todavía) — top N del ranking + ludoteca, identidad nomás.
  search_new_game.py (uso normal, lo que corre el cron sin --add):
  agrega a bgg_data.jsonl solo los bgg_id de universo_juegos.jsonl que
  todavía no tienen fila — nunca reescribe una fila existente.
  --add <id o nombre> (un juego a la vez, nunca en el cron): además de
  sumar la fila a universo_juegos.jsonl, en la misma corrida arma un
  slug best-effort para Cazagangas y lo verifica con un HEAD real
  (collect_initial_data/cazagangas/cazagangas_common.py) — si da 200,
  carga link_cazagangas + fila en cazagangas_data.jsonl solo; si no,
  deja link_cazagangas vacío para cargar a mano — y agrega una fila
  stub a mis_datos.jsonl (bgg_id/nombre nomás, el resto vacío
  esperando tu criterio).
  modify_values.py / extract_new_fields.py: edición manual de campos
  puntuales / columnas nuevas sobre filas ya existentes — mismo
  principio de upsert, nunca reescritura completa.
                            │
                            ▼
      data/01_data_understanding/bgg_data.jsonl   (commiteado, caché de BGG:
        anio, descripcion, disenador, edad_min, jug_min/max, jug_best_min/max,
        duracion_min/max, complejidad, puntaje_bgg, reviews_bgg, ranking_bgg,
        mecanicas, categorias — una fila que falta es regenerable
        (search_new_game.py la completa); una fila que ya existe nunca se
        reescribe sola, así una corrección manual no se pierde)

data/01_data_understanding/cazagangas_data.jsonl   (commiteado, status HTTP verificado)
  bgg_id, nombre, status_http, fecha_chequeado — una fila por juego con
  link_cazagangas cargado. check_cazagangas_links.py re-verifica en
  lote lo ya cargado (manual, --limit N); search_new_game.py --add
  resuelve y verifica el de un juego nuevo en el momento de agregarlo.

data/01_data_understanding/mis_datos.jsonl   (commiteado, 100% manual, lo cargás vos)
  bgg_id, nombre, estado, modo, transportable, mi_puntaje, pros, cons,
  notas — tu criterio, nunca inferido. search_new_game.py --add es la
  única excepción que lo escribe, y solo para crear la fila stub
  (bgg_id/nombre) de un juego nuevo; integrate_data.py lo lee. Si se
  borra, se pierde tu trabajo: no es regenerable de ninguna fuente.

      data/01_data_understanding/grupos.json ─────┐  (curado a mano, ver "Agrupar variantes/expansiones")
      data/01_data_understanding/cazagangas_data.jsonl ─┤  (check_cazagangas_links.py, manual — ver más abajo)
                            │
      mis_datos.jsonl + universo_juegos.jsonl + bgg_data.jsonl + grupos.json
      + cazagangas_data.jsonl
                            ▼
      02_data_preparation/integrate_data.py
        base = mis_datos.jsonl; suma universo_juegos.jsonl/bgg_data.jsonl
        por bgg_id (nombre como fallback), y grupos.json/cazagangas_data.jsonl
        por nombre — sin tipar ni calcular nada (eso es trabajo de
        construct_data.py). Las últimas cuatro son opcionales: si no
        existen, esos campos quedan en null
                            ▼
      data/02_data_preparation/integrated_data.jsonl   (intermedio del build, gitignored:
        se regenera siempre de archivos ya commiteados, no se edita a mano)
                            ▼
      02_data_preparation/construct_data.py
        calcula duracion, modo, puntaje_ajust_bgg, precio_calidad
        (derivadas, no vienen de ninguna fuente — ver README.md
        "Columnas calculadas"); transportable/bgg_url/link_cazagangas/
        grupo/cazagangas_status pasan de largo tal cual (ya vienen resueltos)
                            ▼
      docs/data/data.json   (commiteado al repo, fuente de verdad del sitio)
                            ▲
        │  .github/workflows/sync-data.yml: cron mensual + workflow_dispatch manual
        │  corre search_new_game.py + integrate_data.py + construct_data.py,
        │  commitea lo que cambió, pushea a main ("[skip ci]" para no
        │  re-triggerear otros workflows)
                            ▼
      push a main → redeploy automático de GitHub Pages
                            ▼
      Frontend vanilla JS: <link rel="preload" href="data/data.json" as="fetch" crossorigin>
                            + fetch("data/data.json") al cargar la página

[PAUSADO] 01_data_understanding/collect_initial_data/bosque_ludico/: resolve_bosque_links.py
+ collect_bosque_precios.py ya funcionan (mis_datos.jsonl → links.json →
bosque_data.json, primera columna bgg_id) pero nada los corre activamente
ni los integra todavía — ver "Qué evitar"/Pendiente. A diferencia de
cazagangas_data.jsonl, bosque_data.json ni siquiera está commiteado (ver
.gitignore): el día que se retome, pasa por el mismo camino (su propio
collect_*, un merge en integrate_data.py).
```

Nadie en el camino del usuario final toca ninguna API externa: para quien visita el sitio, `data/data.json` es un archivo estático más, servido por GitHub Pages.

**01 (entender/recolectar) nunca depende de un output de 02 (integrar/construir).** `integrate_data.py` lee `mis_datos.jsonl`/`bgg_data.jsonl`/`grupos.json`/`cazagangas_data.jsonl` directo (outputs de 01), nunca al revés — y `construct_data.py` lee la salida de `integrate_data.py`, nunca las fuentes crudas directo (así cada paso tiene una sola fuente de verdad: 01 recolecta, `integrate_data.py` junta, `construct_data.py` calcula).

**El universo de candidatos ya no lo cura una persona a mano (la vieja columna Watchlist del Sheet): lo arma automáticamente "top N de un ranking público menos lo que ya tenés", con la opción de sumar juegos puntuales con `--add`.** Esto es deliberado — mantener a mano una lista de "juegos que me interesan" no escala a miles de candidatos, y el ranking de BGG ya hace ese trabajo de curación/orden inicial; `--add` cubre el caso puntual ("quiero este juego en el análisis aunque no esté en el top N"). El costo es volumen (el "¿Cuál comprar?" del sitio puede mostrar hasta ~1000 tarjetas); los datos por candidato están casi completos (~98%, contra un dataset placeholder de 2025 — ver "Decisiones clave"), salvo precio, que depende de una integración con Bosque Lúdico que todavía no existe.

**Identidad + enriquecimiento externo en un único archivo, no en piezas separadas que haya que combinar en cada build.** Versiones anteriores de este pipeline separaban "quién tenés" (un JSON/Sheet aparte) de "qué sabe BGG de cada uno" (un caché por id, regenerado en el build). Fusionarlos en un solo CSV con columnas propias vs. columnas de fuente externa (nunca se pisan entre sí, ver más arriba) simplifica el pipeline a un solo archivo de identidad, al costo de que ese archivo mezcle dato curado y dato automático en la misma fila — aceptable acá porque las columnas están claramente separadas y documentadas, y el archivo entero se versiona (un diff de git muestra tanto "agregué un juego" como "BGG actualizó el rating", pero eso es información real, no ruido).

**Un identificador compartido por todas las fuentes (`bgg_id`, el id de BGG) en vez de matchear por nombre.** Cada fila de `bgg_data.jsonl` lleva `bgg_id` como primera columna — calculado una sola vez en el bootstrap (`extract_bgg_id` sobre `bgg_url` para la ludoteca, directo de la columna del dataset para los candidatos del top N) y nunca vuelto a derivar. La futura integración con `bosque_data.csv` (por nombre, no por id — Bosque Lúdico no expone un id de BGG) sigue este mismo criterio: `bosque_data.csv` también lleva `bgg_id` como primera columna aunque el join real sea por nombre, para que cualquier análisis posterior pueda cruzar ambos archivos sin tener que volver a resolver el id.

## Decisiones clave (y por qué)

- **JSON Lines (un objeto por línea) en vez de CSV para la fuente curada a mano, cuando alguna columna trae texto libre con saltos de línea reales.** `bgg_data.jsonl` tiene una columna (`descripcion`) con texto de BGG que incluye `\n` reales adentro: en CSV eso hace que una sola fila se desparrame en decenas de líneas visuales en el editor de texto (aunque el parser la siga leyendo bien como una fila), haciendo casi imposible ubicar/editar a mano el campo de un juego puntual sin una herramienta de CSV dedicada. En JSON ese mismo salto de línea se escapa como `\n` literal dentro del string, así que cada fila queda garantizada en una sola línea física del archivo — buscable por nombre con Ctrl+F en cualquier editor de texto plano, sin extensiones. El costo es editar `{"clave": "valor", ...}` en vez de un valor entre comas, algo peor para cambios de una sola celda pero sin alternativa real una vez que el contenido de una columna deja de ser "una celda corta". La señal para este cambio no es "¿CSV es incómodo en general?" sino "¿alguna columna de texto libre tiene saltos de línea reales que rompen la alineación de una fila = una línea?" — si ninguna columna los tiene, CSV sigue siendo más simple de editar a mano (sobre todo en una planilla) y no hace falta este cambio.

- **JSON commiteado en vez de fetch a la API de Sheets en cada visita.** Sin esto: latencia extra en cada carga, sin rate limits propios (los de Google sí existen), sin API key/credential que guardar, y funciona en un host 100% estático (GitHub Pages no tiene backend). El costo es que el dato puede estar hasta un mes desactualizado — aceptable para un catálogo que no cambia todos los días; si hiciera falta más tiempo real, bajar el cron, no volver al fetch en vivo.
- **CSV export público en vez de la API oficial de Sheets.** Mientras el Sheet esté compartido "cualquiera con el enlace: lector", `.../export?format=csv&gid=...` no pide ninguna credencial. Si el Sheet pasara a ser privado, la alternativa es la API de Sheets con una service account (más setup, un secret que guardar en el repo).
- **Mapeo de columnas por texto del encabezado, no por posición/índice.** Agregar o reordenar una columna en el Sheet no rompe el build; una columna nueva sin regla se ignora en silencio (ver "Qué evitar" sobre el costo de ese silencio).
- **Falla ruidosa ante datos sospechosos.** El script corta con `sys.exit(1)` si parsea muy pocas filas o no encuentra la columna esperada, en vez de commitear un JSON vacío o a medio llenar. Un build que "funciona" pero pisa datos buenos con basura es peor que un build que no corre.
- **Lógica de enriquecimiento específica del dominio vive en el script, como constantes documentadas**, no desparramada en el frontend. En este proyecto es la resolución de links a BGG (`BGG_SEARCH_OVERRIDES`, `BGG_SKIP`): cada entrada tiene al lado, en un comentario, de dónde salió el override (en este caso, pistas que ya estaban a mano en la columna "Notas" del Sheet).
- **Enriquecimiento externo con columnas propias vs. de BGG, nunca mezcladas, y las propias siempre ganan.** Sin `--add`, `01_data_understanding/collect_initial_data/search_new_game.py` solo completa `data/01_data_understanding/bgg_data.jsonl` (`puntaje_bgg`, `complejidad`, etc.) para los `bgg_id` que todavía no tienen fila; las columnas propias (`nombre`, `estado`, `modo`, `transportable`, `mi_puntaje`, `pros`, `cons`, `notas`) viven en `data/01_data_understanding/mis_datos.jsonl`, un archivo que ninguno de los scripts de BGG abre para escribir — separadas en dos archivos, no solo por convención dentro de uno (ver "Las columnas que no vienen de BGG viven en su propio archivo" más abajo, con el por qué del cambio). La vía oficial (`--mode api`, `xmlapi2/thing`) está **bloqueada** hasta que BGG apruebe la aplicación registrada (hoy devuelve 401); mientras tanto corre automático contra un dataset placeholder de terceros (`--mode dummy`, default — ver el bullet de abajo sobre datasets públicos).
- **Un caché "100% regenerable" deja de serlo en cuanto alguien lo edita a mano — separar "regenerar desde cero" de "completar lo que falta".** `bgg_data.jsonl` se documentó originalmente como "se reescribe entero en cada corrida, si se borra se reconstruye sola" (ver más abajo, "Las columnas que no vienen de BGG..."), razonamiento válido mientras nadie tocara una fila individual. En la práctica el usuario empezó a corregir a mano campos puntuales (ej. `jug_min`/`jug_max` con el dato de "Community" de la ficha en vez del de caja que trae el dataset placeholder), y el `refresh` mensual del cron se los pisaba sin aviso en la siguiente corrida — el dataset de origen (snapshot 2025 de Hugging Face) nunca se entera de esa corrección. La separación que lo resuelve: un script de bootstrap que sí reescribe todo (se corre una sola vez, `initialize_bgg_data.py`) vs. un script de uso normal que solo hace upsert — agrega filas para los `bgg_id` que faltan, nunca reescribe una fila que ya existe (`search_new_game.py`, que reemplazó al "refresh"; `modify_values.py`/`extract_new_fields.py` para ediciones puntuales). La señal para aplicar este patrón en otro proyecto: en cuanto un caché que se regenera automático empieza a recibir correcciones manuales de verdad (no solo en teoría), "regenerar todo" deja de ser seguro y hace falta separar "traer lo que falta" de "reconstruir desde cero".
- **Reusar cookies de una sesión de navegador en un script aparte no es una alternativa real cuando el bot-detection correlaciona fingerprint de conexión, no solo el cookie.** Se probó explícitamente contra la página normal de BGG (reusando cookies de una sesión ya autenticada): aunque el `cf_clearance` se exportara recién pasado el challenge, `curl`/`urllib` seguían recibiendo un challenge nuevo (403) — Cloudflare lo ata al TLS/JA3 y al stack de headers real del navegador que lo generó, no solo al valor de la cookie. Antes de asumir que "cookies + requests" alcanza para reusar una sesión ya autenticada contra un anti-bot serio, probarlo con un caso real primero; si falla, no vale la pena perseguir evasión más sofisticada (spoof de fingerprint, etc.) — es la misma línea que no resolver CAPTCHAs, solo que con más ingeniería. Esa vía quedó descartada (no está ni en el código): la opción que sí funciona sin evadir nada es un dataset público de un tercero (ver abajo).
- **Columnas calculadas que antes eran fórmulas del Sheet se migran leyendo la fórmula real de la celda, nunca reinventándola.** Al sacar `puntaje_ajust_bgg` y `precio_calidad` del Sheet (para que solo queden ahí los datos que no son de BGG/Bosque Lúdico) se usó la API de Sheets (`get_spreadsheet` con `includeGridData` + `fields: ["...userEnteredValue.formulaValue"]`) para leer la fórmula tal cual estaba en varias celdas, no se adivinó "a ojo" mirando los valores. Esto destapó que el Sheet tenía **dos variantes de la misma fórmula conviviendo** (una con una constante hardcodeada en 53 filas, otra que recalculaba un desvío estándar en vivo en 6 filas, más 3 filas con el valor pegado a mano sin fórmula) — una inconsistencia invisible si solo se mira el resultado. Verificar el resultado del script nuevo contra el valor real de varias filas del Sheet (no solo "corre sin error") antes de darlo por bueno.
- **Ante una fórmula inconsistente entre filas de un Sheet, no elegir una variante en silencio: mostrarle las dos al usuario con el conteo real de filas de cada una y dejar que elija cuál es la oficial.** Es una decisión de negocio (qué constante usar), no una de implementación.
- **Cuando la fuente oficial de un dato está bloqueada (API que exige auth, sitio con bot-detection serio), buscar un dataset público de un tercero que ya hizo ese scraping/sync antes de resignarse a esperar o de evadir el bloqueo.** El top N de BGG sale de `github.com/beefsack/bgg-ranking-historicals`: un CSV diario, público, sin auth, mantenido por un tercero — no le pega a BGG en absoluto. Verificar que de verdad esté vivo (último commit reciente, no un repo abandonado) antes de depender de él, y documentar explícitamente que es una fuente de terceros, no la oficial, para que quede claro si algún día hay que migrar.
- **Al combinar "lo que el usuario cargó a mano" con "un dataset externo grande", el externo nunca duplica una entidad que ya está en el de mano: se deduplica por id estable (acá, el id de BGG extraído de la URL), nunca por nombre.** Dos títulos pueden diferir en mayúsculas/acentos/edición y el nombre nunca es una clave confiable para dedupe entre fuentes distintas.
- **Cuando una columna pedida no tiene una variable real en ninguna fuente disponible, no asumir que hay que inventar un proxy calculado — primero preguntar si el usuario prefiere cargarla a mano.** Se probó con `transportable` (tamaño de caja; BGG no lo trackea en ningún campo) un proxy calculado a partir de complejidad + duración, calibrado contra 3 casos de referencia conocidos (Pistas Cruzadas, La Isla Prohibida, Catan). El usuario lo descartó: prefirió carga 100% manual (columna propia más, como `mi_puntaje`/`pros`/`cons`), porque "entra en una mochila" es un juicio que él ya tiene y un proxy puede acertar los 3 casos de calibración y fallar en el resto. Lección: un proxy calibrado contra pocos casos de referencia es una apuesta razonable cuando el dato es costoso de cargar a mano para *muchas* filas (acá, todo el universo de BGG); cuando lo que hace falta es una columna manual para un puñado de juegos que el usuario ya conoce bien (su propia ludoteca), cargarla a mano directamente es más simple y más confiable que cualquier heurística — no reemplaza el juicio del dueño del dato por una fórmula sin que lo pida.
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

Para relevar precios de El Bosque Lúdico (`01_data_understanding/collect_initial_data/bosque_ludico/resolve_bosque_links.py`) hizo falta encontrar la ficha de producto de cada juego sin usar su buscador: su `robots.txt` tiene `Disallow: /search/` explícito. La solución, generalizable a cualquier sitio en la misma situación:

- **Usar el sitemap del sitio (`sitemap.xml` / `sitemap.xml.gz`, declarado en `robots.txt` bajo `Sitemap:`) como listado completo, en vez del buscador.** El sitemap está pensado para ser indexado — nunca está en `Disallow` — y en un solo request trae todas las URLs de producto, que después se matchean por texto en el propio script, sin tocarle más al sitio.
- **Matchear por contención de palabras completas, no por ratio de caracteres (`difflib.SequenceMatcher` crudo).** Un ratio de similitud de string completo da falsos positivos fuertes con nombres cortos (p. ej. "Codenames" vs. slug "cometas" salía con ratio 0.62): dos nombres cortos comparten letras por azar. La regla que funcionó: normalizar y partir en palabras, exigir que (casi) todas las palabras del término buscado aparezcan como palabra completa en el slug candidato (no como substring de letras), y recién ahí aceptar el match. Tiendanube (y seguramente otras plataformas) le agrega un sufijo random de pocos caracteres a los slugs que colisionan (p. ej. `ark-nova-v2ui5`): conviene detectar y descartar ese sufijo (último token corto con al menos un dígito) antes de normalizar, para no ensuciar el matching.
- Mismo patrón que la resolución de links a BGG: un override a mano (`BOSQUE_SEARCH_OVERRIDES`/`BOSQUE_SKIP`, análogo a `BGG_SEARCH_OVERRIDES`/`BGG_SKIP`) para los casos que el matching automático no resuelve bien, documentado con un comentario de por qué.
- Si un sitio no público bloquea agresivamente (Cloudflare challenge, 401 sin app aprobada, etc.) y no tiene sitemap ni vía oficial, aplica lo mismo que ya está documentado para BGG en "Decisiones clave": no vale la pena perseguir evasión de bot-detection, es la misma familia de problema que resolver un CAPTCHA a mano.

## Separar código (01/02) de datos (`/data`), y una carpeta por fuente solo cuando el código lo justifica

**El código (recolectar, transformar) y los datos que ese código lee/escribe viven en lugares distintos del repo.** `/data` en la raíz es *solo* datasets (`.jsonl`, `.csv`, lo que sea) — nunca un `.py`. El código que los produce/consume vive en la estructura CRISP-DM de siempre: recolección cruda en `01_data_understanding/collect_initial_data/`, transformación/integración en `02_data_preparation/`. Esto es deliberado y separado de la regla de abajo: un script no se muda de carpeta porque el dataset que produce se mudó — `construct_data.py` sigue en `02_data_preparation/` aunque lea y escriba en `/data`.

**Un script de recolección va en su propia subcarpeta dentro de `collect_initial_data/` solo si tiene más de un archivo** (varios scripts, overrides, salidas intermedias — como `bosque_ludico/`, `cazagangas/` (`cazagangas_common.py` + `check_cazagangas_links.py`), y `bgg/` (`bgg_common.py` + `initialize_bgg_data.py`/`modify_values.py`/`extract_new_fields.py`): fue una sola fuente, `collect_bgg_data.py`, hasta que separar "bootstrap" de "editar un campo" de "sumar una columna" se volvió necesario para que un refresh dejara de pisar ediciones manuales, ver más abajo). Una fuente con un solo script va directo dentro de `collect_initial_data/`, sin subcarpeta propia — una carpeta para un solo archivo es anidamiento que no paga su costo. **Un script que orquesta varias fuentes (no pertenece a ninguna) va un nivel arriba, al lado de las carpetas que orquesta, nunca adentro de una de ellas** — `search_new_game.py` agrega un juego a `bgg/` + `cazagangas/` + `mis_datos.jsonl` en un solo `--add`, así que vive directo en `collect_initial_data/`, aunque internamente importe `bgg_common.py` y `cazagangas_common.py` como librerías. Generalizable más allá de esto: si una fuente cambia a un ritmo distinto de otra (en este proyecto, el *link* a una ficha de producto es estable pero el *precio* cambia seguido), conviene separar en dos scripts/pasos en vez de uno solo que recalcule todo cada vez — así un re-relevamiento de precio no vuelve a pagar el costo de resolver matches.

**Nombrar los datasets por la fuente, no por lo que hace el script que los generó:** `data/bosque_data.csv`/`data/01_data_understanding/bgg_data.jsonl`/`data/01_data_understanding/cazagangas_data.jsonl` (no `bosque_ludico_precios.json` o similar). El nombre del archivo le dice a quien lo abre de dónde salió el dato sin tener que leer el script; el nombre del script le dice qué hace (`collect_bosque_precios.py`, `collect_bgg_data.py`, `check_cazagangas_links.py`). Un script que solo integra fuentes ya recolectadas se llama `integrate_data.py` (no `build_data.py` — "build" es ambiguo sobre si también recolecta): acá empezó a existir recién cuando hubo una segunda fuente real que integrar (`grupos.json`, después `cazagangas_data.jsonl`) — con una sola fuente activa no hacía falta, `construct_data.py` la leía directo.

## Las columnas que no vienen de BGG viven en su propio archivo (`data/01_data_understanding/mis_datos.jsonl`)

`bgg_data.jsonl` arrancó siendo dos cosas a la vez: el universo de juegos (identidad + Estado, que cargás vos) y el caché de datos de BGG (que se refresca solo) — un humano mandaba sobre un grupo de columnas de la fila, BGG sobre el resto, documentado con una constante (`OWNED_FIELDS` vs `BGG_FIELDS`) pero conviviendo en el mismo archivo. Funcionaba porque `collect_bgg_data.py` nunca pisaba `OWNED_FIELDS` en un refresh — pero "funciona si el script se porta bien" es más frágil que "no puede pasar": un bug en el refresh, un `write_jsonl` con el `dict` armado mal, cualquier cosa que toque el archivo entero, pone en riesgo datos irreemplazables (`mi_puntaje`, `pros`, `cons`, `notas`) junto a datos 100% regenerables (`puntaje_bgg`, `descripcion`, etc.).

**Separarlos en dos archivos saca esa fragilidad por diseño, no por disciplina:** `data/01_data_understanding/mis_datos.jsonl` (antes `OWNED_FIELDS`: `bgg_id`, `nombre`, `estado`, `bgg_url`, `modo`, `transportable`, `mi_puntaje`, `pros`, `cons`, `notas`) es ahora EL universo — la única fuente de qué juegos existen, y lo único que un refresh de BGG no puede tocar porque ni siquiera abre ese archivo para escribirlo. `data/01_data_understanding/bgg_data.jsonl` queda como caché puro (antes `BGG_FIELDS`, join por `bgg_id`): si se borra entero, el próximo refresh lo reconstruye solo a partir de los `bgg_id` de `mis_datos.jsonl` — no hay forma de perder nada al tocarlo. `integrate_data.py` pasa a tener `mis_datos.jsonl` como base (no `bgg_data.jsonl`): un juego sin bgg_id (o sin match en el dataset) igual aparece en `data.json`, con las columnas de BGG en `null`.

Efecto colateral en `collect_bgg_data.py`: `--set-estado` deja de tocar el dataset de BGG para nada (antes recorría `enrich()` igual, ahora es una edición pura de `mis_datos.jsonl`), y el "Refresh" nunca vuelve a escribir `mis_datos.jsonl` en absoluto — antes lo reescribía entero cada vez (con el `dict` reordenado por `ALL_FIELDS`), ahora ni lo abre en modo escritura.

**Generalizable: cuando un archivo mezcla "lo que edita un humano" con "lo que regenera un script", separarlos en cuanto el segundo volumen empiece a justificar su propio archivo** (acá, agregar `check_cazagangas_links.py`/`grupos.json` como nuevas fuentes a integrar hizo evidente el patrón: por qué sí separar esas dos en archivos propios, y la fuente de BGG mezclada en el mismo archivo que lo manual, no). No hace falta hacerlo desde el día 1 — mientras una sola fuente automatizada exista y el archivo sea chico, la separación es ceremonia de más; se vuelve la opción correcta cuando el archivo mezclado empieza a ser un riesgo real de perder algo irreemplazable.

**Segunda vuelta de tuerca: separar "identidad" (bgg_id, nombre, bgg_url, link_cazagangas) de "tu opinión" (estado, modo, transportable, mi_puntaje, pros, cons, notas), aunque las dos sean manuales/semi-manuales.** `mis_datos.jsonl` seguía mezclando dos cosas de naturaleza distinta: identidad del juego (qué es, dónde está — bgg_url, y después link_cazagangas) y tu relación con él (qué pensás, en qué estado está). La señal para separar de nuevo: `check_cazagangas_links.py` necesitaba saber la URL de Cazagangas de cada juego para verificarla, y esa URL no tiene nada que ver con si el juego está en tu Watchlist o no — forzar a ese script a leer `mis_datos.jsonl` (con estado adentro) solo para sacar `nombre` lo acoplaba a un archivo que es 100% tuyo sin necesidad. `data/01_data_understanding/universo_juegos.jsonl` (`bgg_id`, `nombre`, `bgg_url`, `link_cazagangas`) pasa a ser el catálogo de identidad — lo que collect_bgg_data.py y check_cazagangas_links.py necesitan para saber qué buscar, sin tocar nunca `mis_datos.jsonl`. `mis_datos.jsonl` se achica a solo tu opinión/estado (sigue con `bgg_id` y `nombre` para que un humano pueda abrirlo y entender cada fila sin cruzar con otro archivo, y como fallback de join cuando `bgg_id` está vacío). Agregar un juego nuevo pasa a ser dos pasos independientes: sumarlo a `universo_juegos.jsonl` (identidad, por `--add` o a mano) y, aparte, cuando quieras, agregarlo a `mis_datos.jsonl` con el estado que corresponda — ninguno de los dos pasos depende del otro.

## Agrupar variantes/expansiones del mismo sistema de juego (`data/01_data_understanding/grupos.json`)

En "¿Cuál comprar?" varias cajas de un mismo sistema (ej. las 7 de Unmatched, las 5 de Ticket to Ride) saturaban la grilla. No hay forma confiable de detectar esto automático: ni el prefijo antes de `:` del nombre ni la "family" de BGG alcanzan, porque agrupan por **marca/tema**, no por si es el mismo diseño — "Star Wars: Rebellion" y "Star Wars: X-Wing" comparten prefijo y BGG family pero son juegos completamente distintos; "Roll Through the Ages" y "Through the Ages" comparten casi el nombre entero y son de autores distintos. Mismo problema con `boardgameimplementation`/`boardgameexpansion` de BGG: están pensados para expansiones "de verdad" (reglas que se suman a un juego base), no para "mismo motor, otra caja standalone" (que es el caso típico acá: Unmatched, Ticket to Ride, Century, Azul).

Solución: heurística de prefijo + jugadores solo como **generador de candidatos** (nunca auto-aplicado), curados a mano en `data/01_data_understanding/grupos.json` (junto al resto de los datasets, no en `docs/` — es un input del build, no algo que el sitio pida por su cuenta) — `{ "grupos": [{ "nombre": "Unmatched", "juegos": ["Unmatched Game System", "Unmatched: Cobble & Fog", ...] }] }`, matcheado por el campo `nombre` exacto de `mis_datos.jsonl`. El criterio para meter dos juegos en el mismo grupo: **mismo motor/sistema de juego** (jugarías uno u otro, no los dos; comprar la otra caja no te hace falta si ya tenés una), no "mismo diseñador" ni "misma marca/IP" ni "edición revisada con cambios de diseño real" (eso se deja separado, como pediste con Codenames/Codenames: Duet).

`integrate_data.py` resuelve el grupo de cada juego y lo graba como el campo `grupo` (nombre del grupo, o `null`); `construct_data.py` lo pasa de largo hasta `docs/data/data.json` — el sitio no pide un segundo archivo aparte ni resuelve nada en el cliente, solo lee ese campo. `collapseGrupos` en `shared.js` colapsa en la grilla, usando ese campo, solo la primera aparición de cada grupo (ya ordenada por el sort activo) y cuelga el resto como variantes expandibles dentro de esa tarjeta — no se pierde ningún juego, solo se oculta por default.

Al sumar un juego nuevo que sea "otra caja del mismo sistema" de algo que ya está en `grupos.json`, agregarlo a mano a ese grupo (no hay automatización, es a propósito) y correr `integrate_data.py` + `construct_data.py` de nuevo para que el campo `grupo` se actualice en `data.json`.

## Link a una tienda sin resolver nada: construir la URL por convención y verificar el código HTTP real una sola vez (`data/01_data_understanding/cazagangas_data.jsonl`)

A diferencia de El Bosque Lúdico (que necesita matchear por texto contra un sitemap, ver "Resolver un link a producto..." más arriba), Cazagangas publica sus fichas en una URL predecible a partir del nombre (`/juego/<slug>`). Primera versión: el frontend armaba ese slug al vuelo y mostraba el link igual, a ver qué pasaba ("si no existe, da 404 y lo veo yo"). Segunda versión: `check_cazagangas_links.py` generaba el mismo slug del lado Python y lo verificaba con un `HEAD` real. **Versión actual (esta): ni el frontend ni `check_cazagangas_links.py` generan ninguna URL — `link_cazagangas` se carga a mano en `data/01_data_understanding/universo_juegos.jsonl`** (junto a `bgg_id`/`nombre`/`bgg_url`, ver "Las columnas que no vienen de BGG viven en su propio archivo"), y `check_cazagangas_links.py` solo le pega un `HEAD` a lo que ya está cargado ahí, guardando el código HTTP (`200`/`404`/`error`) en `data/01_data_understanding/cazagangas_data.jsonl`. Sacar el slugify evita mantener el mismo algoritmo sincronizado en dos lugares (antes Python + JS) y evita adivinar: si el link está mal, se corrige una vez en `universo_juegos.jsonl`, no en la lógica de armado. El frontend sigue sin adivinar nada: `shared.js` solo muestra el link cuando `cazagangas_status === "200"`.

Igual que `collect_bosque_precios.py`, es un chequeo de red por juego (hasta ~1000 candidatos, los que tengan `link_cazagangas` cargado en `universo_juegos.jsonl` — ya no filtra por estado, porque ese campo ni vive en el mismo archivo): corre con `--limit` para ir de a tandas y mergea por nombre contra corridas anteriores, sin perder lo ya chequeado. A diferencia de Bosque Lúdico, esto **no está pausado**: es una fuente activa, su output se commitea (no va en `.gitignore`) y `integrate_data.py` la lee en cada build — pero el chequeo en sí (`check_cazagangas_links.py`) no corre en el cron de `sync-data.yml`, se corre a mano cuando hace falta refrescar, por el mismo motivo que Bosque Lúdico: ~1000 requests de red a un tercero es demasiado para colgarlo de un cron automático sin supervisión.

## Qué evitar

- Pegarle a la API de Google (o hacer `fetch` al Sheet) desde el cliente en cada visita — expone el id/gid del Sheet de forma prominente, agrega latencia, y si el Sheet se pone privado rompe el sitio en producción en vez de romper el próximo sync en CI.
- Mapear columnas por índice/posición: cualquier edición inocente del Sheet (reordenar, insertar una columna) corrompe silenciosamente los datos.
- Mezclar lógica de negocio hardcodeada (overrides, excepciones puntuales) sin un comentario que diga de dónde salió el dato — a los seis meses nadie se acuerda por qué "Memotest (Ruibal)" busca "Memory".
- Commitear igual aunque no haya cambios (ensucia el historial) o commitear datos a medias cuando el build detecta algo raro (preferir cortar con `exit 1` y dejar el `data.json` viejo tal cual).
- Que el frontend asuma que el fetch siempre funciona: sin un `.catch` que muestre algo legible, un `data.json` roto o un typo en la ruta deja la página en blanco sin pista de qué pasó.
