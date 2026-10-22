"""Integra las fuentes ya recolectadas en 01_data_understanding/ en un único
docs/data/data.json: el universo de juegos (game_universe.load_universe():
mi_ludoteca.json, fuente de verdad para lo que tenés/tuviste, + el top N de
BGG como candidatos Watchlist) + el caché de BGG + el dataset de precios de
Bosque Lúdico, estos dos últimos solo completando lo que quedó vacío — nunca
pisan un valor cargado a mano en mi_ludoteca.json.

Solo integra: la recolección cruda de cada fuente vive en 01_data_understanding/
(ludoteca/, bgg/, bosque_ludico/, game_universe.py), este script no le pega a
ningún sitio externo.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "01_data_understanding"))
sys.path.insert(0, str(ROOT / "01_data_understanding" / "ludoteca"))

from game_universe import load_universe  # noqa: E402
from ludoteca_source import NUMERIC_FIELDS_FLOAT, NUMERIC_FIELDS_INT  # noqa: E402

OUTPUT_PATH = ROOT / "docs" / "data" / "data.json"
BGG_CACHE_DIR = ROOT / "docs" / "data" / "cache" / "bgg"
BOSQUE_DATA_PATH = ROOT / "01_data_understanding" / "bosque_ludico" / "bosque_data.json"

# Campos que, si el universo los dejó vacíos, se completan con el caché de
# BGG (ver 01_data_understanding/bgg/enrich_bgg.py) cuando el juego tiene un
# link exacto a BGG. mi_ludoteca.json manda siempre sobre tus propios
# juegos: esto nunca pisa un valor ya cargado a mano.
BGG_FALLBACK_FIELDS = (
    "descripcion", "disenador", "edad_min", "jug_min", "jug_max", "jug_best_min", "jug_best_max",
    "duracion", "duracion_min", "duracion_max", "complejidad", "puntaje_bgg", "reviews_bgg", "ranking_bgg",
    "mecanicas", "categorias",
)


def apply_bgg_fallback(game):
    """Los valores del caché de BGG (enrich_bgg.py) ya son numéricos en
    formato estándar (punto decimal) — se parsean con float()/int() directo."""
    if not game.get("bgg_id"):
        return
    cache_path = BGG_CACHE_DIR / f"{game['bgg_id']}.json"
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
            game[field] = float(value)
        elif field in NUMERIC_FIELDS_INT:
            game[field] = int(float(value))
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
    cuando quedaron vacíos. mi_ludoteca.json manda siempre sobre tus propios
    juegos si vos ya cargaste algo ahí."""
    precio = precios_by_nombre.get(game.get("nombre"))
    if not precio:
        return
    if game.get("costo") is None and precio.get("precio") is not None:
        game["costo"] = int(precio["precio"])
    if not game.get("link_tienda") and precio.get("bosque_url"):
        game["link_tienda"] = precio["bosque_url"]


def main():
    games = load_universe()
    bosque_precios = load_bosque_precios()
    for game in games:
        apply_bgg_fallback(game)
        apply_bosque_fallback(game, bosque_precios)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(games, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"OK: {len(games)} juegos escritos en {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
