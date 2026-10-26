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

Con --find-group-candidates (uso manual, no corre en el cron): en vez de
recortar y escribir, imprime clusters candidatos a grupo (mismo prefijo antes
de ":"/"–"), para curar a mano en grupos.json — solo sobre los seleccionados
(curados + top Watchlist), nunca sobre el universo completo (28.000 juegos
genera demasiado ruido para revisar uno por uno, ver conversación del
2026-10-26). Es un generador de candidatos, igual que el de grupos.json
mismo: nunca se auto-aplica, lo decide un humano.
"""
import json
import re
import statistics
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_PATH = ROOT / "docs" / "data" / "data.json"
GRUPOS_PATH = ROOT / "data" / "01_data_understanding" / "grupos.json"

MIN_REVIEWS_PERCENTILE = 80  # descarta el Watchlist por debajo de este percentil de reviews_bgg
TOP_N_WATCHLIST = 5000  # de lo que queda, los TOP_N mejor puntuados (puntaje_bgg) por sobre el resto


def seleccionar(games):
    curados = [g for g in games if g.get("estado") != "Watchlist"]
    watchlist = [g for g in games if g.get("estado") == "Watchlist"]

    reviews_watchlist = sorted(g.get("reviews_bgg") or 0 for g in watchlist)
    min_reviews = statistics.quantiles(reviews_watchlist, n=100)[MIN_REVIEWS_PERCENTILE - 1]
    con_reviews = [g for g in watchlist if (g.get("reviews_bgg") or 0) >= min_reviews]
    con_reviews.sort(key=lambda g: g.get("puntaje_bgg") or 0, reverse=True)
    top_watchlist = con_reviews[:TOP_N_WATCHLIST]

    return curados + top_watchlist, len(watchlist), min_reviews


def prefijo(nombre):
    return re.split(r"[:–—]", nombre, maxsplit=1)[0].strip()


def find_group_candidates(seleccionados):
    """Imprime clusters con 2+ juegos del mismo prefijo donde al menos uno
    no está todavía en grupos.json — ver docstring del módulo. No escribe
    nada: el humano decide cuáles son de verdad "mismo motor" (ver criterio
    en grupos.json) y los agrega a mano."""
    grupos_data = json.loads(GRUPOS_PATH.read_text(encoding="utf-8")) if GRUPOS_PATH.exists() else {"grupos": []}
    grupo_por_juego = {j: g["nombre"] for g in grupos_data["grupos"] for j in g["juegos"]}

    por_prefijo = defaultdict(list)
    for g in seleccionados:
        por_prefijo[prefijo(g["nombre"])].append(g["nombre"])

    existentes_con_faltantes = 0
    nuevos = 0
    for pref, nombres in sorted(por_prefijo.items()):
        if len(nombres) < 2:
            continue
        sin_grupo = [n for n in nombres if n not in grupo_por_juego]
        con_grupo = [n for n in nombres if n in grupo_por_juego]
        if not sin_grupo:
            continue
        if con_grupo:
            existentes_con_faltantes += 1
            print(f"--- {pref} (grupo existente: {grupo_por_juego[con_grupo[0]]}) ---")
        else:
            nuevos += 1
            print(f"--- {pref} (posible grupo nuevo, {len(nombres)} juegos) ---")
        for n in sin_grupo:
            print("   ", n)
    print(f"\n{existentes_con_faltantes} grupos existentes con variantes sin agregar, "
          f"{nuevos} clusters candidatos a grupo nuevo, sobre {len(seleccionados)} juegos seleccionados.")


def main():
    if not DATA_PATH.exists():
        raise SystemExit(f"No existe {DATA_PATH}; corré 02_data_preparation/construct_data.py primero.")
    games = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    seleccionados, total_watchlist, min_reviews = seleccionar(games)

    if "--find-group-candidates" in sys.argv:
        find_group_candidates(seleccionados)
        return

    DATA_PATH.write_text(json.dumps(seleccionados, ensure_ascii=False, indent=2), encoding="utf-8")
    curados = sum(1 for g in seleccionados if g.get("estado") != "Watchlist")
    print(
        f"OK: {len(seleccionados)} juegos escritos en {DATA_PATH} "
        f"({curados} curados + {len(seleccionados) - curados} de Watchlist, "
        f"de {total_watchlist} candidatos originales, corte en {min_reviews:.0f} reviews "
        f"= percentil {MIN_REVIEWS_PERCENTILE})"
    )


if __name__ == "__main__":
    main()
