"""Verify Data Quality (CRISP-DM, fase Data Understanding): chequeos sobre
data/01_data_understanding/bgg_data.jsonl (datos crudos de BGG, que es el
catálogo completo), bgg_collection.jsonl (tu colección en BGG) y
cazagangas_data.jsonl que no dependen de ningún otro paso del pipeline — corre
standalone, antes o después de refresh_bgg_data.py.

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
from bgg_common import BGG_CACHE_FIELDS, COLLECTION_FIELDS, LIST_FIELDS  # noqa: E402

DATA_DIR = HERE.parent / "data" / "01_data_understanding"
BGG_DATA_PATH = DATA_DIR / "bgg_data.jsonl"
COLLECTION_PATH = DATA_DIR / "bgg_collection.jsonl"
CAZAGANGAS_PATH = DATA_DIR / "cazagangas_data.jsonl"
CAZAGANGAS_FIELDS = ["bgg_id", "link_cazagangas", "status_http", "fecha_chequeado"]

# campo: (min, max). averageweight/average son crudos de bgg_data.jsonl;
# 0 es el "sin dato" de BGG, no un valor real.
NUMERIC_RANGES_BGG = {"averageweight": (0, 5), "average": (0, 10)}


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
    return row.get("name") or row.get("nombre") or "(sin nombre)"


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
        nombre = (row.get("name") or "").strip().lower()
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


def check_rangos_min_max(bgg_rows):
    """minplayers/maxplayers, minplaytime/maxplaytime: el mínimo no puede
    ser mayor que el máximo."""
    problems = []
    pares = [
        ("minplayers", "maxplayers"),
        ("minplaytime", "maxplaytime"),
    ]
    for row in bgg_rows:
        for lo_key, hi_key in pares:
            lo = _as_float(row.get(lo_key))
            hi = _as_float(row.get(hi_key))
            if lo and hi and lo > hi:  # 0 = sin dato en BGG, no se compara
                problems.append(("WARNING", f"bgg_id {row.get('bgg_id')}: {lo_key}={lo} > {hi_key}={hi} (viene así de BGG)"))
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



def check_ranking_bgg_duplicado(bgg_rows, nombre_por_bgg_id):
    """ranking_bgg es la posición de un juego en el ranking global de BGG:
    por definición, dos juegos nunca deberían compartir el mismo número.
    Si pasa, es casi siempre porque se actualizó el ranking de algunos
    juegos con un dato más nuevo (ej. un mirror en vivo, ver DATA_PLAYBOOK.md)
    y otros quedaron con el valor viejo del dataset placeholder — warning,
    no error: mientras se actualiza de a partes del catálogo es esperable
    que pase, y se corrige a mano cuando se nota (como con Ark Nova /
    Pandemic Legacy: Season 1, 2026-10-28)."""
    problems = []
    por_ranking = {}
    for row in bgg_rows:
        ranking = _as_float(row.get("Board Game Rank"))
        if ranking is None:
            continue
        por_ranking.setdefault(ranking, []).append(row)
    for ranking, rows in sorted(por_ranking.items()):
        if len(rows) > 1:
            nombres = ", ".join(
                f'"{nombre_por_bgg_id.get(r.get("bgg_id"), "(sin nombre)")}" (bgg_id {r.get("bgg_id")})'
                for r in rows
            )
            problems.append(("WARNING", f"Board Game Rank {int(ranking)} repetido en {len(rows)} juegos: {nombres}"))
    return problems




def main():
    collection_rows = load_jsonl(COLLECTION_PATH, required=False)
    cazagangas_rows = load_jsonl(CAZAGANGAS_PATH, required=False)
    bgg_rows = load_jsonl(BGG_DATA_PATH)
    print(f"Verificando {len(bgg_rows)} juego(s) en {BGG_DATA_PATH}, {len(collection_rows)} de tu colección "
          f"en {COLLECTION_PATH} y {len(cazagangas_rows)} link(s) en {CAZAGANGAS_PATH}...\n")

    ids_bgg = {r["bgg_id"] for r in bgg_rows}
    all_problems = []
    all_problems += check_schema(bgg_rows, BGG_CACHE_FIELDS, BGG_DATA_PATH)
    all_problems += check_schema(collection_rows, COLLECTION_FIELDS, COLLECTION_PATH)
    all_problems += check_schema(cazagangas_rows, CAZAGANGAS_FIELDS, CAZAGANGAS_PATH)
    all_problems += check_bgg_id_unico(bgg_rows, BGG_DATA_PATH)
    all_problems += check_nombre_duplicado(bgg_rows, BGG_DATA_PATH)
    all_problems += check_rangos_min_max(bgg_rows)
    all_problems += check_rangos_numericos(bgg_rows, NUMERIC_RANGES_BGG)
    all_problems += check_list_fields(bgg_rows)
    all_problems += check_ranking_bgg_duplicado(bgg_rows, {r["bgg_id"]: r.get("name") for r in bgg_rows})
    for nombre_archivo, rows in (("bgg_collection.jsonl", collection_rows), ("cazagangas_data.jsonl", cazagangas_rows)):
        for r in rows:
            if r.get("bgg_id") not in ids_bgg:
                all_problems.append(("WARNING", f"{nombre_archivo}: bgg_id {r.get('bgg_id')} no está en bgg_data.jsonl (corré refresh_bgg_data.py)"))

    errores = [p for p in all_problems if p[0] == "ERROR"]
    warnings = [p for p in all_problems if p[0] == "WARNING"]

    for nivel, mensaje in all_problems:
        print(f"[{nivel}] {mensaje}")

    print(f"\n{len(errores)} error(es), {len(warnings)} warning(s).")
    if errores:
        sys.exit(1)


if __name__ == "__main__":
    main()
