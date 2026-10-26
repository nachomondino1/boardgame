"""Agrega juegos nuevos al catálogo, de dos formas:

1. --add <id o nombre>: busca el juego en el dataset de BGG y lo suma a
   las CUATRO fuentes que dependen de universo_juegos.jsonl, en un solo
   paso:
     - universo_juegos.jsonl: fila de identidad (bgg_id, nombre, bgg_url).
     - bgg_data.jsonl: sus datos de BGG (igual que el modo sin --add).
     - cazagangas_data.jsonl / link_cazagangas: arma un slug best-effort
       a partir del nombre y lo verifica con un HEAD real (ver
       cazagangas_common.resolver_link) — si da 200, carga el link solo;
       si no, deja link_cazagangas vacío para cargarlo a mano.
     - mis_datos.jsonl: agrega una fila stub (bgg_id + nombre, el resto
       vacío) para que vos completes estado/modo/etc. a mano — este
       script NUNCA decide esos campos, solo te evita el paso de crear
       la fila.
2. Sin --add (default): compara los bgg_id de universo_juegos.jsonl
   contra los que ya están en bgg_data.jsonl y, para los que falten,
   busca sus datos (Hugging Face o --mode api) y los agrega como fila
   nueva — nunca reescribe ni toca una fila que ya existía. No toca
   cazagangas_data.jsonl ni mis_datos.jsonl (eso es solo parte de --add,
   para no recorrer todo el catálogo con requests de red en cada corrida
   del cron — el chequeo masivo de links sigue siendo
   check_cazagangas_links.py --limit N, manual).

Es el reemplazo del viejo "refresh" de collect_bgg_data.py: ya no se
reconstruye bgg_data.jsonl entero en cada corrida (eso pisaba cualquier
edición manual, ver initialize_bgg_data.py), solo se completan los
bgg_id que todavía no tienen fila.

Vive en collect_initial_data/ (no en bgg/ ni en cazagangas/) porque orquesta
las dos fuentes, no es parte de ninguna — importa bgg_common.py y
cazagangas_common.py como librerías.

Uso:
    python3 01_data_understanding/collect_initial_data/search_new_game.py
    python3 01_data_understanding/collect_initial_data/search_new_game.py --add 174430
    python3 01_data_understanding/collect_initial_data/search_new_game.py --add "Wingspan"
    python3 01_data_understanding/collect_initial_data/search_new_game.py --mode api
"""
import argparse
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "bgg"))
sys.path.insert(0, str(HERE / "cazagangas"))

from bgg_common import (  # noqa: E402
    UNIVERSO_PATH,
    CRAWL_DELAY_SECONDS,
    load_universo,
    write_universo,
    load_bgg_cache,
    upsert_bgg_cache,
    fetch_dataset,
    fetch_attributes,
    find_in_dataset,
)
from cazagangas_common import resolver_link  # noqa: E402

MIS_DATOS_PATH = UNIVERSO_PATH.parent / "mis_datos.jsonl"
# Mismo orden que MIS_DATOS_FIELDS en verify_data_quality.py — si se toca
# uno, tocar el otro (verify_data_quality.py falla si no coinciden).
MIS_DATOS_FIELDS = ["bgg_id", "nombre", "estado", "modo", "transportable", "mi_puntaje", "pros", "cons", "notas"]


def add_game(term, dataset, existing_ids):
    row = find_in_dataset(term, dataset)
    bgg_id, nombre = row["id"], row["name"]
    if bgg_id in existing_ids:
        sys.exit(f"\"{term}\" resolvió a bgg_id={bgg_id} ({nombre}), que ya está en {UNIVERSO_PATH.name}.")

    link_cazagangas, status = resolver_link(nombre, bgg_id)
    if status != "200":
        link_cazagangas = ""

    new_row = {
        "bgg_id": bgg_id,
        "nombre": nombre,
        "bgg_url": f"https://boardgamegeek.com/boardgame/{bgg_id}",
        "link_cazagangas": link_cazagangas,
    }
    print(f"Agregando a {UNIVERSO_PATH.name}: {nombre} (bgg_id={bgg_id})")
    if link_cazagangas:
        print(f"  link_cazagangas resuelto y verificado (200): {link_cazagangas}")
    else:
        print(f"  link_cazagangas: sin match verificado (status {status}) — cargalo a mano si existe con otro slug.")
    return new_row


