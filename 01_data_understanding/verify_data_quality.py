"""Verify Data Quality (CRISP-DM, fase Data Understanding): chequeos sobre
bgg_data.jsonl que no dependen de ningún otro paso del pipeline — corre
standalone, antes o después de un refresh/--add de collect_bgg_data.py.

No modifica nada: solo reporta. Pensado para correr a mano después de
cargar juegos nuevos o corregir datos, y eventualmente como paso de CI
(sale con exit code 1 si hay algún ERROR, 0 si como mucho hay WARNINGs).

Uso:
    python3 01_data_understanding/verify_data_quality.py
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
COLLECT_DIR = HERE / "collect_initial_data"
sys.path.insert(0, str(COLLECT_DIR))
from collect_bgg_data import ALL_FIELDS, LIST_FIELDS  # noqa: E402

BGG_DATA_PATH = HERE.parent / "data" / "bgg_data.jsonl"

ESTADOS_VALIDOS = {"Own", "Prev. owned", "Watchlist", "Want to buy", "Descartado"}
# "Ambos" y "A confirmar" son variantes legacy conocidas (ver README) — se
# marcan como warning, no error, hasta que se decida normalizarlas.
MODOS_VALIDOS = {"Competitivo", "Cooperativo", "Equipos", "Cooperativo y competitivo"}
NUMERIC_RANGES = {
    # campo: (min, max)
    "complejidad": (1, 5),
    "puntaje_bgg": (1, 10),
    "mi_puntaje": (1, 10),
}


def load_rows():
    if not BGG_DATA_PATH.exists():
        sys.exit(f"No existe {BGG_DATA_PATH}.")
    rows = []
    with BGG_DATA_PATH.open(encoding="utf-8") as f:
        for i, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as e:
                sys.exit(f"Línea {i} de {BGG_DATA_PATH} no es JSON válido: {e}")
    return rows


def nombre_de(row):
    return row.get("nombre") or "(sin nombre)"


# ---------------------------------------------------------------------------
# Cada check devuelve una lista de (nivel, mensaje). nivel es "ERROR" o
# "WARNING" — ERROR hace fallar la corrida (exit code != 0), WARNING no.
# ---------------------------------------------------------------------------

def check_schema(rows):
    """Cada fila tiene exactamente las columnas esperadas (ni de más ni de
    menos) — detecta un campo renombrado/tipeado mal o un campo viejo que
    quedó pegado tras un cambio de esquema."""
    problems = []
    expected = set(ALL_FIELDS)
    for row in rows:
        actual = set(row.keys())
        faltantes = expected - actual
        de_mas = actual - expected
        if faltantes:
            problems.append(("ERROR", f"{nombre_de(row)}: faltan columnas {sorted(faltantes)}"))
        if de_mas:
            problems.append(("ERROR", f"{nombre_de(row)}: columnas no esperadas {sorted(de_mas)}"))
    return problems


def check_bgg_id_unico(rows):
    """bgg_id es el identificador del juego en BGG: si se repite, son dos
    filas para el mismo juego (duplicado real, no una coincidencia)."""
    problems = []
    vistos = {}
    for row in rows:
        bgg_id = (row.get("bgg_id") or "").strip()
        if not bgg_id:
            continue  # vacío es válido (juego sin ficha en BGG), no es un duplicado
        if bgg_id in vistos:
            problems.append((
                "ERROR",
                f'bgg_id {bgg_id} repetido: "{vistos[bgg_id]}" y "{nombre_de(row)}"',
            ))
        else:
            vistos[bgg_id] = nombre_de(row)
    return problems


def check_nombre_duplicado(rows):
    """Mismo nombre en dos filas con bgg_id distinto (o vacío) puede ser el
    mismo juego cargado dos veces por error, o dos ediciones distintas
    legítimas — se marca como warning para que se revise a mano, no error
    automático."""
    problems = []
    vistos = {}
    for row in rows:
        nombre = (row.get("nombre") or "").strip().lower()
        if not nombre:
            problems.append(("ERROR", "fila con nombre vacío"))
            continue
        if nombre in vistos:
            problems.append((
                "WARNING",
                f'nombre repetido: "{nombre_de(row)}" (bgg_id {row.get("bgg_id") or "vacío"}) '
                f'ya estaba cargado (bgg_id {vistos[nombre] or "vacío"})',
            ))
        else:
            vistos[nombre] = row.get("bgg_id")
    return problems


def check_estado(rows):
    problems = []
    for row in rows:
        estado = row.get("estado")
        if estado not in ESTADOS_VALIDOS:
            problems.append(("ERROR", f'{nombre_de(row)}: estado "{estado}" no es uno de {sorted(ESTADOS_VALIDOS)}'))
    return problems


def check_modo(rows):
    problems = []
    for row in rows:
        modo = row.get("modo")
        if modo and modo not in MODOS_VALIDOS:
            problems.append(("WARNING", f'{nombre_de(row)}: modo "{modo}" no es uno de los valores canónicos {sorted(MODOS_VALIDOS)}'))
    return problems


def _as_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def check_rangos_min_max(rows):
    """jug_min/jug_max, jug_best_min/jug_best_max, duracion_min/duracion_max:
    el mínimo no puede ser mayor que el máximo."""
    problems = []
    pares = [
        ("jug_min", "jug_max"),
        ("jug_best_min", "jug_best_max"),
        ("duracion_min", "duracion_max"),
    ]
    for row in rows:
        for lo_key, hi_key in pares:
            lo = _as_float(row.get(lo_key))
            hi = _as_float(row.get(hi_key))
            if lo is not None and hi is not None and lo > hi:
                problems.append(("ERROR", f"{nombre_de(row)}: {lo_key}={lo} > {hi_key}={hi}"))
    return problems


def check_rangos_numericos(rows):
    """complejidad, puntaje_bgg y mi_puntaje tienen que caer dentro del
    rango que usa BGG/el sitio, no cualquier número."""
    problems = []
    for row in rows:
        for campo, (lo, hi) in NUMERIC_RANGES.items():
            valor = _as_float(row.get(campo))
            if valor is not None and not (lo <= valor <= hi):
                problems.append(("ERROR", f"{nombre_de(row)}: {campo}={valor} fuera de [{lo}, {hi}]"))
    return problems


def check_list_fields(rows):
    """mecanicas/categorias se guardan como array JSON (ver docstring de
    collect_bgg_data.py) — si alguna fila quedó con un string suelto
    (regresión al formato CSV viejo, o una edición a mano rota), se nota."""
    problems = []
    for row in rows:
        for campo in LIST_FIELDS:
            valor = row.get(campo)
            if valor is not None and not isinstance(valor, list):
                problems.append(("ERROR", f"{nombre_de(row)}: {campo} no es una lista ({type(valor).__name__})"))
    return problems


def check_bgg_url_coincide_con_bgg_id(rows):
    problems = []
    for row in rows:
        bgg_id = (row.get("bgg_id") or "").strip()
        bgg_url = (row.get("bgg_url") or "").strip()
        if bgg_id and bgg_url and f"/boardgame/{bgg_id}" not in bgg_url and f"/boardgameexpansion/{bgg_id}" not in bgg_url:
            problems.append(("ERROR", f'{nombre_de(row)}: bgg_url "{bgg_url}" no contiene el bgg_id {bgg_id}'))
    return problems


CHECKS = [
    check_schema,
    check_bgg_id_unico,
    check_nombre_duplicado,
    check_estado,
    check_modo,
    check_rangos_min_max,
    check_rangos_numericos,
    check_list_fields,
    check_bgg_url_coincide_con_bgg_id,
]


def main():
    rows = load_rows()
    print(f"Verificando {len(rows)} juego(s) en {BGG_DATA_PATH}...\n")

    all_problems = []
    for check in CHECKS:
        all_problems.extend(check(rows))

    errores = [p for p in all_problems if p[0] == "ERROR"]
    warnings = [p for p in all_problems if p[0] == "WARNING"]

    for nivel, mensaje in all_problems:
        print(f"[{nivel}] {mensaje}")

    print(f"\n{len(errores)} error(es), {len(warnings)} warning(s).")
    if errores:
        sys.exit(1)


if __name__ == "__main__":
    main()
