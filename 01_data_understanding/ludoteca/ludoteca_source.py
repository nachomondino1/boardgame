"""Lee mi_ludoteca.json: los juegos que tenés o tuviste, editado directo acá
en vez de en un Google Sheet.

Por qué no un Sheet: el Sheet original justificaba su complejidad (fetch
CSV + .xlsx para hyperlinks, parseo de columnas, etc.) cuando tenía las ~70
columnas de BGG/Bosque Lúdico cargadas a mano fila por fila. Una vez que esas
fuentes se automatizaron (ver bgg/ y bosque_ludico/) y el Sheet quedó
reducido a ~10 columnas de ~30 filas que cambian pocas veces al año, pegarle
a la API de Google para esto dejó de tener sentido: un JSON versionado en el
repo, que editás directo (a mano o pidiéndoselo a Claude), es más simple y
no depende de que el Sheet siga siendo público.

Esquema de cada entrada de mi_ludoteca.json (solo nombre_en y estado son
obligatorios):
    nombre_en   nombre en inglés — el que usa BGG para buscar/matchear
    nombre_es   nombre/edición local, si difiere del de la caja en inglés
    modo
    estado      "Own" o "Prev. owned"
    bgg_id      id numérico de BGG, como string, si lo tenés (identificador
                compartido con bgg/bgg_top1000.csv — ver game_universe.py).
                Si no lo tenés pero sí bgg_url con un link exacto, se extrae
                de ahí solo. Sin ninguno de los dos, el juego linkea a una
                búsqueda y queda sin bgg_id (no hay forma de saberlo sin un
                link exacto).
    bgg_url     link exacto a BGG, si lo tenés; si no está, se resuelve una
                búsqueda por nombre (mismo criterio que usa el top N — ver
                resolve_bgg_url)
    pros, cons, mi_puntaje, youtube, notas

Uso como módulo:
    from ludoteca_source import load_games
    games = load_games()  # todos, estado Own o Prev. owned

Uso como script: imprime un resumen por Estado.
"""
import json
import re
import sys
import urllib.parse
from collections import Counter
from pathlib import Path

DATA_PATH = Path(__file__).resolve().parent / "mi_ludoteca.json"

# Mismo patrón que antes en el Sheet: para ediciones locales o nombres que
# no matchean bien contra BGG, se fuerza el término de búsqueda o se marca
# el juego como sin ficha razonable en BGG.
BGG_SEARCH_OVERRIDES = {
    "Fantasma Blitz": "Ghost Blitz",
    "Misterio (Ruibal)": "Misterio",
    "Alcatraz: la fuga imposible": "Alcatraz",
    "Memotest (Ruibal)": "Memory",
    "Batalla Naval": "Battleship",
    "Ludo (Mickey and Kids)": "Pachisi",
}
BGG_SKIP = {
    "Ajedrez y damas",
    "Ajedrez / Backgammon (caja rosa)",
    "Puzzles Trefl 1000 piezas",
    "Mente Matic (Habano)",
}

# Mismos nombres de campo y tipos que usaba el Sheet, para que
# integrate_data.py no tenga que distinguir de dónde vino cada juego.
NUMERIC_FIELDS_FLOAT = {"complejidad", "puntaje_bgg", "puntaje_ajust_bgg", "precio_calidad"}
NUMERIC_FIELDS_INT = {"anio", "jug_min", "jug_max", "jug_best_min", "jug_best_max", "duracion", "duracion_min",
                       "duracion_max", "edad_min", "reviews_bgg", "ranking_bgg", "mi_puntaje", "costo"}
TEXT_FIELDS = {"nombre", "nombre_en", "nombre_es", "modo", "descripcion", "disenador", "pros", "cons", "estado",
               "link_tienda", "youtube", "notas"}


def resolve_bgg_url(nombre, exact_url):
    if nombre in BGG_SKIP:
        return None
    if exact_url:
        return exact_url
    term = BGG_SEARCH_OVERRIDES.get(nombre)
    if term is None:
        term = re.sub(r"\s*\([^)]*\)\s*$", "", nombre).strip()
    return "https://boardgamegeek.com/geeksearch.php?action=search&objecttype=boardgame&q=" + urllib.parse.quote(term)


def extract_bgg_id(url):
    """El id de BGG de un link exacto (/boardgame/<id>/... o
    /boardgameexpansion/<id>/...), o None si url es un link de búsqueda (o
    vacío). Identificador único usado en todo el pipeline — ver
    game_universe.py — para no andar matcheando por nombre entre fuentes."""
    match = re.search(r"/boardgame(?:expansion)?/(\d+)", url or "")
    return match.group(1) if match else None


def load_games():
    try:
        entries = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError:
        sys.exit(f"No existe {DATA_PATH}")

    games = []
    for entry in entries:
        nombre_en = (entry.get("nombre_en") or "").strip()
        if not nombre_en:
            continue
        game = {
            "nombre_en": nombre_en,
            "nombre_es": entry.get("nombre_es") or "",
            "modo": entry.get("modo") or "",
            "estado": entry.get("estado") or "",
            "pros": entry.get("pros") or "",
            "cons": entry.get("cons") or "",
            "mi_puntaje": entry.get("mi_puntaje"),
            "youtube": entry.get("youtube") or "",
            "notas": entry.get("notas") or "",
        }
        game["nombre"] = game["nombre_es"] or game["nombre_en"]
        game["bgg_url"] = resolve_bgg_url(nombre_en, entry.get("bgg_url"))
        bgg_id = entry.get("bgg_id")
        game["bgg_id"] = str(bgg_id) if bgg_id else extract_bgg_id(game["bgg_url"])
        games.append(game)

    if not games:
        sys.exit(f"{DATA_PATH} no tiene juegos")
    return games


def main():
    games = load_games()
    counts = Counter(g["estado"] or "(vacío)" for g in games)
    print(f"{len(games)} juegos leídos de {DATA_PATH}:")
    for estado, n in counts.most_common():
        print(f"  {estado}: {n}")


if __name__ == "__main__":
    main()