def stub_mis_datos(bgg_id, nombre):
    """Agrega una fila vacía (bgg_id/nombre nomás) a mis_datos.jsonl si
    el juego todavía no tiene una — nunca pisa una fila existente ni
    completa estado/modo/etc., eso queda 100% para vos."""
    if not MIS_DATOS_PATH.exists():
        rows = []
    else:
        with MIS_DATOS_PATH.open(encoding="utf-8") as f:
            rows = [json.loads(line) for line in f if line.strip()]

    ya_existe = any((r.get("bgg_id") or "") == bgg_id and bgg_id for r in rows) or \
        any(r.get("nombre") == nombre for r in rows)
    if ya_existe:
        return False

    stub = {k: "" for k in MIS_DATOS_FIELDS}
    stub["bgg_id"], stub["nombre"] = bgg_id, nombre
    rows.append(stub)

    with MIS_DATOS_PATH.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps({k: r.get(k, "") for k in MIS_DATOS_FIELDS}, ensure_ascii=False))
            f.write("\n")
    print(f"  Fila stub agregada a mis_datos.jsonl — completá estado/modo/etc. a mano.")
    return True


def missing_ids(universo_rows, cache_rows):
    universo_ids = [(r.get("bgg_id") or "").strip() for r in universo_rows]
    universo_ids = [i for i in universo_ids if i]
    cached_ids = {r.get("bgg_id") for r in cache_rows if r.get("bgg_id")}
    return [i for i in universo_ids if i not in cached_ids]


def main():
    parser = argparse.ArgumentParser(description="Suma juegos nuevos a universo_juegos.jsonl / bgg_data.jsonl / cazagangas_data.jsonl / mis_datos.jsonl")
    parser.add_argument("--add", metavar="ID_O_NOMBRE", help="agrega un juego puntual a las cuatro fuentes")
    parser.add_argument("--mode", choices=["dummy", "api"], default="dummy",
                         help="dummy = dataset placeholder de Hugging Face (default); "
                              "api = xmlapi2 oficial (requiere app aprobada)")
    args = parser.parse_args()

    dataset = fetch_dataset() if args.mode == "dummy" else {}

    universo_rows = load_universo()

    if args.add:
        existing_ids = {r["bgg_id"] for r in universo_rows if r.get("bgg_id")}
        new_row = add_game(args.add, dataset, existing_ids)
        universo_rows.append(new_row)
        write_universo(universo_rows)
        stub_mis_datos(new_row["bgg_id"], new_row["nombre"])

    cache_rows = load_bgg_cache()
    pending = missing_ids(universo_rows, cache_rows)
    if not pending:
        print(f"Nada pendiente: todos los bgg_id de {UNIVERSO_PATH.name} ya tienen fila en bgg_data.jsonl.")
        return

    print(f"{len(pending)} juego(s) en {UNIVERSO_PATH.name} sin datos de BGG todavía, buscando...")
    updates = {}
    for i, bgg_id in enumerate(pending):
        attrs = fetch_attributes(bgg_id, args.mode, dataset)
        if attrs is None:
            print(f"  bgg_id={bgg_id}: sin match en la fuente, se agrega fila vacía (reintentar más adelante).", file=sys.stderr)
            attrs = {}
        updates[bgg_id] = attrs
        if args.mode == "api" and i < len(pending) - 1:
            time.sleep(CRAWL_DELAY_SECONDS)

    added, updated = upsert_bgg_cache(updates)
    print(f"OK: {added} fila(s) nueva(s) en bgg_data.jsonl (ninguna fila existente fue tocada).")


if __name__ == "__main__":
    main()
