"""Bootstrap de data/01_data_understanding/universo_juegos.jsonl +
bgg_data.jsonl, a partir del top N del ranking de BGG + ludoteca propia.

[CUIDADO] Este script se corre UNA SOLA VEZ (ya se corrió): arma el
universo de juegos desde cero y reescribe bgg_data.jsonl entero contra
el dataset de Hugging Face. NO volver a correrlo salvo que de verdad se
quiera reiniciar el catálogo — HF trae un snapshot de 2025 que ya está
desactualizado respecto a lo que vos fuiste corrigiendo a mano en
bgg_data.jsonl (ej. jug_min/max de community en vez de caja), así que
una corrida nueva te pisa esos cambios manuales sin aviso.

Para agregar un juego nuevo al universo ya existente, usar
search_new_game.py (no este script). Para editar un campo puntual,
modify_values.py. Para sumar una columna nueva a todas las filas,
extract_new_fields.py.

Uso:
    python3 01_data_understanding/collect_initial_data/bgg/initialize_bgg_data.py
    python3 01_data_understanding/collect_initial_data/bgg/initialize_bgg_data.py --top 1500
"""
import argparse
import json
import re
import sys
import urllib.parse
from pathlib import Path

from bgg_common import (
    UNIVERSO_PATH,
    extract_bgg_id,
    fetch_dataset,
    write_universo,
    write_bgg_cache_full,
    dataset_row_to_attributes,
)

HERE = Path(__file__).resolve().parent
LUDOTECA_PATH = HERE / "ludoteca" / "mi_ludoteca.json"
TOP_N_DEFAULT = 1000

# Mismo patrón que tenía ludoteca_source.py: para ediciones locales o
# nombres que no matchean bien contra BGG, se fuerza el término de
# búsqueda o se marca el juego como sin ficha razonable en BGG. Solo se
# usa acá (una sola lectura de mi_ludoteca.json, una sola vez).
BGG_SEARCH_OVERRIDES = {
    "Fantasma Blitz": "Ghost Blitz",
    "Misterio (Ruibal)": "Misterio",
    "Alcatraz: la fuga imposible": "Alcatraz",
    "Memotest (Ruibal)": "Memory",
    "Batalla Naval": "Battleship",
    "Ludo (Mickey and Kids)": "Pachisi",
}
BGG_SKIP = {
    "Ajedrez y damas",
    "Ajedrez / Backgammon (caja rosa)",
    "Puzzles Trefl 1000 piezas",
    "Mente Matic (Habano)",
}


def load_ludoteca_once():
    if not LUDOTECA_PATH.exists():
        print(f"Aviso: no encontré {LUDOTECA_PATH}, bootstrap sin juegos propios.", file=sys.stderr)
        return []

    entries = json.loads(LUDOTECA_PATH.read_text(encoding="utf-8"))
    own = []
    for entry in entries:
        nombre_en = (entry.get("nombre_en") or "").strip()
        if not nombre_en:
            continue
        nombre = entry.get("nombre_es") or nombre_en

        if nombre_en in BGG_SKIP:
            bgg_url = None
        elif entry.get("bgg_url"):
            bgg_url = entry["bgg_url"]
        else:
            term = BGG_SEARCH_OVERRIDES.get(nombre_en) or re.sub(r"\s*\([^)]*\)\s*$", "", nombre_en).strip()
            bgg_url = "https://boardgamegeek.com/geeksearch.php?action=search&objecttype=boardgame&q=" + urllib.parse.quote(term)

        own.append({
            "bgg_id": entry.get("bgg_id") or extract_bgg_id(bgg_url) or "",
            "nombre": nombre,
            "bgg_url": bgg_url or "",
        })
    return own


def bootstrap(dataset, top_n):
    own = load_ludoteca_once()
    owned_ids = {g["bgg_id"] for g in own if g["bgg_id"]}
    rows = list(own)

    ranked = sorted(dataset.values(), key=lambda r: float(r.get("Board Game Rank") or 10**9))
    added = 0
    for r in ranked:
        if added >= top_n:
            break
        if r["id"] in owned_ids:
            continue
        rows.append({
            "bgg_id": r["id"],
            "nombre": r["name"],
            "bgg_url": f"https://boardgamegeek.com/boardgame/{r['id']}",
        })
        added += 1

    print(f"Bootstrap: {len(own)} juego(s) propios + {added} candidatos del top {top_n} de BGG "
          f"(identidad nomás — cargá el estado de cada uno en mis_datos.jsonl a mano).")
    return rows


def build_full_cache(universo_rows, dataset):
    ids = [(r.get("bgg_id") or "").strip() for r in universo_rows]
    ids = [i for i in ids if i]
    cache_rows = []
    for bgg_id in ids:
        source = dataset.get(bgg_id)
        attrs = dataset_row_to_attributes(source) if source else None
        row = {"bgg_id": bgg_id}
        if attrs:
            row.update(attrs)
        cache_rows.append(row)
    return cache_rows


def main():
    parser = argparse.ArgumentParser(
        description="Bootstrap único de universo_juegos.jsonl + bgg_data.jsonl. "
                    "No correr de nuevo si el catálogo ya existe (ver docstring)."
    )
    parser.add_argument("--top", type=int, default=TOP_N_DEFAULT, help="tamaño del universo (default 1000)")
    parser.add_argument("--force", action="store_true", help="correr aunque universo_juegos.jsonl ya exista")
    args = parser.parse_args()

    if UNIVERSO_PATH.exists() and not args.force:
        sys.exit(
            f"{UNIVERSO_PATH} ya existe — este script es solo para el bootstrap inicial.\n"
            "Para agregar un juego nuevo: search_new_game.py --add <id o nombre>.\n"
            "Para reiniciar el catálogo desde cero a propósito: --force (vas a perder "
            "cualquier edición manual en bgg_data.jsonl)."
        )

    dataset = fetch_dataset()
    rows = bootstrap(dataset, args.top)
    write_universo(rows)

    cache_rows = build_full_cache(rows, dataset)
    write_bgg_cache_full(cache_rows)
    print(f"\nOK: {len(rows)} juego(s) en {UNIVERSO_PATH.name}, {len(cache_rows)} con datos de BGG.")


if __name__ == "__main__":
    main()
