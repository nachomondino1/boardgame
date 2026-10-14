# Playbook de diseño (unificado)

Cómo me gusta diseñar mis webs. Unifica los playbooks de **buitres-stats** (B), **catálogo de juegos de mesa** (J) y **recommend_movie** (P). Pegalo en el `CLAUDE.md` o en el prompt inicial de un proyecto nuevo.

**Cómo usarlo:** todo lo de abajo es el default. Si un proyecto necesita desviarse, decilo explícito y anotá el motivo en `DECISIONS.md`. Los valores de color marcados como *ejemplo* se reemplazan por los del proyecto; la estructura de tokens no.

---

## 1. Filosofía

- **Producto personal cuidado, no SaaS corporativo ni landing de marketing.** Denso en información, directo, sin relleno visual.
- **Minimalista y cálido** (tipo Linear / Notion, pero con off-white en vez de gris frío). Nada de look genérico de UI kit (Bootstrap/Material por default).
- **Un solo color de acento**, usado con moderación. Todo lo demás son neutros.
- **Jerarquía por tamaño y peso de tipografía**, no por color ni decoración.
- **Menos es más:** ante la duda, colapsar el control secundario (`<details>`, botón "Filtros") antes que mostrarlo todo desplegado.
- **Mobile-first de la información**, no solo del layout: el celular es el uso real.
- **Simplicidad primero:** client-side sobre un dataset existente antes que sumar backend/cuentas. Lo que pide escritura real va al backlog, no se fuerza.
- **Priorizar por impacto/esfuerzo**, no por lo más vistoso.
- **Performance y accesibilidad son parte del diseño:** objetivo Lighthouse 100/100/100/100.

## 2. Base técnica

- Para sitios chicos: HTML/CSS/JS vanilla, sin build step, un solo `style.css`. Si el proyecto ya es React/Next, los tokens y reglas de este documento aplican igual (el playbook es de diseño, no de stack).
- **Todo es variable CSS en `:root`.** Nunca colores, radios o sombras hardcodeados en las reglas.
- **Dark mode automático** vía `@media (prefers-color-scheme: dark)`, reescribiendo los mismos tokens (sin inventar tokens nuevos). Sin toggle manual por default.
- **Emoji del dominio como logo** (favicon como SVG inline en data-uri + `<h1>`). Emoji en vez de librerías de íconos cuando cumplen la función.
- Fuente: **Inter** (Google Fonts, 400–800) con `preconnect` + carga no bloqueante (`media="print" onload="this.media='all'"`) y fallback `system-ui, -apple-system, "Segoe UI", Roboto, sans-serif`. Verificar que no rompa Lighthouse/CLS.

## 3. Tokens

### Modo claro (estructura fija, acento = ejemplo)

```css
:root {
  /* Superficies */
  --bg: #fafaf8;            /* fondo de página: off-white cálido, nunca blanco puro */
  --bg-subtle: #f2f1ed;     /* hover de filas, headers de tabla, chips, tracks */
  --surface: #ffffff;       /* cards, paneles, inputs: sí blanco puro, para que "floten" */

  /* Texto */
  --text: #1a1a17;          /* casi-negro cálido, nunca #000 */
  --muted: #6f6d67;         /* secundario */
  --muted-soft: #a19e96;    /* terciario, labels, iconos pasivos */

  /* Bordes: dos niveles a propósito */
  --border: #e4e2dc;        /* elementos interactivos (inputs, selects, chips) */
  --border-soft: #ecebe6;   /* contenedores (cards, tablas) */

  /* Acento: UNO por proyecto, propio del dominio (no reusar el de otro proyecto) */
  --accent: #3d5a80;        /* ejemplo */
  --accent-soft: color-mix(in srgb, var(--accent) 12%, transparent); /* hover, filtro activo, focus ring */
  --accent-contrast: #ffffff;

  /* Semánticos: SOLO si el dato es objetivamente bueno/malo (ver §4) */
  --good: #16a34a; --warn: #d97706; --bad: #dc2626;  /* ejemplo */

  /* Radios */
  --radius-sm: 8px;         /* inputs, selects, botones, stats chicos */
  --radius: 12px;           /* cards, paneles, tablas */
  --radius-lg: 16px;        /* modales, bloques destacados */
  /* pills / chips / badges / nav / steppers: siempre 999px */

  /* Sombras: suaves, tinte cálido en claro */
  --shadow-xs: 0 1px 2px rgba(20,19,15,.05);                                   /* cards en reposo */
  --shadow-sm: 0 1px 3px rgba(20,19,15,.06), 0 1px 2px rgba(20,19,15,.04);     /* barras sticky */
  --shadow-md: 0 8px 24px rgba(20,19,15,.10);                                  /* menús, modales */
  --shadow-lg: 0 18px 32px -10px rgba(20,19,15,.16), 0 4px 10px rgba(20,19,15,.06); /* hover lift */
}
```

