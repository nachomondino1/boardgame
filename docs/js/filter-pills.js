// Barra de filtros como píldoras con menú: la usan ¿Cuál comprar?, Mi ludoteca y ¿Qué jugamos hoy?.
//
// Cada filtro es una píldora que abre un menú con la misma forma (título + fichas). Un filtro es de
// una sola opción (state[id] = valor o null) o de varias (state[id] = Set de ids; vacío = todas).
// Las "toggles" son píldoras sin menú que prenden y apagan un booleano (state[key]). La píldora resume
// lo elegido y se pinta cuando difiere del valor por defecto; "Limpiar filtros" (fuera de las píldoras,
// en la fila de resultados) vuelve todo al valor por defecto.
//
// mountFilterPills(container, { filters, toggles, state, clearButton, onChange })
//   filters (opcional): [{ id, titulo, icono, multiple, opciones: [{ id, label, hint? }],
//               (opcional `grupo` en cada opción: las opciones, ya ordenadas, se muestran bajo el título de su grupo)
//               numero?: true         (las opciones de una sola elección son números),
//               unidad?: (n) => str   (cómo se resume la elección, ej. "4 jugadores"),
//               defecto?: [ids],      (selección por defecto de un filtro de varias; si no, vacía)
//               excluir?: "clave"   (filtro de varias con exclusión: cada ficha rota neutral → incluir → excluir → neutral;
//                                    las excluidas quedan en state[clave], un Set de ids)
//               extra?: { key, label, sufijo } }   (ficha booleana que se habilita al elegir un valor)
//   toggles: [{ key, label, icono }]
// Devuelve { sync }.

