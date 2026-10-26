"""Verify Data Quality (CRISP-DM, fase Data Understanding): chequeos sobre
data/mis_datos.jsonl (el universo + lo que cargás a mano) y data/bgg_data.jsonl
(el caché de BGG) que no dependen de ningún otro paso del pipeline — corre
standalone, antes o después de un refresh/--add/--set-estado de
collect_bgg_data.py.

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
from collect_bgg_data import MIS_DATOS_FIELDS, BGG_CACHE_FIELDS, LIST_FIELDS  # noqa: E402

MIS_DATOS_PATH = HERE.parent / "data" / "mis_datos.jsonl"
BGG_DATA_PATH = HERE.parent / "data" / "bgg_data.jsonl"

ESTADOS_VALIDOS = {"Own", "Prev. owned", "Watchlist", "Want to buy", "Descartado"}
# "Ambos" y "A confirmar" son variantes legacy conocidas (ver README) — se
# marcan como warning, no error, hasta que se decida normalizarlas.
MODOS_VALIDOS = {"Competitivo", "Cooperativo", "Equipos", "Cooperativo y competitivo"}
# campo: (min, max). complejidad/puntaje_bgg viven en bgg_data.jsonl,
# mi_puntaje en mis_datos.jsonl — ver dónde se usa cada uno más abajo.
NUMERIC_RANGES_BGG = {"complejidad": (1, 5), "puntaje_bgg": (1, 10)}
NUMERIC_RANGES_MIS_DATOS = {"mi_puntaje": (1, 10)}


def load_jsonl(path):
    if not path.exists():
        sys.exit(f"No existe {path}.")
    rows = []
    with path.open(encoding="utf-8") as f:
        for i, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as e:
                sys.exit(f"Línea {i} de {path} no es JSON válido: {e}")
    return rows


def nombre_de(row):
    return row.get("nombre") or "(sin nombre)"


def _as_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Cada check devuelve una lista de (nivel, mensaje). nivel es "ERROR" o
# "WARNING" — ERROR hace fallar la corrida (exit code != 0), WARNING no.
# ---------------------------------------------------------------------------

def check_schema(rows, expected_fields, path):
    """Cada fila tiene exactamente las columnas esperadas (ni de más ni de
    menos) — detecta un campo renombrado/tipeado mal o un campo viejo que
    quedó pegado tras un cambio de esquema."""
    problems = []
    expected = set(expected_fields)
    for row in rows:
        actual = set(row.keys())
        faltantes = expected - actual
        de_mas = actual - expected
        label = row.get("nombre") or row.get("bgg_id") or "(fila sin nombre ni bgg_id)"
        if faltantes:
            problems.append(("ERROR", f"{path.name}: {label}: faltan columnas {sorted(faltantes)}"))
        if de_mas:
            problems.append(("ERROR", f"{path.name}: {label}: columnas no esperadas {sorted(de_mas)}"))
    return problems


def check_bgg_id_unico(rows):
    """bgg_id es el identificador del juego en BGG: si se repite en
    mis_datos.jsonl, son dos filas para el mismo juego (duplicado real, no
    una coincidencia)."""
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


def check_rangos_min_max(bgg_rows):
    """jug_min/jug_max, jug_best_min/jug_best_max, duracion_min/duracion_max:
    el mínimo no puede ser mayor que el máximo."""
    problems = []
    pares = [
        ("jug_min", "jug_max"),
        ("jug_best_min", "jug_best_max"),
        ("duracion_min", "duracion_max"),
    ]
    for row in bgg_rows:
        for lo_key, hi_key in pares:
            lo = _as_float(row.get(lo_key))
            hi = _as_float(row.get(hi_key))
            if lo is not None and hi is not None and lo > hi:
                problems.append(("ERROR", f"bgg_id {row.get('bgg_id')}: {lo_key}={lo} > {hi_key}={hi}"))
    return problems


def check_rangos_numericos(rows, ranges):
    problems = []
    for row in rows:
        for campo, (lo, hi) in ranges.items():
            valor = _as_float(row.get(campo))
            if valor is not None and not (lo <= valor <= hi):
                label = row.get("nombre") or f"bgg_id {row.get('bgg_id')}"
                problems.append(("ERROR", f"{label}: {campo}={valor} fuera de [{lo}, {hi}]"))
    return problems


def check_list_fields(bgg_rows):
    """mecanicas/categorias se guardan como array JSON (ver docstring de
    collect_bgg_data.py) — si alguna fila quedó con un string suelto
    (regresión al formato CSV viejo, o una edición a mano rota), se nota."""
    problems = []
    for row in bgg_rows:
        for campo in LIST_FIELDS:
            valor = row.get(campo)
            if valor is not None and not isinstance(valor, list):
                problems.append(("ERROR", f"bgg_id {row.get('bgg_id')}: {campo} no es una lista ({type(valor).__name__})"))
    return problems


def check_bgg_url_coincide_con_bgg_id(rows):
    problems = []
    for row in rows:
        bgg_id = (row.get("bgg_id") or "").strip()
        bgg_url = (row.get("bgg_url") or "").strip()
        if bgg_id and bgg_url and f"/boardgame/{bgg_id}" not in bgg_url and f"/boardgameexpansion/{bgg_id}" not in bgg_url:
            problems.append(("ERROR", f'{nombre_de(row)}: bgg_url "{bgg_url}" no contiene el bgg_id {bgg_id}'))
    return problems


def check_bgg_id_sin_cache(mis_datos_rows, bgg_ids_en_cache):
    """Un juego con bgg_id en mis_datos.jsonl pero sin fila en
    bgg_data.jsonl: o no corrió collect_bgg_data.py todavía después de
    cargarlo, o ese bgg_id no tiene match en el dataset de origen (puede
    pasar, no es necesariamente un error — se marca warning para revisar)."""
    problems = []
    for row in mis_datos_rows:
        bgg_id = (row.get("bgg_id") or "").strip()
        if bgg_id and bgg_id not in bgg_ids_en_cache:
            problems.append(("WARNING", f"{nombre_de(row)}: bgg_id {bgg_id} no tiene datos en bgg_data.jsonl todavía"))
    return problems


def main():
    mis_datos_rows = load_jsonl(MIS_DATOS_PATH)
    bgg_rows = load_jsonl(BGG_DATA_PATH)
    print(f"Verificando {len(mis_datos_rows)} juego(s) en {MIS_DATOS_PATH} "
          f"y {len(bgg_rows)} fila(s) en {BGG_DATA_PATH}...\n")

    all_problems = []
    all_problems += check_schema(mis_datos_rows, MIS_DATOS_FIELDS, MIS_DATOS_PATH)
    all_problems += check_schema(bgg_rows, BGG_CACHE_FIELDS, BGG_DATA_PATH)
    all_problems += check_bgg_id_unico(mis_datos_rows)
    all_problems += check_nombre_duplicado(mis_datos_rows)
    all_problems += check_estado(mis_datos_rows)
    all_problems += check_modo(mis_datos_rows)
    all_problems += check_bgg_url_coincide_con_bgg_id(mis_datos_rows)
    all_problems += check_rangos_numericos(mis_datos_rows, NUMERIC_RANGES_MIS_DATOS)
    all_problems += check_rangos_min_max(bgg_rows)
    all_problems += check_rangos_numericos(bgg_rows, NUMERIC_RANGES_BGG)
    all_problems += check_list_fields(bgg_rows)
    all_problems += check_bgg_id_sin_cache(mis_datos_rows, {r["bgg_id"] for r in bgg_rows})

    errores = [p for p in all_problems if p[0] == "ERROR"]
    warnings = [p for p in all_problems if p[0] == "WARNING"]

    for nivel, mensaje in all_problems:
        print(f"[{nivel}] {mensaje}")

    print(f"\n{len(errores)} error(es), {len(warnings)} warning(s).")
    if errores:
        sys.exit(1)


if __name__ == "__main__":
    main()