### Modo oscuro

Reglas (las que sí son firmes):
- **Nunca gris neutro puro ni negro puro.** Siempre con un dejo de color (slate azulado).
- **La superficie de las cards tiene que ser claramente más clara que el fondo**, si no todo se ve como una masa negra sin separación.
- El acento se **aclara** para mantener contraste.
- Las sombras pasan a negro puro.
- Los colores de estado/semánticos necesitan su **variante dark explícita** (ajustar el texto a mano; no se infiere).

```css
@media (prefers-color-scheme: dark) {
  :root {
    /* valores propuestos al unificar, validar en pantalla */
    --bg: #0f1218;
    --bg-subtle: #1a202b;
    --surface: #181e29;
    --text: #e6e8ec;
    --muted: #9aa3b2;
    --muted-soft: #6b7585;
    --border: #2a3342;
    --border-soft: #212836;
    --accent: /* acento del proyecto, ~20-25% más claro */;
    --shadow-xs: 0 1px 2px rgba(0,0,0,.4);
    --shadow-sm: 0 1px 3px rgba(0,0,0,.45);
    --shadow-md: 0 8px 24px rgba(0,0,0,.5);
    --shadow-lg: 0 18px 32px -10px rgba(0,0,0,.6);
  }
}
```

## 4. Uso del color

- **Acento** para: selección activa (tabs, chips, filtros), focus, hover, botón primario, links, badges de logro.
- **Semánticos (verde/ámbar/rojo) solo si el dato es objetivamente bueno o malo** (ganado/perdido, error/éxito). Un dato neutro (fecha, rival, récord sin carga positiva/negativa) va en `--text`, **no** en acento/verde "para destacar".
- Si hace falta un segundo color decorativo (ej. badge "nuevo"), un tono cálido apagado (ámbar `#fef3c7` / `#92400e`), nunca semáforo.
- **Badges de estado:** fondo = color saturado al ~17% de alpha, texto = el mismo color sólido.
- **Hover:** `color-mix(... var(--accent) 10–14%, transparent)`, nunca un segundo color hardcodeado.
- **Valor numérico continuo "bueno → malo"** (ej. complejidad): interpolar en HSL en vez de paleta fija: `hsl(${120 - (v/max)*120}, 62%, 42%)`.

## 5. Tipografía

- Base **14px**, `line-height: 1.55`, `-webkit-font-smoothing: antialiased`. Producto denso: cuerpo y stats entre 0.78–0.95rem.
- Pesos: 400 texto, 500–600 labels/énfasis, 700–800 títulos y números grandes.
- Títulos y números grandes con `letter-spacing: -0.01em` a `-0.02em`.
- **Labels/eyebrows** (filtros, headers de tabla, section labels): mayúscula, 11–12px, peso 700, `letter-spacing: +0.04–0.06em`, color `--muted-soft`.
- **Escala numérica:** número "hero" de una vista = 3rem bold; número de card = 1.75rem; etiquetas = 0.75–0.85rem en `--muted`, nunca compiten con el dato.
- **Sin decimales en la UI salvo que sea estrictamente necesario.** "53%", no "52,9%".
- Descripción corta debajo de un `<h2>`: secundaria, en `--muted`, nunca compite con el título.
- Contenedor centrado `max-width: 1240px`, padding horizontal 24px (16px en mobile).

## 6. Componentes

