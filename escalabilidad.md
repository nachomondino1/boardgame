# Escalabilidad

Notas sobre cómo llevar el proyecto de "mi ludoteca" a "la ludoteca de cualquiera". Documento vivo: se agrega a medida que aprendemos.

## 1. Idea central

Separar los datos en dos grupos:

| Grupo | Qué es | Quién lo actualiza | Se comparte entre usuarios |
|---|---|---|---|
| **Catálogo** | Datos de BGG de todos los juegos (top 5000 + descubiertos) | Yo, con `sync_data.sh` | Sí |
| **Datos de usuario** | Su colección de BGG: `own`, `prevowned`, `wanttobuy` y su `rating` (opcional) | Cada usuario, en BGG | No |

La colección de BGG es pública salvo que el usuario la oculte, así que alcanza con el username. Con eso se cruza contra el catálogo y se arma Ludoteca / Hoy / Comprar.

Hoy el proyecto **no usa partidas**: todo sale de la colección (Estado y puntaje propio) más el catálogo. Por eso no hay datos extra que pedirle a otro usuario. Un juego del catálogo que no está en su colección queda como Watchlist, igual que hoy.

`wanttobuy` es opcional para el usuario: sin eso, "¿Cuál comprar?" sigue funcionando con el Watchlist del catálogo.

## 2. Camino por etapas

1. **MVP sin login.** Una página donde se ingresa un username de BGG y se muestra su ludoteca cruzada con el catálogo. Valida la idea con poca infraestructura.
2. **Backend mínimo con caché** de colecciones (refresco manual o diario).
3. **Login** recién cuando haya algo que guardar por usuario (preferencias, por ejemplo). Si todo sale de la colección en BGG, puede que no haga falta nunca. No guardar contraseñas propias: usar un servicio de auth (Supabase Auth, Firebase Auth, Clerk) o magic link por mail.

### Caché de la colección (idea del MVP)

Es posible. Dos variantes:

- **En el navegador del usuario** (`localStorage`): se guarda el username y la última colección bajada, y se refresca pasado un tiempo. Simple y sin base de datos, pero cada visitante dispara su propia llamada.
- **En un servidor** (función serverless + tabla): `bgg_username → colección + fecha de descarga`. Si la colección es reciente se sirve del caché; si no, se vuelve a pedir a BGG. Evita golpear a BGG de más.

Probable que haga falta el servidor igual: la API de BGG pide token, y ese token no puede quedar expuesto en el JS del navegador. Además hay que verificar si BGG permite llamadas directas desde el navegador (CORS); no lo comprobé. Un proxy chico (Cloudflare Worker, Netlify/Vercel function) resuelve las dos cosas.

## 3. Riesgos

### 3.1 Dependencia de BGG (el más grande)
- **Rate limits** de la API.
- **Colección en cola:** al pedir una colección BGG a veces responde "202, la estoy preparando" y hay que reintentar.
- **Un usuario nuevo = una llamada a BGG.** Hay que cachear y refrescar con intervalo razonable, no en cada visita.
- Si BGG cambia las reglas o cierra el acceso, el producto queda sin fuente.

**Estado actual en este repo:** la aplicación registrada ya fue aprobada y la API oficial (`xmlapi2`) se usa con token Bearer (`BGG_TOKEN`), respetando el `Crawl-delay` de 5s. Scrapear la web sigue descartado (Cloudflare). Para escalar hay que pensar que ese token es único y de la aplicación: todas las consultas de todos los usuarios comparten su cuota y su rate limit.

### 3.2 Términos de uso / pata comercial
Según la documentación de BGG (consultada en la búsqueda, ver fuentes; confirmar siempre en la página oficial):
- Se requiere **registrar la aplicación y obtener autorización/token** para usar la XML API.
- Uso **comercial requiere licencia aparte**; los términos base son estrictamente no comerciales. Puede haber tarifa según la monetización, y BGG puede negarla si considera que la app compite con sus intereses.
- **Prohibido usar los datos para entrenar IA/LLMs.**
- Las apps públicas deben mostrar el logo **"Powered by BGG"** con link a BoardGameGeek.

