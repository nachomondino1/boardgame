"""Integra las fuentes crudas de data/01_data_understanding/ en un único
archivo, antes de que construct_data.py calcule las columnas derivadas. La
base es bgg_data.jsonl — EL catálogo completo, "todo juego que este repo
conoce", crudo y con los nombres de BGG (ver bgg_common.py) — y se le suman,
por join en `bgg_id`:

- bgg_collection.jsonl — tu colección en BGG, cruda (own, wanttobuy,
  rating…). Un juego que no está en tu colección no es un error: sus campos
  quedan en `null` y construct_data.py le da `estado` "Watchlist".
- cazagangas_data.jsonl — link a Cazagangas y código HTTP real de ese link
  (check_cazagangas_links.py). Se suma como `link_cazagangas` y
  `cazagangas_status`; sin fila, quedan en `null`.

Las dos últimas son opcionales: si alguna no existe todavía, los campos que
aporta quedan en `null`, en vez de cortar con error.

bgg_data.jsonl está **gitignored** (2026-10-28, junto con el resto de
`data/01_data_understanding/`, ver DATA_PLAYBOOK.md): pesa ~94MB, y vive solo
local, con copia de seguridad a cargo del usuario (no de git).

Esto solo integra (join): no tipa ni calcula nada. Los valores crudos pasan
sin tocar; construct_data.py es el que convierte a número y calcula las
columnas derivadas (nombre, grupo, estado, jugadores, etc.), a partir de
esta salida.

Uso:
    python3 02_data_preparation/integrate_data.py

Salida: data/02_data_preparation/integrated_data.jsonl (campos de
bgg_data.jsonl + los de bgg_collection.jsonl + `link_cazagangas`,
`cazagangas_status` al final de cada fila).
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data" / "01_data_understanding"
BGG_DATA_PATH = DATA_DIR / "bgg_data.jsonl"
COLLECTION_PATH = DATA_DIR / "bgg_collection.jsonl"
CAZAGANGAS_DATA_PATH = DATA_DIR / "cazagangas_data.jsonl"
OUTPUT_PATH = ROOT / "data" / "02_data_preparation" / "integrated_data.jsonl"

# Campos de bgg_collection.jsonl que se suman a cada juego (crudos; `null`
# si el juego no está en tu colección).
COLLECTION_FIELDS_TO_ADD = ["own", "prevowned", "wanttobuy", "wanttoplay", "wishlist", "rating"]


def load_jsonl(path):
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def index_by_bgg_id(path):
    """bgg_id -> fila. `{}` si el archivo no existe todavía."""
    return {r["bgg_id"]: r for r in load_jsonl(path) if r.get("bgg_id")}


def main():
    bgg_rows = load_jsonl(BGG_DATA_PATH)
    if not bgg_rows:
        raise SystemExit(f"{BGG_DATA_PATH} está vacío o no existe; corré initialize_bgg_data.py primero.")

    collection_index = index_by_bgg_id(COLLECTION_PATH)
    cazagangas_index = index_by_bgg_id(CAZAGANGAS_DATA_PATH)

    integrated = []
    for bgg_row in bgg_rows:
        row = dict(bgg_row)
        bgg_id = row["bgg_id"]

        collection = collection_index.get(bgg_id)
        for field in COLLECTION_FIELDS_TO_ADD:
            row[field] = collection.get(field) if collection else None

        cazagangas = cazagangas_index.get(bgg_id)
        row["link_cazagangas"] = cazagangas["link_cazagangas"] if cazagangas else None
        row["cazagangas_status"] = cazagangas["status_http"] if cazagangas else None

        integrated.append(row)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)  # gitignored, no existe en un checkout limpio de CI
    OUTPUT_PATH.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in integrated) + "\n",
        encoding="utf-8",
    )
    en_coleccion = sum(1 for r in integrated if r["own"] is not None)
    con_cazagangas_ok = sum(1 for r in integrated if r["cazagangas_status"] == "200")
    print(f"OK: {len(integrated)} juegos integrados en {OUTPUT_PATH} "
          f"({en_coleccion} en tu colección de BGG, {con_cazagangas_ok} con link de Cazagangas que responde 200).")


if __name__ == "__main__":
    main()
