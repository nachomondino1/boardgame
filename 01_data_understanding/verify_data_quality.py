"""Verify Data Quality (CRISP-DM, fase Data Understanding): chequeos sobre
data/01_data_understanding/ludoteca.jsonl (lo que cargás a mano, solo para
los juegos que curaste — ver su propio docstring en search_new_game.py),
universo_juegos.jsonl (el catálogo completo) y bgg_data.jsonl (el caché de
BGG) que no dependen de ningún otro paso del pipeline — corre standalone,
antes o después de search_new_game.py/modify_values.py o de una edición a
mano de ludoteca.jsonl.

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
COLLECT_DIR = HERE / "collect_initial_data" / "bgg"
sys.path.insert(0, str(COLLECT_DIR))
from bgg_common import UNIVERSO_FIELDS, BGG_CACHE_FIELDS, LIST_FIELDS  # noqa: E402

DATA_DIR = HERE.parent / "data" / "01_data_understanding"
LUDOTECA_PATH = DATA_DIR / "ludoteca.jsonl"
UNIVERSO_PATH = DATA_DIR / "universo_juegos.jsonl"
BGG_DATA_PATH = DATA_DIR / "bgg_data.jsonl"

LUDOTECA_FIELDS = ["bgg_id", "nombre", "estado", "transportable", "mi_puntaje", "pros", "cons", "notas"]

# "Watchlist" es válido como valor EXPLÍCITO acá (un juego que no posees
# pero sobre el que ya tenés notas/transportable cargado), aunque el
# default para un juego sin fila en absoluto (ver integrate_data.py) sea
# justamente "Watchlist" — la diferencia es "lo pensé y es Watchlist" vs.
# "nunca lo curé".
ESTADOS_VALIDOS = {"Own", "Prev. owned", "Watchlist", "Want to buy", "Descartado"}
# campo: (min, max). complejidad/puntaje_bgg viven en bgg_data.jsonl,
# mi_puntaje en ludoteca.jsonl — ver dónde se usa cada uno más abajo.
NUMERIC_RANGES_BGG = {"complejidad": (1, 5), "puntaje_bgg": (1, 10)}
NUMERIC_RANGES_LUDOTECA = {"mi_puntaje": (1, 10)}


def load_jsonl(path, required=True):
    if not path.exists():
        if required:
            sys.exit(f"No existe {path}.")
        return []
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


def check_bgg_id_unico(rows, path):
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
                f'{path.name}: bgg_id {bgg_id} repetido: "{vistos[bgg_id]}" y "{nombre_de(row)}"',
            ))
        else:
            vistos[bgg_id] = nombre_de(row)
    return problems


def check_nombre_duplicado(rows, path):
    """Mismo nombre en dos filas con bgg_id distinto (o vacío) puede ser el
    mismo juego cargado dos veces por error, o dos ediciones distintas
    legítimas — se marca como warning para que se revise a mano, no error
    automático."""
    problems = []
    vistos = {}
    for row in rows:
        nombre = (row.get("nombre") or "").strip().lower()
        if not nombre:
            problems.append(("ERROR", f"{path.name}: fila con nombre vacío"))
            continue
        if nombre in vistos:
            problems.append((
                "WARNING",
                f'{path.name}: nombre repetido: "{nombre_de(row)}" (bgg_id {row.get("bgg_id") or "vacío"}) '
                f'ya estaba cargado (bgg_id {vistos[nombre] or "vacío"})',
            ))
        else:
            vistos[nombre] = row.get("bgg_id")
    return problems


def check_estado(rows):
    """Una fila en ludoteca.jsonl existe porque alguien la curó a
    propósito (ver search_new_game.py --estado) — a diferencia de antes,
    no hay un estado "pendiente" válido: si la fila está, `estado` tiene
    que ser uno de los válidos."""
    problems = []
    for row in rows:
        estado = row.get("estado")
        if estado not in ESTADOS_VALIDOS:
            problems.append(("ERROR", f'{nombre_de(row)}: estado "{estado}" no es uno de {sorted(ESTADOS_VALIDOS)}'))
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
    bgg_common.py) — si alguna fila quedó con un string suelto
    (regresión al formato CSV viejo, o una edición a mano rota), se nota."""
    problems = []
    for row in bgg_rows:
        for campo in LIST_FIELDS:
            valor = row.get(campo)
            if valor is not None and not isinstance(valor, list):
                problems.append(("ERROR", f"bgg_id {row.get('bgg_id')}: {campo} no es una lista ({type(valor).__name__})"))
    return problems