Implicancia: gratis y sin monetizar es el terreno seguro; cobrar, mostrar publicidad o venderle a una tienda exige hablar con BGG antes.

### 3.3 Otros
- **Privacidad:** si una colección está oculta no se puede leer; avisar bien en la UI.
- **Costos y mantenimiento:** pasar de sitio estático a backend suma hosting, monitoreo y deuda operativa.

## 4. Estado del arte (competencia)

Resultado de una búsqueda rápida, **sin probar las herramientas ni verificar precios o vigencia**. Sirve como lista de partida para el análisis.

| Herramienta | Qué hace | Relevancia |
|---|---|---|
| **Kallax** | Importa de BGG; filtra colección propia y de amigos ("qué jugar") por jugadores, duración, etc. | La más parecida a "qué jugamos hoy" |
| **Pista** | Importa colección de BGG, recomendaciones por ánimo, registro de partidas. Dice no usar IA; matching hecho a mano con categorías/mecánicas/familias | Parecida en la parte de recomendación |
| **BG Stats** | App móvil: sync automático de colección BGG, import de partidas (BGG, Yucata, BGA), filtros para elegir juego para tu grupo. Algunas funciones pagas | Referente en estadísticas de partidas |
| **Game Shelf** (iOS) | Organiza colección (import BGG, escaneo de código de barras), registro de partidas y estadísticas; import de historial pago | Referente en colección + partidas |
| **What Game You Bringing** | iOS: filtra catálogo y colección de BGG por cantidad de jugadores | Filtro simple |
| **TableTop Pick** | Web gratis: importa colección BGG y sugiere juegos, sin registro | Casi el mismo MVP que planteamos |
| **BGG App** (monteslu/bggapp) | Web open source: filtra la colección para elegir juego | Referencia técnica |
| **Gameshelf** (web, antigua) | Junta colecciones de varios usernames de BGG para un grupo | Idea de "grupo de juego" |
| **mybgg**, **bgg-mcp** | Script CLI y servidor MCP para consultar colecciones y pedir recomendaciones | Referencia para desarrolladores |

### Qué analizar de cada una (para cuando las probemos)
- ¿Cuánto tarda desde que ingreso el username hasta ver algo útil?
- ¿Qué filtros ofrece para "qué jugamos hoy"? ¿Cuántos jugadores, tiempo, peso, ánimo?
- ¿Tiene "qué comprar"? ¿Con qué criterio?
- ¿Pide registrar partidas o alcanza con la colección?
- ¿Cómo maneja la dependencia de BGG, y cumple con "Powered by BGG"?
- ¿Es gratis, tiene paywall, requiere cuenta?
- Qué hace mal: fricción, datos viejos, diseño, falta de idioma español.

### Kallax.io: observaciones (2026-10-29, de una captura y navegación del usuario con cuenta gratis)

Se ve en la captura:
- Entra por username/colección ("Showing board games from X's collection").
- Barra de filtros: Players, Playtime, Complexity, Type, Mechanics, Categories, Language Req., Designer, y un botón **Pick** (el usuario cree que elige al azar; no confirmado).
- Cada juego muestra jugadores, duración y complejidad en categorías (Low / Simple / Unknown), no en peso numérico.
- Menú: Game Tags, Add Games, Explore (Near you, Events, Communities, Board Games), Social (Feed, Friends, Chats), Tools (Find expansions, Collection timeline, Statistics, Wallpaper).
- Hay plan pago ("Upgrade to Hobbyist") y "Install App" (parece instalación web, no app de tienda).

Observado por el usuario:
- No hay app en iOS/Android, solo acceso directo.
- Sin grupos de juego cerca en Argentina: la parte social depende de que haya gente en la zona.
- No vio buscador de juegos que no estén en la colección (un Watchlist propio).

Sin confirmar (revisar):
- Si "Pick" recomienda algo más que un random.
- Si "Explore → Board Games" es un buscador de catálogo general.
- Qué funciones están detrás del plan pago y cuánto cuesta.
- Si tiene un equivalente a "¿Cuál comprar?".

### BG Stats: observaciones (2026-10-29, de su página oficial vista por el usuario)