**Cards / paneles:** `--surface` + borde 1px `--border-soft` + `--shadow-xs` + `--radius`. Opcional: borde de color de 3–4px en un lado para indicar categoría/estado sin depender del texto. Si la card es clickeable: hover = `translateY(-3px)` + `--shadow-lg` + el borde se desvanece. La elevación en hover es la interacción "viva" del sitio (no en cards estáticas).

**Separar contenedores:** sombra sutil + `--border-soft` juntos. Entre secciones apiladas: borde superior sutil + margen generoso, sin cajas ni sombras pesadas.

**Header sticky con blur:** `position: sticky`, fondo `color-mix` con `--bg` semitransparente + `backdrop-filter: blur(14px)`.

**Navegación entre vistas** (elegir según el caso):
| Caso | Patrón |
|---|---|
| 2–4 vistas de una misma pantalla | **Segmented control**: contenedor `--bg-subtle` con padding 4px, pastilla blanca + `--shadow-xs` en el activo. Full-width en mobile. |
| App con secciones principales (uso mobile fuerte) | **Tab bar fija abajo en mobile**, fila arriba en desktop. |
| Varias páginas | **Pills** con scroll horizontal y scrollbar oculta (nunca wrap a 2 líneas). |

**Filtros:**
- Siempre agrupados en **su propia card** (nunca selects flotando sobre el fondo). Cada control con label chico en mayúscula arriba.
- **Mobile:** colapsados detrás de un botón "Filtros" (con badge de cantidad activa). Desktop: siempre visibles en fila.
- "Limpiar filtros" = link subrayado, visible solo si hay algo activo.
- Multi-select: dropdown propio (toggle + menú) con checkboxes y "Todos" arriba; mismo estilo que los selects simples. Decidir y documentar AND vs OR.
- Select nativo con **chevron custom** (SVG data-uri, uno claro y uno oscuro), nunca la flecha del SO.
- Inputs numéricos: **steppers circulares** (+/−) en vez de `<input type="number">`; 32px en filtros, 58px como acción hero.

**Chips / pills (999px):** borde `--border`, fondo `--surface`; activo = fondo y borde `--accent`, texto `--accent-contrast`. Todo lo "etiqueta" es pill (chips, badges, contadores, nav), comparten la misma escala de padding.

**Botón primario:** fondo/borde `--accent`, texto blanco, peso 600, `--radius-sm`, hover `opacity: .9`. Controles secundarios (✕, steppers) sin fondo en reposo, se llenan de acento en hover y hacen `scale(.92–.94)` al click. Nada de botones grises por defecto.

**Tablas:**
- Header `--bg-subtle`, mayúscula chica `--muted`; filas con hover `--bg-subtle`.
- Números a la derecha con `font-variant-numeric: tabular-nums`; texto/nombres a la izquierda.
- Primera columna sticky a la izquierda (scroll horizontal) y header sticky arriba (scroll vertical, ver trampa en §10).
- Siglas con `<abbr>` (subrayado punteado) en vez de iconos o texto extra.
- En mobile, si se oculta una columna, repetir esa info apilada dentro de la celda principal ("meta line" con chips). Nunca perderla.
- Siempre con estado vacío explícito.

**Modal:** overlay `rgba(15,15,20,.55)` + `blur(2px)`; caja `max-width: 560px`, `--radius-lg`, `--shadow-md`.

**Progressive disclosure:** `<details>/<summary>` nativo ("+ Más info" / "− Más info"), no acordeones ni modales con JS.

**Badges:** pill chica, mayúscula, 10px, con moderación (nunca decoración).

**Grids de cards:** `repeat(auto-fit, minmax(Npx, 1fr))` en vez de media queries por breakpoint.

**Scrollbar fina** (solo WebKit) en contenedores con scroll propio: 8px, thumb `--border`, track transparente.

## 7. Estados de carga, vacío y error

- **Skeletons con shimmer** (respetar `prefers-reduced-motion: reduce`), no spinners genéricos ni pantalla en blanco.
- **Vacíos y errores:** centrados, texto `--muted`; el error en `--bad` sin dramatizar.
- **Un dato sin soporte no se fuerza:** si nadie metió goles con esos filtros, la card dice "–", no resalta a alguien con 0.
- Reservar `min-height` en elementos que se llenan de forma asíncrona para evitar CLS.

