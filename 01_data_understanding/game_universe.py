"""Combina las dos fuentes de qué juegos existen en el universo del catálogo:
- ludoteca/ludoteca_source.py: lo que tenés o tuviste (mi_ludoteca.json,
  Estado Own/Prev. owned)
- bgg/bgg_top1000.csv: el top N de BGG (bgg/collect_bgg_rankings.py), como
  candidatos a comprar — cualquiera de esos juegos que no sea ya tuyo entra
  con Estado "Watchlist".

Vive acá (no adentro de ludoteca/ ni de bgg/) porque junta las dos: es la
única pieza de 01_data_understanding que mira más de una fuente a la vez.
Tanto 02_data_preparation/integrate_data.py como
01_data_understanding/bosque_ludico/resolve_bosque_links.py importan
load_universe() en vez de leer mi_ludoteca.json o el ranking de BGG por su
cuenta — mismo criterio que ludoteca_source.load_games() ya aplicaba antes
de que existiera esta capa.
"""
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "ludoteca"))
from ludoteca_source import load_games  # noqa: E402

BGG_TOP_PATH = Path(__file__).resolve().parent / "bgg" / "bgg_top1000.csv"


def _csv_int(s):
    return int(s) if s else None


def _csv_float(s):
    return float(s) if s else None


def load_candidates(exclude_bgg_ids):
    """Juegos del top N de BGG que no están ya en tu ludoteca. Si
    bgg_top1000.csv no corrió todavía, devuelve una lista vacía (no bloquea
    el resto del pipeline, igual que el resto de los pasos opcionales de
    01_data_understanding).

    bgg_top1000.csv ya tiene los números en formato US (punto decimal, sin
    separador de miles) tal como los escribió collect_bgg_rankings.py — acá
    se parsean con float()/int() directo, NO con locale es-AR."""
    if not BGG_TOP_PATH.exists():
        return []

    candidates = []
    with BGG_TOP_PATH.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row["bgg_id"] in exclude_bgg_ids:
                continue
            candidates.append({
                "nombre": row["nombre"],
                "nombre_en": row["nombre"],
                "nombre_es": "",
                "bgg_id": row["bgg_id"],
                "anio": _csv_int(row.get("anio")),
                "ranking_bgg": _csv_int(row.get("ranking_bgg")),
                "puntaje_bgg": _csv_float(row.get("puntaje_bgg")),
                "reviews_bgg": _csv_int(row.get("reviews_bgg")),
                "bgg_url": row["bgg_url"],
                "estado": "Watchlist",
            })
    return candidates


def load_universe():
    """mi_ludoteca.json (Own/Prev. owned) + candidatos del top N de BGG que
    no sean ya tuyos. Dedupe por bgg_id (el identificador común a las dos
    fuentes — ver ludoteca_source.extract_bgg_id), nunca por nombre: dos
    títulos pueden diferir en mayúsculas/acentos/edición. Tu ludoteca
    siempre va primero y gana ante cualquier duplicado."""
    own_games = load_games()
    owned_bgg_ids = {g["bgg_id"] for g in own_games if g.get("bgg_id")}
    candidates = load_candidates(owned_bgg_ids)
    return own_games + candidates


def main():
    universe = load_universe()
    own = sum(1 for g in universe if g.get("estado") in ("Own", "Prev. owned"))
    watchlist = sum(1 for g in universe if g.get("estado") == "Watchlist")
    print(f"{len(universe)} juegos en el universo: {own} propios (mi_ludoteca.json), {watchlist} candidatos (BGG top N)")


if __name__ == "__main__":
    main()
