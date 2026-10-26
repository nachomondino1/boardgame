"""Edita a mano uno o más campos de un juego puntual en
data/01_data_understanding/bgg_data.jsonl, sin tocar el resto de la fila
ni ninguna otra fila del archivo.

Caso típico: BGG trae el rango de jugadores de CAJA (jug_min/jug_max),
pero vos preferís cargar el de "Community" de la ficha — este script es
la vía para pisar ese valor puntual sin que una corrida posterior de
search_new_game.py te lo vuelva a pisar a él (ese script nunca toca una
fila que ya existe, solo agrega las que faltan).

Uso:
    python3 01_data_understanding/collect_initial_data/bgg/modify_values.py 409750 jug_min=2 jug_max=4
    python3 01_data_understanding/collect_initial_data/bgg/modify_values.py 174430 complejidad=3.8 anio=2017
"""
import argparse
import sys

from bgg_common import BGG_DATA_PATH, BGG_CACHE_FIELDS, LIST_FIELDS, load_bgg_cache, upsert_bgg_cache


def parse_assignment(raw):
    if "=" not in raw:
        sys.exit(f"Formato inválido \"{raw}\", esperaba campo=valor")
    key, value = raw.split("=", 1)
    key = key.strip()
    if key not in BGG_CACHE_FIELDS:
        sys.exit(f"Campo desconocido \"{key}\". Campos válidos: {', '.join(BGG_CACHE_FIELDS)}")
    if key in LIST_FIELDS:
        value = [v.strip() for v in value.split("|") if v.strip()]
    return key, value


def main():
    parser = argparse.ArgumentParser(description="Edita campos puntuales de un juego en bgg_data.jsonl")
    parser.add_argument("bgg_id", help="bgg_id del juego a editar")
    parser.add_argument("asignaciones", nargs="+", metavar="campo=valor",
                         help="uno o más campo=valor (listas como mecanicas/categorias: separadas por |)")
    args = parser.parse_args()

    cache_rows = load_bgg_cache()
    if not any(r.get("bgg_id") == args.bgg_id for r in cache_rows):
        sys.exit(f"No encontré bgg_id={args.bgg_id} en {BGG_DATA_PATH.name}. "
                  "Si es un juego nuevo, correr primero search_new_game.py --add.")

    attrs = dict(parse_assignment(a) for a in args.asignaciones)
    upsert_bgg_cache({args.bgg_id: attrs})

    print(f"OK: bgg_id={args.bgg_id} actualizado en {BGG_DATA_PATH.name} — {attrs}")


if __name__ == "__main__":
    main()