## 8. Mobile y responsive

- Probar en celular real (no solo achicar el navegador) y en anchos explícitos: **320 / 360 / 375 / 768 / 1280**.
- Reordenar columnas para que el dato más importante quede primero; no ocultar "lo que sobra por posición".
- Paddings/gaps −20–30% y un escalón menos de tipografía; **el lenguaje de componentes no cambia** entre mobile y desktop.
- **Filtros sticky en mobile (regla firme):** la barra queda pegada arriba, **colapsada por default**, y **barra + panel abierto nunca pasan del 30% del alto de pantalla**. El panel scrollea por dentro si el contenido no entra.

```css
@media (max-width: 767px) {
  .filters-bar   { position: sticky; top: 0; z-index: 20; }
  .filters-panel { max-height: calc(30vh - 48px);   /* fallback */
                   max-height: calc(30dvh - 48px);  /* 48px = alto de la barra */
                   overflow-y: auto; overscroll-behavior: contain; }
}
```

- **Verificar con números, no a ojo:** `bar.getBoundingClientRect().height / window.innerHeight <= 0.30` en estado colapsado **y** expandido, a 320×568, 375×667 y en landscape de poco alto.
- **Otros sticky en mobile:** si hay barra de filtros sticky, el **header deja de ser sticky** (se va con el scroll) para no apilar dos barras fijas. El header de tabla mantiene su regla: desactivado en mobile angosto y en landscape de poco alto (`@media (max-height: 480px)`).
- Nav/filtros sticky arriba en desktop en páginas largas, con `scroll-margin-top` en las secciones.
- Verificar overflow con `scrollWidth` / `getBoundingClientRect()`, no solo con el screenshot (hay bugs de 1–2px invisibles).

## 9. Micro-interacciones, foco y accesibilidad

- Transiciones **0.1–0.18s ease, por propiedad** (`background`, `color`, `transform`, `box-shadow`, `border-color`). Nunca `transition: all`. Nada largo ni "bouncy".
- **Foco en inputs/selects:** borde → `--accent` + `box-shadow: 0 0 0 3px var(--accent-soft)`.
- **Foco en el resto** (botones, links, tabs, summary): `:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px }`. Nunca sacar el outline sin reemplazo.
- Si Lighthouse marca CLS en un elemento, buscar la causa real antes de ponerle `min-height` (suele ser el elemento *anterior* que arranca vacío y empuja).

## 10. Trampas de CSS a no repetir

- **Sticky en header de tabla:** `overflow-x: auto` fuerza `overflow-y: auto` y el sticky se pega al contenedor, no al viewport. Patrón correcto: la tabla vive en su propio scroll-container (`overflow: auto; max-height: Nvh`) y `th { position: sticky; top: 0 }` referencia a ese contenedor.
- Selector `.filter-group label` se filtra a labels anidados (checkboxes de un dropdown hijo). Usar `>` cuando el estilo es solo para el label directo.
- En media queries mobile, `width: 100%` en hijos no hace nada si el padre sigue en `flex-direction: row`; hace falta `column` en el mismo query.

## 11. Identidad visual y micro-visualizaciones

- **Codificación visual compacta > pared de números:** racha de resultados como puntitos de color, no "G-G-E-P-G"; ranking con top 2–3, no solo el líder; podio chico en vez de tabla completa.
- **Avatares con color por hash determinístico del nombre** (mismo nombre, mismo color) en vez de depender de fotos.
- **Fotos / banners full-width = riesgo alto de gusto.** Ya se probó uno y se sacó ("queda muy mal"). Probar visualmente antes de asumir que una foto mejora; importa más el tratamiento (tamaño, ubicación, dentro de una card vs. full-width) que tener la foto.

## 12. Producto (solo comunidades / hobbies / grupos)

- Mirar qué hacen bien otras apps del mismo nicho antes de inventar features.
- Dos patrones con engagement real: **sentirse "pro"** (stats con tratamiento prolijo, logros automáticos con umbrales calibrados contra datos reales, rankings con top 2–3) y **competencia sana** (comparadores lado a lado, leaderboards, rachas).

