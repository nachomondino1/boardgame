"""Bootstrap de data/01_data_understanding/bgg_data.jsonl (el universo de
juegos) a partir del top N del ranking de BGG, desde el dataset de Hugging Face.

[CUIDADO] Este script se corre UNA SOLA VEZ (ya se corrió): arma el
universo de juegos desde cero y reescribe bgg_data.jsonl entero. NO volver a
correrlo salvo que de verdad se quiera reiniciar el catálogo — HF trae un
snapshot de 2025 que ya está desactualizado respecto a lo que
refresh_bgg_data.py fue trayendo de la API, así que una corrida nueva te pisa
esos datos más nuevos sin aviso.

Para agregar un juego nuevo al universo ya existente, usar
refresh_bgg_data.py --add (no este script). Para actualizar datos que cambian,
refresh_bgg_data.py.

Uso:
    python3 01_data_understanding/collect_initial_data/bgg/initialize_bgg_data.py
    python3 01_data_understanding/collect_initial_data/bgg/initialize_bgg_data.py --top 1500
"""
import argparse
import sys

from bgg_common import BGG_DATA_PATH, dataset_row_to_raw, fetch_dataset, write_bgg_cache_full

TOP_N_DEFAULT = 1000


def main():
    parser = argparse.ArgumentParser(
        description="Bootstrap único de bgg_data.jsonl. No correr de nuevo si el catálogo ya existe (ver docstring)."
    )
    parser.add_argument("--top", type=int, default=TOP_N_DEFAULT, help="tamaño del universo (default 1000)")
    parser.add_argument("--force", action="store_true", help="correr aunque bgg_data.jsonl ya exista")
    args = parser.parse_args()

    if BGG_DATA_PATH.exists() and not args.force:
        sys.exit(
            f"{BGG_DATA_PATH} ya existe — este script es solo para el bootstrap inicial.\n"
            "Para agregar un juego nuevo: refresh_bgg_data.py --add <id o nombre>.\n"
            "Para reiniciar el catálogo desde cero a propósito: --force (vas a perder "
            "lo que trajo refresh_bgg_data.py)."
        )

    dataset = fetch_dataset()
    ranked = sorted(dataset.values(), key=lambda r: float(r.get("Board Game Rank") or 10**9))[: args.top]
    write_bgg_cache_full([dataset_row_to_raw(r) for r in ranked])
    print(f"\nOK: {len(ranked)} juego(s) del top {args.top} de BGG en {BGG_DATA_PATH.name}.")


if __name__ == "__main__":
    main()
