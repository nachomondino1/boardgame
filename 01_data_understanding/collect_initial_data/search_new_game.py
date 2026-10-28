"""Agrega juegos nuevos al catálogo, de tres formas:

0. --add-all: bulk, agrega TODO bgg_id del dataset que falte en
   universo_juegos.jsonl, con link_cazagangas vacío (resolverlo juego
   por juego para miles de filas es muy costoso por ahora). Solo con
   --mode dummy.
1. --add <id o nombre>: busca el juego en el dataset de BGG y lo suma a
   universo_juegos.jsonl / bgg_data.jsonl / cazagangas_data.jsonl en un
   solo paso:
     - universo_juegos.jsonl: fila de identidad (bgg_id, nombre, bgg_url).
     - bgg_data.jsonl: sus datos de BGG (igual que sin --add).
     - cazagangas_data.jsonl / link_cazagangas: arma un slug best-effort
       a partir del nombre y lo verifica con un HEAD real (ver
       cazagangas_common.resolver_link) — si da 200, carga el link solo;
       si no, deja link_cazagangas vacío para cargarlo a mano.
   ludoteca.jsonl NO se toca por default: un juego nuevo sin curar es
   "Watchlist" implícito (ver integrate_data.py, ESTADO_DEFAULT) — no
   hace falta una fila para eso. Si ya sabés que lo tenés, lo tuviste, o
   lo querés comprar, pasá --estado para crear la fila de una:
       --add 174430 --estado Own
   Eso agrega una fila a ludoteca.jsonl con ese estado y el resto vacío
   (transportable/mi_puntaje/pros/cons/notas: 100% tu criterio, nunca se
   infiere) — nunca pisa una fila que ya exista.
2. Sin --add (default): compara los bgg_id de universo_juegos.jsonl
   contra los que ya están en bgg_data.jsonl y, para los que falten,
   busca sus datos (Hugging Face o --mode api) y los agrega como fila
   nueva — nunca reescribe ni toca una fila que ya existía. No toca
   cazagangas_data.jsonl ni ludoteca.jsonl (eso es solo parte de --add,
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
    python3 01_data_understanding/collect_initial_data/search_new_game.py --add "Wingspan" --estado "Want to buy"
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

LUDOTECA_PATH = UNIVERSO_PATH.parent / "ludoteca.jsonl"
# Mismo orden que LUDOTECA_FIELDS en verify_data_quality.py — si se toca
# uno, tocar el otro (verify_data_quality.py falla si no coinciden).
LUDOTECA_FIELDS = ["bgg_id", "nombre", "estado", "transportable", "mi_puntaje", "pros", "cons", "notas"]
# Mismo set que ESTADOS_VALIDOS en verify_data_quality.py. "Watchlist" es
# válido acá también (curarlo explícito, ej. para dejar una nota, sin
# poseerlo) aunque sea el default implícito de un juego sin fila.
ESTADOS_VALIDOS = ["Own", "Prev. owned", "Want to buy", "Watchlist", "Descartado"]


def add_game(term, dataset, existing_ids, mode):
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

    attrs = fetch_attributes(bgg_id, mode, dataset) or {}
    return new_row, attrs


def add_to_ludoteca(bgg_id, nombre, estado):
    """Agrega una fila a ludoteca.jsonl (`estado` + bgg_id/nombre nomás;
    transportable/mi_puntaje/pros/cons/notas quedan vacíos, 100% tu
    criterio). Nunca pisa una fila existente — si el juego ya tiene fila,
    no hace nada (editá a mano, o con modify_values.py si existiera un
    equivalente para ludoteca.jsonl)."""
    if not LUDOTECA_PATH.exists():
        rows = []
    else:
        with LUDOTECA_PATH.open(encoding="utf-8") as f:
            rows = [json.loads(line) for line in f if line.strip()]

    ya_existe = any((r.get("bgg_id") or "") == bgg_id and bgg_id for r in rows) or \
        any(r.get("nombre") == nombre for r in rows)
    if ya_existe:
        print(f"  {nombre} ya tiene fila en ludoteca.jsonl, no se toca.")
        return False

    nueva = {k: "" for k in LUDOTECA_FIELDS}
    nueva["bgg_id"], nueva["nombre"] = bgg_id, nombre
    nueva["estado"] = estado
    rows.append(nueva)

    with LUDOTECA_PATH.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps({k: r.get(k, "") for k in LUDOTECA_FIELDS}, ensure_ascii=False))
            f.write("\n")
    print(f"  Fila agregada a ludoteca.jsonl: estado \"{estado}\" — completá el resto a mano.")
    return True


def add_all_missing(universo_rows, dataset):
    """Agrega una fila de identidad para TODO bgg_id del dataset que
    todavía no esté en universo_juegos.jsonl — bulk, sin resolver
    Cazagangas (--estado tampoco aplica acá, es por juego): hoy
    verificar el link de Cazagangas de miles de juegos de una es
    demasiado costoso (HEAD real por juego, con delay), así que queda
    vacío para cargar a mano o resolver más adelante con search_new_game.py
    --add puntual."""
    existing_ids = {r["bgg_id"] for r in universo_rows if r.get("bgg_id")}
    nuevas = [
        {"bgg_id": bgg_id, "nombre": row["name"], "bgg_url": f"https://boardgamegeek.com/boardgame/{bgg_id}", "link_cazagangas": ""}
        for bgg_id, row in dataset.items()
        if bgg_id not in existing_ids
    ]
    universo_rows.extend(nuevas)
    print(f"Agregando {len(nuevas)} juego(s) nuevo(s) del dataset a {UNIVERSO_PATH.name} (link_cazagangas vacío).")
    return nuevas


def missing_ids(universo_rows, cache_rows):
    universo_ids = [(r.get("bgg_id") or "").strip() for r in universo_rows]
    universo_ids = [i for i in universo_ids if i]
    cached_ids = {r.get("bgg_id") for r in cache_rows if r.get("bgg_id")}
    return [i for i in universo_ids if i not in cached_ids]


def main():
    parser = argparse.ArgumentParser(description="Suma juegos nuevos a universo_juegos.jsonl / bgg_data.jsonl / cazagangas_data.jsonl")
    parser.add_argument("--add", metavar="ID_O_NOMBRE", help="agrega un juego puntual")
    parser.add_argument("--add-all", action="store_true",
                         help="agrega TODO bgg_id del dataset que falte en universo_juegos.jsonl (bulk, sin Cazagangas)")
    parser.add_argument("--estado", choices=ESTADOS_VALIDOS, default=None,
                         help="si se pasa, también agrega una fila a ludoteca.jsonl con este estado "
                              "(sin esto, el juego nuevo queda como Watchlist implícito, sin fila)")
    parser.add_argument("--mode", choices=["dummy", "api"], default="dummy",
                         help="dummy = dataset placeholder de Hugging Face (default); "
                              "api = xmlapi2 oficial (requiere app aprobada)")
    args = parser.parse_args()
    if args.add_all and args.add:
        parser.error("--add-all y --add son excluyentes")
    if args.add_all and args.mode == "api":
        parser.error("--add-all solo con --mode dummy (miles de requests a xmlapi2 no es razonable)")

    universo_rows = load_universo()
    updates = {}

    # Bajar el dataset (~94MB) es caro — solo vale la pena si de verdad hay
    # algo que resolver con él (--add/--add-all, o un bgg_id sin fila
    # todavía en bgg_data.jsonl). La corrida normal de sync_data.sh, sin
    # juegos nuevos, no debería pagar ese costo por nada.
    necesita_dataset = args.add_all or args.add or missing_ids(universo_rows, load_bgg_cache())
    dataset = fetch_dataset() if args.mode == "dummy" and necesita_dataset else {}

    if args.add_all:
        add_all_missing(universo_rows, dataset)
        write_universo(universo_rows)

    if args.add:
        existing_ids = {r["bgg_id"] for r in universo_rows if r.get("bgg_id")}
        new_row, attrs = add_game(args.add, dataset, existing_ids, args.mode)
        universo_rows.append(new_row)
        write_universo(universo_rows)
        if args.estado:
            add_to_ludoteca(new_row["bgg_id"], new_row["nombre"], args.estado)
        else:
            print(f"  Sin --estado: queda como Watchlist implícito (no se tocó ludoteca.jsonl).")
        updates[new_row["bgg_id"]] = attrs  # ya resuelto arriba, no lo volvemos a pedir abajo

    cache_rows = load_bgg_cache()
    pending = [i for i in missing_ids(universo_rows, cache_rows) if i not in updates]
    if not pending and not updates:
        print(f"Nada pendiente: todos los bgg_id de {UNIVERSO_PATH.name} ya tienen fila en bgg_data.jsonl.")
        return

    if pending:
        print(f"{len(pending)} juego(s) en {UNIVERSO_PATH.name} sin datos de BGG todavía, buscando...")
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