## 13. Proceso de trabajo

- **Mostrar en el navegador (mobile y desktop) antes de commitear** cambios de diseño y ajustar con feedback real.
- Para probar rápido: generar solo el HTML (el paso mínimo del pipeline) y abrirlo.
- Para casos que no existen todavía en producción (serie con 1 solo punto, filtros sin resultados): **inyectar datos falsos por consola/JS** sin tocar los reales.
- **Documentar decisiones en `DECISIONS.md`** apenas se toman (qué se probó, qué se descartó, por qué).
- Ambigüedades (desempates, criterios): resolver de forma **determinística** y documentar, no con heurísticas "más justas" pero impredecibles.

## 14. Qué evitar

- Grises neutros o negro puro en dark mode; blanco puro como fondo de página.
- Paletas saturadas por default, gradientes decorativos, sombras duras, bordes gruesos.
- Acento/verde en un valor solo para "destacarlo" cuando el dato es neutro.
- Decimales en la UI cuando un entero alcanza.
- Todos los controles desplegados en mobile.
- `transition: all`, animaciones largas.
- Librerías de íconos SVG cuando alcanza un emoji.
- Fotos/banners full-width sin probar.
- Forzar features que necesitan backend/cuentas en un producto estático.

## 15. Checklist para un proyecto nuevo

1. Copiar bloque de tokens (`:root` + `prefers-color-scheme: dark` con los mismos nombres).
2. Definir **un acento propio del dominio** y derivar `--accent-soft` (12%), `--accent-contrast` y su versión dark.
3. Cargar Inter con fallback a system-ui; base 14px.
4. Emoji temático como logo + favicon.
5. Cards con `--border-soft` + `--shadow-xs`; hover lift solo si son clickeables.
6. Filtros en su propia card con labels en mayúscula; colapsados detrás de botón en mobile.
7. Navegación según la tabla de §6.
8. Estados vacío / carga (skeleton) / error en toda lista filtrable.
9. Foco visible en todo, `prefers-reduced-motion` respetado.
10. Probar en 320/375/1280, verificar overflow con `scrollWidth`, correr Lighthouse.
11. Crear `DECISIONS.md`.

---

## Apéndice: decisiones al unificar (no hace falta cargarlo en cada proyecto)

Donde los 3 playbooks se contradecían, esto es lo que se eligió y por qué. Si no te cierra alguna, es el lugar para cambiarla.

| Tema | B (buitres) | J (juegos) | P (pelis) | Elegido |
|---|---|---|---|---|
| Fuente | system-ui, sin webfonts | Inter | Inter | **Inter + fallback system** (2 de 3; chequear impacto en Lighthouse) |
| Neutros light | off-white cálido | paper cálido | zinc (ni cálido ni azulado) | **Cálido** (2 de 3) |
| Neutros dark | slate azulado | casi-negro cálido | no definido | **Slate con dejo azulado** (valores propuestos, no extraídos) |
| Toggle de tema | opcional (auto→oscuro→claro) | nunca | no definido | **Sin toggle por default**; menos código, sin localStorage ni script en `<head>` |
| Radios | 8px único | 8 / 14 / 18 | 8 / 12 / 16 | **8 / 12 / 16** |
| Sombras | evitar sombras pesadas | cálidas, elevación en hover | sombra + border-soft | **border-soft + sombra sutil; lift solo en hover de cards clickeables** |
| Números en tablas | centrados | no definido | derecha + tabular-nums | **Derecha + tabular-nums** |
| Navegación | tab bar fija abajo (mobile) | pills con scroll horizontal | segmented control | **Según caso** (tabla en §6) |
| Filtros en mobile | botón sticky con badge | botón toggle | barra sticky desactivada en mobile | **Botón chico (puede ser sticky) + panel no sticky** |
| Foco | outline 2px offset 2px | borde acento + ring 3px | no definido | **Ring en inputs, outline en el resto** |
| Segundo color | semántico solo si es real | badges con alpha 17% | ámbar apagado | **Los tres, con la regla de §4** |
