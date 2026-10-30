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
//               numero?: true         (las opciones de una sola elección son números),
//               unidad?: (n) => str   (cómo se resume la elección, ej. "4 jugadores"),
//               defecto?: [ids],      (selección por defecto de un filtro de varias; si no, vacía)
//               extra?: { key, label, sufijo } }   (ficha booleana que se habilita al elegir un valor)
//   toggles: [{ key, label, icono }]
// Devuelve { sync }.

function mountFilterPills(container, { filters = [], toggles = [], state, clearButton, onChange }) {
  const defectoDe = (f) => (f.multiple ? (f.defecto || []).map(String) : []);

  function seleccion(f) {
    if (f.multiple) return [...state[f.id]].map(String);
    return state[f.id] == null ? [] : [String(state[f.id])];
  }

  function difiereDelDefecto(f) {
    const sel = seleccion(f).sort().join("|");
    return sel !== defectoDe(f).sort().join("|");
  }

  function etiqueta(f) {
    const sel = seleccion(f);
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
    const chips = f.opciones
      .map((o) => `<button type="button" class="fchip" data-filtro="${f.id}" data-opcion="${escapeHtml(String(o.id))}" aria-pressed="false"${o.hint ? ` title="${escapeHtml(o.hint)}"` : ""}>${escapeHtml(o.label)}</button>`)
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
      wrap.querySelectorAll(".fchip[data-opcion]").forEach((c) => c.setAttribute("aria-pressed", String(sel.includes(c.dataset.opcion))));
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
      if (f.multiple) {
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
