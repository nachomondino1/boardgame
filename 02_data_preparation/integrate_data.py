"""Integra las fuentes ya recolectadas en 01_data_understanding/ en un único
docs/data/data.json: el Sheet (sheet_source.load_games(), fuente de verdad)
+ el caché de BGG + el dataset de precios de Bosque Lúdico, estos dos
últimos solo completando lo que el Sheet dejó vacío — nunca pisan un valor
cargado a mano.

Solo integra: la recolección cruda de cada fuente vive en 01_data_understanding/
(sheet/, bgg/, bosque_ludico/), este script no le pega a ningún sitio externo.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "01_data_understanding" / "sheet"))

from sheet_source import (  # noqa: E402
    NUMERIC_FIELDS_FLOAT, NUMERIC_FIELDS_INT, load_games, to_float, to_int,
)

OUTPUT_PATH = ROOT / "docs" / "data" / "data.json"
BGG_CACHE_DIR = ROOT / "docs" / "data" / "cache" / "bgg"
BOSQUE_DATA_PATH = ROOT / "01_data_understanding" / "bosque_ludico" / "bosque_data.json"

# Campos que, si el Sheet los dejó vacíos, se completan con el caché de BGG
# (ver 01_data_understanding/bgg/enrich_bgg.py) cuando el juego tiene un
# link exacto a BGG. El Sheet manda siempre: esto nunca pisa un valor ya
# cargado a mano.
BGG_FALLBACK_FIELDS = (
    "disenador", "edad_min", "jug_min", "jug_max", "jug_best_min", "jug_best_max",
    "duracion", "complejidad", "puntaje_bgg", "reviews_bgg", "ranking_bgg",
)


def apply_bgg_fallback(game):
    bgg_id_match = re.search(r"/boardgame(?:expansion)?/(\d+)", game.get("bgg_url") or "")
    if not bgg_id_match:
        return
    cache_path = BGG_CACHE_DIR / f"{bgg_id_match.group(1)}.json"
    try:
        cached = json.loads(cache_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return

    for field in BGG_FALLBACK_FIELDS:
        if game.get(field) is not None:
            continue
        value = cached.get(field)
        if value is None:
            continue
        if field in NUMERIC_FIELDS_FLOAT:
            game[field] = to_float(str(value))
        elif field in NUMERIC_FIELDS_INT:
            game[field] = to_int(str(value))
        else:
            game[field] = value


def load_bosque_precios():
    """{nombre: {precio, disponible, ...}} desde
    01_data_understanding/bosque_ludico/collect_bosque_precios.py, si corrió.
    Paso manual, no bloquea el build si no existe (ver
    01_data_understanding/README.md)."""
    if not BOSQUE_DATA_PATH.exists():
        return {}
    entries = json.loads(BOSQUE_DATA_PATH.read_text(encoding="utf-8"))
    return {e["nombre"]: e for e in entries if "precio" in e}


def apply_bosque_fallback(game, precios_by_nombre):
    """Completa costo/link_tienda con el precio relevado de Bosque Lúdico
    cuando el Sheet los dejó vacíos. El Sheet manda siempre."""
    precio = precios_by_nombre.get(game.get("nombre"))
    if not precio:
        return
    if game.get("costo") is None and precio.get("precio") is not None:
        game["costo"] = to_int(str(precio["precio"]))
    if not game.get("link_tienda") and precio.get("bosque_url"):
        game["link_tienda"] = precio["bosque_url"]


def main():
    games = load_games()
    bosque_precios = load_bosque_precios()
    for game in games:
        apply_bgg_fallback(game)
        apply_bosque_fallback(game, bosque_precios)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(games, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"OK: {len(games)} juegos escritos en {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