def check_bgg_url_coincide_con_bgg_id(universo_rows):
    problems = []
    for row in universo_rows:
        bgg_id = (row.get("bgg_id") or "").strip()
        bgg_url = (row.get("bgg_url") or "").strip()
        if bgg_id and bgg_url and f"/boardgame/{bgg_id}" not in bgg_url and f"/boardgameexpansion/{bgg_id}" not in bgg_url:
            problems.append(("ERROR", f'{nombre_de(row)}: bgg_url "{bgg_url}" no contiene el bgg_id {bgg_id}'))
    return problems


def check_bgg_id_sin_cache(universo_rows, bgg_ids_en_cache):
    """Un juego con bgg_id en universo_juegos.jsonl pero sin fila en
    bgg_data.jsonl: o no corrió search_new_game.py todavía después de
    cargarlo, o ese bgg_id no tiene match en el dataset de origen (puede
    pasar, no es necesariamente un error — se marca warning para revisar)."""
    problems = []
    for row in universo_rows:
        bgg_id = (row.get("bgg_id") or "").strip()
        if bgg_id and bgg_id not in bgg_ids_en_cache:
            problems.append(("WARNING", f"{nombre_de(row)}: bgg_id {bgg_id} no tiene datos en bgg_data.jsonl todavía"))
    return problems


def check_ludoteca_en_universo(ludoteca_rows, universo_rows):
    """Un juego de ludoteca.jsonl que no aparece en universo_juegos.jsonl
    (ni por bgg_id ni por nombre) no va a tener bgg_url/link_cazagangas/
    datos de BGG en data.json — probablemente falta correr
    search_new_game.py --add para ese juego. A diferencia de antes, NO hay
    chequeo en el sentido inverso (universo sin fila en ludoteca): eso es
    el caso normal, no un pendiente — ver integrate_data.py, ESTADO_DEFAULT."""
    ids = {(r.get("bgg_id") or "").strip() for r in universo_rows if r.get("bgg_id")}
    nombres = {r.get("nombre") for r in universo_rows}
    problems = []
    for row in ludoteca_rows:
        bgg_id = (row.get("bgg_id") or "").strip()
        if bgg_id and bgg_id in ids:
            continue
        if row.get("nombre") in nombres:
            continue
        problems.append(("WARNING", f'{nombre_de(row)}: no está en universo_juegos.jsonl todavía (ni por bgg_id ni por nombre)'))
    return problems


def main():
    ludoteca_rows = load_jsonl(LUDOTECA_PATH, required=False)
    universo_rows = load_jsonl(UNIVERSO_PATH)
    bgg_rows = load_jsonl(BGG_DATA_PATH)
    print(f"Verificando {len(ludoteca_rows)} juego(s) curado(s) en {LUDOTECA_PATH}, "
          f"{len(universo_rows)} en {UNIVERSO_PATH} "
          f"y {len(bgg_rows)} fila(s) en {BGG_DATA_PATH}...\n")

    all_problems = []
    all_problems += check_schema(ludoteca_rows, LUDOTECA_FIELDS, LUDOTECA_PATH)
    all_problems += check_schema(universo_rows, UNIVERSO_FIELDS, UNIVERSO_PATH)
    all_problems += check_schema(bgg_rows, BGG_CACHE_FIELDS, BGG_DATA_PATH)
    all_problems += check_bgg_id_unico(ludoteca_rows, LUDOTECA_PATH)
    all_problems += check_bgg_id_unico(universo_rows, UNIVERSO_PATH)
    all_problems += check_nombre_duplicado(ludoteca_rows, LUDOTECA_PATH)
    all_problems += check_nombre_duplicado(universo_rows, UNIVERSO_PATH)
    all_problems += check_estado(ludoteca_rows)
    all_problems += check_rangos_numericos(ludoteca_rows, NUMERIC_RANGES_LUDOTECA)
    all_problems += check_bgg_url_coincide_con_bgg_id(universo_rows)
    all_problems += check_ludoteca_en_universo(ludoteca_rows, universo_rows)
    all_problems += check_rangos_min_max(bgg_rows)
    all_problems += check_rangos_numericos(bgg_rows, NUMERIC_RANGES_BGG)
    all_problems += check_list_fields(bgg_rows)
    all_problems += check_bgg_id_sin_cache(universo_rows, {r["bgg_id"] for r in bgg_rows})

    errores = [p for p in all_problems if p[0] == "ERROR"]
    warnings = [p for p in all_problems if p[0] == "WARNING"]

    for nivel, mensaje in all_problems:
        print(f"[{nivel}] {mensaje}")

    print(f"\n{len(errores)} error(es), {len(warnings)} warning(s).")
    if errores:
        sys.exit(1)


if __name__ == "__main__":
    main()
