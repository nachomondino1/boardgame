"""Suma una columna nueva a TODAS las filas de
data/01_data_understanding/bgg_data.jsonl, extrayéndola del dataset de
Hugging Face (o de la API oficial con --mode api) para cada bgg_id que
ya está en el catálogo.

No reemplaza ningún valor ya cargado a mano: si una fila ya tiene algo
en el campo nuevo (por una corrida anterior, o porque se editó a mano
con modify_values.py), esa fila se saltea salvo que se pase --force.

Antes de correr esto hay que agregar la clave del campo nuevo a
BGG_CACHE_FIELDS en bgg_common.py y mapearla en dataset_row_to_attributes
/fetch_api_attributes (este script no inventa de dónde sale el dato,
solo orquesta la corrida sobre filas ya existentes).

Uso:
    python3 01_data_understanding/collect_initial_data/bgg/extract_new_fields.py jug_best_min jug_best_max
    python3 01_data_understanding/collect_initial_data/bgg/extract_new_fields.py complejidad --force
"""
import argparse
import time

from bgg_common import (
    BGG_DATA_PATH,
    BGG_CACHE_FIELDS,
    CRAWL_DELAY_SECONDS,
    load_bgg_cache,
    upsert_bgg_cache,
    fetch_dataset,
    fetch_attributes,
)


def main():
    parser = argparse.ArgumentParser(description="Extrae columnas nuevas para todos los juegos ya cacheados")
    parser.add_argument("campos", nargs="+", help="nombres de campo a (re)extraer, ya declarados en BGG_CACHE_FIELDS")
    parser.add_argument("--force", action="store_true", help="pisa el valor aunque la fila ya tenga algo cargado")
    parser.add_argument("--mode", choices=["dummy", "api"], default="dummy")
    args = parser.parse_args()

    unknown = [c for c in args.campos if c not in BGG_CACHE_FIELDS]
    if unknown:
        parser.error(f"Campo(s) no declarados en BGG_CACHE_FIELDS: {', '.join(unknown)}")

    dataset = fetch_dataset() if args.mode == "dummy" else {}
    cache_rows = load_bgg_cache()

    pending = [r for r in cache_rows if args.force or any(not r.get(c) for c in args.campos)]
    print(f"{len(pending)}/{len(cache_rows)} fila(s) a extraer ({', '.join(args.campos)}).")

    updates = {}
    for i, row in enumerate(pending):
        bgg_id = row.get("bgg_id")
        attrs = fetch_attributes(bgg_id, args.mode, dataset) or {}
        updates[bgg_id] = {c: attrs.get(c) for c in args.campos if c in attrs}
        if args.mode == "api" and i < len(pending) - 1:
            time.sleep(CRAWL_DELAY_SECONDS)

    added, updated = upsert_bgg_cache(updates)
    print(f"OK: {updated} fila(s) actualizada(s) en {BGG_DATA_PATH.name} (solo los campos pedidos).")


if __name__ == "__main__":
    main()
