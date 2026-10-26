"""Lee docs/data/data.json (salida de construct_data.py) y recorta el pool de
candidatos de Watchlist para que "¿Cuál comprar?" no tenga que mostrar/paginar
miles de tarjetas: descarta el percentil inferior de reviews en BGG (relativo
al propio Watchlist de cada corrida, no un número fijo) y se queda con los
TOP_N mejor puntuados del resto. Reescribe el mismo docs/data/data.json
(más chico) — correr siempre después de construct_data.py.

Nunca se filtra un juego con estado distinto de "Watchlist" (Own/Prev. owned/
Want to buy/Descartado): son tu curación manual en ludoteca.jsonl, no deben
poder desaparecer del sitio por tener pocas reviews o no estar en el top N de
rating — ver DATA_PLAYBOOK.md.
"""
import json
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_PATH = ROOT / "docs" / "data" / "data.json"

MIN_REVIEWS_PERCENTILE = 80  # descarta el Watchlist por debajo de este percentil de reviews_bgg
TOP_N_WATCHLIST = 5000  # de lo que queda, los TOP_N mejor puntuados (puntaje_bgg) por sobre el resto


def main():
    if not DATA_PATH.exists():
        raise SystemExit(f"No existe {DATA_PATH}; corré 02_data_preparation/construct_data.py primero.")
    games = json.loads(DATA_PATH.read_text(encoding="utf-8"))

    curados = [g for g in games if g.get("estado") != "Watchlist"]
    watchlist = [g for g in games if g.get("estado") == "Watchlist"]

    reviews_watchlist = sorted(g.get("reviews_bgg") or 0 for g in watchlist)
    min_reviews = statistics.quantiles(reviews_watchlist, n=100)[MIN_REVIEWS_PERCENTILE - 1]
    con_reviews = [g for g in watchlist if (g.get("reviews_bgg") or 0) >= min_reviews]
    con_reviews.sort(key=lambda g: g.get("puntaje_bgg") or 0, reverse=True)
    top_watchlist = con_reviews[:TOP_N_WATCHLIST]

    seleccionados = curados + top_watchlist

    DATA_PATH.write_text(json.dumps(seleccionados, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        f"OK: {len(seleccionados)} juegos escritos en {DATA_PATH} "
        f"({len(curados)} curados + {len(top_watchlist)} de Watchlist, "
        f"de {len(watchlist)} candidatos originales, corte en {min_reviews:.0f} reviews "
        f"= percentil {MIN_REVIEWS_PERCENTILE})"
    )


if __name__ == "__main__":
    main()
