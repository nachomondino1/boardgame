"""Agrega un juego nuevo al catálogo (bgg_data.jsonl, que es el universo de
juegos) con `--add <id o nombre>`: busca el juego en el dataset de BGG y lo
suma a dos archivos de una:

  - bgg_data.jsonl: sus datos crudos de BGG.
  - cazagangas_data.jsonl: arma un slug best-effort a partir del nombre y lo
    verifica con un HEAD real (ver cazagangas_common.resolver_link) — si da
    200, guarda el link; si no, no guarda nada.

El estado del juego (Own, Want to buy…) no se carga acá: sale de tu colección
en BGG (ver refresh_bgg_data.py, que también trae los juegos de tu colección
que todavía no están en el catálogo). Un juego que no marques ahí es
"Watchlist".

Vive en collect_initial_data/ (no en bgg/ ni en cazagangas/) porque orquesta
las dos fuentes, no es parte de ninguna — importa bgg_common.py y
cazagangas_common.py como librerías.

Uso:
    python3 01_data_understanding/collect_initial_data/search_new_game.py --add 174430
    python3 01_data_understanding/collect_initial_data/search_new_game.py --add "Wingspan"
    python3 01_data_understanding/collect_initial_data/search_new_game.py --add 174430 --mode api
"""
import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "bgg"))
sys.path.insert(0, str(HERE / "cazagangas"))

from bgg_common import (  # noqa: E402
    BGG_DATA_PATH,
    fetch_dataset,
    fetch_attributes,
    find_in_dataset,
    load_bgg_cache,
    upsert_bgg_cache,
)
from cazagangas_common import resolver_link  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description="Suma un juego nuevo a bgg_data.jsonl / cazagangas_data.jsonl")
    parser.add_argument("--add", metavar="ID_O_NOMBRE", required=True, help="agrega un juego puntual")
    parser.add_argument("--mode", choices=["dummy", "api"], default="dummy",
                         help="dummy = dataset placeholder de Hugging Face (default); "
                              "api = xmlapi2 oficial (necesita BGG_TOKEN en .env)")
    args = parser.parse_args()

    dataset = fetch_dataset()
    row = find_in_dataset(args.add, dataset)
    bgg_id, nombre = row["id"], row["name"]
    if bgg_id in {r["bgg_id"] for r in load_bgg_cache()}:
        sys.exit(f"\"{args.add}\" resolvió a bgg_id={bgg_id} ({nombre}), que ya está en {BGG_DATA_PATH.name}.")

    attrs = fetch_attributes(bgg_id, args.mode, dataset) or {}
    upsert_bgg_cache({bgg_id: attrs})
    print(f"Agregado a {BGG_DATA_PATH.name}: {nombre} (bgg_id={bgg_id})")

    link, status = resolver_link(nombre, bgg_id)
    if status == "200":
        print(f"  Cazagangas: link verificado (200) y guardado: {link}")
    else:
        print(f"  Cazagangas: sin match verificado (status {status}), no se guardó ningún link.")


if __name__ == "__main__":
    main()
