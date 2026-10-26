"""Integra las fuentes crudas de data/ en un único archivo, antes de que
construct_data.py calcule las columnas derivadas. La base es
data/01_data_understanding/mis_datos.jsonl (el universo: todo lo que cargás vos a mano, un juego
exista o no en BGG) y se le suman, por join:

- data/01_data_understanding/bgg_data.jsonl — caché de BGG (ver collect_bgg_data.py), join por
  `bgg_id`. Un juego sin bgg_id (o sin match todavía) no tiene fila acá:
  sus columnas de BGG quedan en `null`, no es un error.
- data/01_data_understanding/grupos.json — curado a mano, juego -> nombre de grupo (ver
  DATA_PLAYBOOK.md, "Agrupar variantes/expansiones del mismo sistema de
  juego"), join por `nombre`. Se suma como el campo `grupo`.
- data/01_data_understanding/cazagangas_data.jsonl — resultado de check_cazagangas_links.py
  (link a Cazagangas + código HTTP real), join por `nombre`. Se suma como
  `link_cazagangas` y `cazagangas_status`.

Las tres últimas son opcionales: si alguna no existe todavía, los campos
que aporta quedan en `null` para todos, en vez de cortar con error — no
bloquean el resto del pipeline.

Esto solo integra (join, igual que el resto de los matches de este repo —
ver bosque_ludico/resolve_bosque_links.py): no tipa ni calcula nada. Los
valores crudos pasan sin tocar (strings u arrays, igual que en los archivos
originales); construct_data.py es el que convierte a número/calcula las
columnas derivadas, a partir de esta salida.

Uso:
    python3 02_data_preparation/integrate_data.py

Salida: data/02_data_preparation/integrated_data.jsonl (campos de mis_datos.jsonl + los de
bgg_data.jsonl, más `grupo`, `link_cazagangas`, `cazagangas_status` al
final de cada fila).
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MIS_DATOS_PATH = ROOT / "data" / "01_data_understanding" / "mis_datos.jsonl"
BGG_DATA_PATH = ROOT / "data" / "01_data_understanding" / "bgg_data.jsonl"
GRUPOS_PATH = ROOT / "data" / "01_data_understanding" / "grupos.json"
CAZAGANGAS_DATA_PATH = ROOT / "data" / "01_data_understanding" / "cazagangas_data.jsonl"
OUTPUT_PATH = ROOT / "data" / "02_data_preparation" / "integrated_data.jsonl"

# Campos de bgg_data.jsonl que se suman a cada juego (bgg_id es la clave de
# join, no se repite). Si se le agrega una columna nueva a collect_bgg_data.py,
# agregarla acá también.
BGG_CACHE_FIELDS = [
    "anio", "edad_min", "jug_min", "jug_max", "jug_best_min", "jug_best_max",
    "duracion_min", "duracion_max", "complejidad", "puntaje_bgg", "reviews_bgg", "ranking_bgg",
    "disenador", "mecanicas", "categorias", "descripcion",
]
LIST_FIELDS = {"mecanicas", "categorias"}


def load_jsonl(path):
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def load_bgg_cache_index():
    """bgg_id -> fila de bgg_data.jsonl. `{}` si el archivo no existe
    todavía (corré collect_bgg_data.py primero)."""
    rows = load_jsonl(BGG_DATA_PATH)
    return {r["bgg_id"]: r for r in rows if r.get("bgg_id")}


def load_grupo_index():
    """nombre de juego -> nombre de grupo. `{}` si grupos.json no existe
    todavía (curado manual opcional, no un error)."""
    if not GRUPOS_PATH.exists():
        return {}
    data = json.loads(GRUPOS_PATH.read_text(encoding="utf-8"))
    index = {}
    for grupo in data.get("grupos", []):
        for nombre in grupo["juegos"]:
            index[nombre] = grupo["nombre"]
    return index


def load_cazagangas_index():
    """nombre de juego -> {link_cazagangas, status_http}. `{}` si el
    archivo no existe todavía (check_cazagangas_links.py no corrió, o
    corrió parcial — ver su docstring, acepta --limit)."""
    rows = load_jsonl(CAZAGANGAS_DATA_PATH)
    return {r["nombre"]: r for r in rows}


def main():
    mis_datos = load_jsonl(MIS_DATOS_PATH)
    if not mis_datos:
        raise SystemExit(f"{MIS_DATOS_PATH} está vacío; corré collect_bgg_data.py primero.")

    bgg_cache_index = load_bgg_cache_index()
    grupo_index = load_grupo_index()
    cazagangas_index = load_cazagangas_index()

    integrated = []
    for g in mis_datos:
        row = dict(g)

        bgg_cache = bgg_cache_index.get((row.get("bgg_id") or "").strip())
        for field in BGG_CACHE_FIELDS:
            row[field] = bgg_cache.get(field) if bgg_cache else ([] if field in LIST_FIELDS else None)

        row["grupo"] = grupo_index.get(row["nombre"])
        cazagangas = cazagangas_index.get(row["nombre"])
        row["link_cazagangas"] = cazagangas["link_cazagangas"] if cazagangas else None
        row["cazagangas_status"] = cazagangas["status_http"] if cazagangas else None

        integrated.append(row)

    OUTPUT_PATH.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in integrated) + "\n",
        encoding="utf-8",
    )
    con_bgg = sum(1 for r in integrated if r.get("puntaje_bgg") is not None)
    con_grupo = sum(1 for r in integrated if r["grupo"])
    con_cazagangas_ok = sum(1 for r in integrated if r["cazagangas_status"] == "200")
    print(f"OK: {len(integrated)} juegos integrados en {OUTPUT_PATH} "
          f"({con_bgg} con datos de BGG, {con_grupo} con grupo, "
          f"{con_cazagangas_ok} con link de Cazagangas que responde 200).")


if __name__ == "__main__":
    main()