Se ve en la captura:
- Apps en App Store y Google Play, 16 idiomas, funciona offline, sincroniza con BGG, cloud sync.
- Foco en **registrar partidas**, puntajes y estadísticas por jugador (hojas de puntaje a medida, comparar jugadores, gráficos).
- Gestión de colección con estados (Owned, Wishlist, Want to play, Preordered, etc.), versiones y copias múltiples.
- Entre sus preguntas: "What haven't I played from my collection?" y "What should we play tonight with this group?".
- Tiene secciones de Roadmap, Wishlist (pedidos de funciones) y expansiones pagas (Power Expansion, Challenges).

Observado por el usuario:
- La web es poco moderna.
- El eje es anotar partidas, que al usuario no le resulta tan útil para su caso.

Pendiente: análisis de reseñas en las tiendas de apps (lo corre el usuario).

### Otros competidores relevados por el usuario (documento "Proyecto juegos de mesa", 2026-10-30)

- **TablePick** (tablepick.net): "¿Cuál comprar?" con "% de fit" según jugadores, tiempo, complejidad, tipo de juego y experiencia; base de ~21.000 juegos de BGG; tiene catálogo con buscador. Es el análogo más directo a "¿Cuál comprar?".
- **What Should We Play?** (boardgamehelpers.com): login con BGG, lee colección y notas, recomienda qué jugar de la propia estantería filtrando por jugadores y complejidad. Análogo a "¿Qué jugamos hoy?".
- **Recommend.Games**: recomendaciones por ML a partir de ratings del perfil de BGG; también cruza con otro usuario ("what to play with"). Al usuario no le encontró su colección (parece scrapear BGG en vez de usar la API).
- **Kallax**: ~1,6 M de juegos según Gemini (dato sin verificar; probablemente cuenta juegos en estanterías de usuarios y no el tamaño del catálogo, así que no es comparable con los 28.000). Sitio gratis sin publicidad, financiado con suscripción voluntaria; sin app de tienda.
- **BG Stats**: app de pago (el usuario anotó ~10k, sin moneda ni fecha). Foco en partidas y estadísticas.
- **Cazagangas** (cazagangas.com.ar): precios por tienda en Argentina y compraventa de usados. Ya está integrado en este proyecto.
- Otros: Game Shelf (reservar juntadas), Layer Up (partes imprimibles en 3D).

Conclusión del usuario: las funciones "mi ludoteca", "qué jugar" y "cuál comprar" ya existen, casi todos los competidores apuntan a otros países, y monetizar es difícil. El objetivo principal del MVP es aprender a armar y desplegar un MVP rápido (branch + hosting) para replicarlo en otros proyectos, por ejemplo estadísticas para clubes amateurs (Buitres).

Ángulos de diferenciación que salen de esto (a validar):
- **Argentina:** precios y disponibilidad locales (Cazagangas) combinados con la recomendación. Ningún competidor relevado hace eso.
- **Entrada sin BGG:** marcar a mano qué juegos tenés sobre el catálogo propio, guardado en el navegador. Cubre a quien no usa BGG y no consume cuota de la API.

### Hipótesis de diferenciación (a validar)
- Combinar "qué jugar hoy" y "qué comprar" en una misma herramienta.
- Funcionar solo con la colección (sin registrar partidas), usando además el puntaje propio y el Estado Own / Want to buy.
- Interfaz en español y diseño cuidado.

## 5. Fuentes
- [Using the XML API (BGG)](https://boardgamegeek.com/using_the_xml_api)
- [BGG XML API Commercial Use](https://boardgamegeek.com/wiki/page/BGG_XML_API_Commercial_Use)
- [XML API Terms of Use](https://boardgamegeek.com/wiki/page/XML_API_Terms_of_Use)
- [Board Game Stats (App Store)](https://apps.apple.com/us/app/id892542000)
- [TableTop Pick (DEV)](https://dev.to/riviergrullon/tabletop-pick-import-your-bgg-collection-and-get-smart-game-night-suggestions-42nn)
- [monteslu/bggapp](https://github.com/monteslu/bggapp)
- [What Game You Bringing (Product Hunt)](https://www.producthunt.com/products/what-game-you-bringing)