function mountFilterPills(container, { filters = [], toggles = [], state, clearButton, onChange }) {
  const defectoDe = (f) => (f.multiple ? (f.defecto || []).map(String) : []);

  function seleccion(f) {
    if (f.multiple) return [...state[f.id]].map(String);
    return state[f.id] == null ? [] : [String(state[f.id])];
  }

  const excluidas = (f) => (f.excluir ? [...state[f.excluir]].map(String) : []);

  function difiereDelDefecto(f) {
    const sel = seleccion(f).sort().join("|");
    return sel !== defectoDe(f).sort().join("|") || excluidas(f).length > 0;
  }

  function etiqueta(f) {
    const sel = seleccion(f);
    const no = excluidas(f);
    if (no.length) {
      const nombre = (id) => f.opciones.find((o) => String(o.id) === id).label;
      const sin = no.length === 1 ? `sin ${nombre(no[0])}` : `sin ${no.length}`;
      if (!sel.length) return `${f.icono} ${sin}`;
      return `${f.icono} ${f.titulo} · ${sel.length} · ${sin}`;
    }
    if (!sel.length) return `${f.icono} ${f.titulo}`;
    if (!f.multiple) {
      const op = f.opciones.find((o) => String(o.id) === sel[0]);
      const base = f.unidad ? f.unidad(Number(sel[0])) : op.label;
      return `${f.icono} ${base}${f.extra && state[f.extra.key] ? ` · ${f.extra.sufijo}` : ""}`;
    }
    if (sel.length === 1) return `${f.icono} ${f.opciones.find((o) => String(o.id) === sel[0]).label}`;
    return `${f.icono} ${f.titulo} · ${sel.length}`;
  }

  function activos() {
    return filters.filter(difiereDelDefecto).length + toggles.filter((t) => state[t.key]).length;
  }

  function pillHtml(f) {
    let grupoActual = null;
    const chips = f.opciones
      .map((o) => (o.grupo && o.grupo !== grupoActual ? (grupoActual = o.grupo, `<p class="pill-pop__group">${escapeHtml(o.grupo)}</p>`) : "") + `<button type="button" class="fchip" data-filtro="${f.id}" data-opcion="${escapeHtml(String(o.id))}" aria-pressed="false"${o.hint ? ` title="${escapeHtml(o.hint)}"` : ""}>${escapeHtml(o.label)}</button>`)
      .join("");
    const extra = f.extra
      ? `<div class="pill-pop__extra"><button type="button" class="fchip" data-extra="${f.extra.key}" aria-pressed="false">${escapeHtml(f.extra.label)}</button></div>`
      : "";
    return `
      <div class="pill-wrap" data-pill="${f.id}">
        <button type="button" class="pill" aria-haspopup="true" aria-expanded="false"><span class="pill__label"></span><span class="pill__chev" aria-hidden="true">▾</span></button>
        <div class="pill-pop" hidden>
          <p class="pill-pop__title">${escapeHtml(f.titulo)}</p>
          <div class="pill-pop__chips">${chips}</div>
          ${f.nota ? `<p class="pill-pop__note">${escapeHtml(f.nota)}</p>` : ""}
          ${f.ayuda ? `<details class="pill-pop__help"><summary>${escapeHtml(f.ayudaTitulo || "ℹ️ Ayuda")}</summary><dl>${f.ayuda.map(([t, d]) => `<dt>${escapeHtml(t)}</dt><dd>${escapeHtml(d)}</dd>`).join("")}</dl></details>` : ""}
          ${extra}
        </div>
      </div>`;
  }

  function sync() {
    filters.forEach((f) => {
      const wrap = container.querySelector(`[data-pill="${f.id}"]`);
      const sel = seleccion(f);
      wrap.querySelector(".pill").classList.toggle("on", difiereDelDefecto(f));
      wrap.querySelector(".pill__label").textContent = etiqueta(f);
      const no = excluidas(f);
      wrap.querySelectorAll(".fchip[data-opcion]").forEach((c) => {
        c.setAttribute("aria-pressed", String(sel.includes(c.dataset.opcion)));
        if (f.excluir) c.dataset.excluida = String(no.includes(c.dataset.opcion));
      });
      if (f.extra) {
        const extra = wrap.querySelector("[data-extra]");
        extra.disabled = state[f.id] == null;
        extra.setAttribute("aria-pressed", String(!!state[f.extra.key]));
      }
    });
    toggles.forEach((t) => {
      const el = container.querySelector(`[data-toggle="${t.key}"]`);
      el.classList.toggle("on", !!state[t.key]);
      el.setAttribute("aria-pressed", String(!!state[t.key]));
    });
    if (clearButton) {
      const n = activos();
      clearButton.hidden = n === 0;
      clearButton.textContent = `✕ Limpiar filtros (${n})`;
    }
  }

  function cerrarMenus(except) {
    container.querySelectorAll(".pill-wrap").forEach((wrap) => {
      if (wrap === except) return;
      wrap.querySelector(".pill-pop").hidden = true;
      wrap.querySelector(".pill").setAttribute("aria-expanded", "false");
    });
  }

  function alternarMenu(wrap) {
    cerrarMenus(wrap);
    const pop = wrap.querySelector(".pill-pop");
    const abrir = pop.hidden;
    pop.hidden = !abrir;
    wrap.querySelector(".pill").setAttribute("aria-expanded", String(abrir));
    if (abrir) {
      // Si el menú se saldría de la pantalla por la derecha, se alinea al borde derecho de la píldora.
      pop.classList.remove("pill-pop--right");
      if (pop.getBoundingClientRect().right > window.innerWidth - 12) pop.classList.add("pill-pop--right");
    }
  }

  function elegirOpcion(chip) {
    if (chip.dataset.extra) {
      const f = filters.find((x) => x.extra && x.extra.key === chip.dataset.extra);
      if (state[f.id] == null) return;
      state[f.extra.key] = !state[f.extra.key];
    } else {
      const f = filters.find((x) => x.id === chip.dataset.filtro);
      const opcion = chip.dataset.opcion;
      if (f.multiple && f.excluir) {
        // neutral → incluir → excluir → neutral
        if (state[f.excluir].has(opcion)) state[f.excluir].delete(opcion);
        else if (state[f.id].has(opcion)) { state[f.id].delete(opcion); state[f.excluir].add(opcion); }
        else state[f.id].add(opcion);
      } else if (f.multiple) {
        if (state[f.id].has(opcion)) state[f.id].delete(opcion);
        else state[f.id].add(opcion);
      } else {
        const valor = f.numero ? Number(opcion) : opcion;
        state[f.id] = state[f.id] === valor ? null : valor;
        if (state[f.id] == null && f.extra) state[f.extra.key] = false;
        cerrarMenus(); // elegir un valor es una sola decisión: el menú se cierra
      }
    }
    sync();
    onChange();
  }

  function limpiar() {
    filters.forEach((f) => {
      if (f.multiple) state[f.id] = new Set(defectoDe(f));
      else state[f.id] = null;
      if (f.extra) state[f.extra.key] = false;
      if (f.excluir) state[f.excluir] = new Set();
    });
    toggles.forEach((t) => { state[t.key] = false; });
    sync();
    onChange();
  }

  container.innerHTML = filters.map(pillHtml).join("")
    + toggles.map((t) => `<button type="button" class="pill" data-toggle="${t.key}" aria-pressed="false">${t.icono} ${escapeHtml(t.label)}</button>`).join("");

  container.addEventListener("click", (e) => {
    const chip = e.target.closest(".fchip");
    if (chip) { elegirOpcion(chip); return; }
    const pill = e.target.closest(".pill-wrap > .pill");
    if (pill) { alternarMenu(pill.parentElement); return; }
    const toggle = e.target.closest("[data-toggle]");
    if (toggle) {
      state[toggle.dataset.toggle] = !state[toggle.dataset.toggle];
      sync();
      onChange();
    }
  });
  document.addEventListener("click", (e) => { if (!e.target.closest(".pill-wrap")) cerrarMenus(); });
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") cerrarMenus(); });
  if (clearButton) clearButton.addEventListener("click", limpiar);

  sync();
  return { sync };
}
