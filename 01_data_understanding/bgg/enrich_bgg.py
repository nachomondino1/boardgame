"""Enriquecimiento externo con caché: completa datos de BGG (diseñador, edad
mín., jugadores, duración, complejidad, puntaje, reviews, ranking) para los
juegos del universo (game_universe.load_universe(): Sheet + top N de BGG)
que tienen un link exacto a BGG, y los guarda en docs/data/cache/bgg/<id>.json.

Dos modos:
  - dummy (default, hoy): BGG cerró el acceso sin auth a xmlapi2 (401 hasta
         que aprueben la aplicación registrada) y la página normal exige
         pasar un challenge de Cloudflare — scrapearla está descartado (ver
         DATA_PLAYBOOK.md). En cambio se usa, como placeholder temporal, un
         dataset público de terceros con un snapshot de BGG (GitHub, sin
         auth): board_games.csv de sansinghsanjay/predicting_board_games_reviews.
         **Es de 2016**: un juego con id de BGG que no exista todavía en ese
         snapshot (cualquier lanzamiento de ~2017 en adelante, que es buena
         parte del top del ranking actual) simplemente no tiene entrada acá
         — sin error, sin dato inventado. Corregible a mano por juego si
         hace falta antes de que BGG apruebe la app.
  - api  (para cuando BGG apruebe la aplicación): xmlapi2/thing, la vía
         oficial — reemplaza el placeholder dummy sin tocar nada más del
         pipeline en cuanto esté disponible.

02_data_preparation/integrate_data.py lee este caché y completa SOLO los
campos que el universo dejó vacíos (None) — el Sheet y el top N de BGG
siguen siendo la fuente de verdad; esto es un fallback, no un override.

Uso:
    python3 01_data_understanding/bgg/enrich_bgg.py                 # modo dummy, todo el universo
    python3 01_data_understanding/bgg/enrich_bgg.py --mode api      # cuando BGG apruebe la app
    python3 01_data_understanding/bgg/enrich_bgg.py 174430 161936   # ids puntuales
"""
import argparse
import csv
import io
import json
import sys
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from game_universe import load_universe  # noqa: E402

API_URL = "https://boardgamegeek.com/xmlapi2/thing"
CRAWL_DELAY_SECONDS = 5  # robots.txt de BGG: Crawl-delay: 5
USER_AGENT = "boardgame-personal-catalog/1.0 (uso personal; contacto: negocios.mondineta@gmail.com)"

# Dataset público de terceros, snapshot de BGG ~2016, usado como placeholder
# hasta que la API oficial esté disponible. Ver docstring del módulo.
DUMMY_DATASET_URL = (
    "https://raw.githubusercontent.com/sansinghsanjay/"
    "predicting_board_games_reviews/master/board_games.csv"
)

ROOT = Path(__file__).resolve().parent.parent.parent
CACHE_DIR = ROOT / "docs" / "data" / "cache" / "bgg"


def ids_from_universe() -> list[str]:
    games = load_universe()
    ids = []
    for game in games:
        gid = game.get("bgg_id")
        if gid and gid not in ids:
            ids.append(gid)
    return ids


def http_get(url: str, retries: int = 3) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    delay = CRAWL_DELAY_SECONDS
    for attempt in range(1, retries + 1):
        try:
            with urllib.request.urlopen(req) as resp:
                return resp.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as e:
            if e.code in (429, 503) and attempt < retries:
                print(f"  HTTP {e.code}, reintento {attempt}/{retries} en {delay}s...", file=sys.stderr)
                time.sleep(delay)
                delay *= 2
                continue
            raise
    raise RuntimeError("No se pudo completar la request")


def parse_api_item(item: ET.Element) -> dict:
    def text(tag, attr="value"):
        el = item.find(tag)
        return el.get(attr) if el is not None else None

    stats = item.find("statistics/ratings")
    rating = stats.find("average").get("value") if stats is not None and stats.find("average") is not None else None
    usersrated = stats.find("usersrated").get("value") if stats is not None and stats.find("usersrated") is not None else None
    rank_el = stats.find("ranks/rank[@name='boardgame']") if stats is not None else None
    rank = rank_el.get("value") if rank_el is not None else None
    weight = stats.find("averageweight").get("value") if stats is not None and stats.find("averageweight") is not None else None

    links = [l.get("value") for l in item.findall("link[@type='boardgamedesigner']")]

    best_min = best_max = None
    poll = item.find("poll[@name='suggested_numplayers']")
    if poll is not None:
        best_result, best_votes = None, -1
        for results in poll.findall("results"):
            best_el = results.find("result[@value='Best']")
            if best_el is not None:
                votes = int(best_el.get("numvotes", 0))
                if votes > best_votes:
                    best_votes, best_result = votes, results.get("numplayers")
        if best_result:
            parts = best_result.replace("+", "").split("-")
            best_min, best_max = parts[0], parts[-1]

    return {
        "id": item.get("id"),
        "disenador": ", ".join(links) or None,
        "edad_min": text("minage"),
        "jug_min": text("minplayers"),
        "jug_max": text("maxplayers"),
        "jug_best_min": best_min,
        "jug_best_max": best_max,
        "duracion": text("maxplaytime"),
        "complejidad": weight,
        "puntaje_bgg": rating,
        "reviews_bgg": usersrated,
        "ranking_bgg": rank,
    }


def enrich_api(ids: list[str], force: bool):
    for i, game_id in enumerate(ids):
        cache_file = CACHE_DIR / f"{game_id}.json"
        if cache_file.exists() and not force:
            print(f"[{i + 1}/{len(ids)}] {game_id}: ya en caché, salteo")
            continue

        print(f"[{i + 1}/{len(ids)}] {game_id} (api)...")
        raw = http_get(f"{API_URL}?id={game_id}&stats=1")
        root = ET.fromstring(raw)
        item_el = root.find("item")
        if item_el is None:
            print(f"  sin resultado para {game_id}", file=sys.stderr)
            continue

        data = parse_api_item(item_el)
        cache_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  puntaje={data['puntaje_bgg']} rank={data['ranking_bgg']} complejidad={data['complejidad']}")

        if i < len(ids) - 1:
            time.sleep(CRAWL_DELAY_SECONDS)


def fetch_dummy_dataset() -> dict[str, dict]:
    print(f"Descargando dataset placeholder ({DUMMY_DATASET_URL})...")
    raw = http_get(DUMMY_DATASET_URL)
    rows = csv.DictReader(io.StringIO(raw))
    return {row["id"]: row for row in rows if row.get("id")}


def parse_dummy_row(row: dict) -> dict:
    def num(key):
        value = (row.get(key) or "").strip()
        return value if value else None

    return {
        "id": row["id"],
        "disenador": None,  # no viene en este dataset
        "edad_min": num("minage"),
        "jug_min": num("minplayers"),
        "jug_max": num("maxplayers"),
        "jug_best_min": None,  # no viene en este dataset (hace falta el poll de BGG, solo vía api)
        "jug_best_max": None,
        "duracion": num("maxplaytime"),
        "complejidad": num("average_weight"),
        "puntaje_bgg": num("average_rating"),
        "reviews_bgg": num("users_rated"),
        "ranking_bgg": None,  # ya sale de bgg/bgg_top1000.csv para los candidatos
    }


def enrich_dummy(ids: list[str], force: bool):
    dataset = fetch_dummy_dataset()
    print(f"{len(dataset)} juegos en el dataset placeholder.\n")

    found = skipped = missing = 0
    for i, game_id in enumerate(ids):
        cache_file = CACHE_DIR / f"{game_id}.json"
        if cache_file.exists() and not force:
            skipped += 1
            continue

        row = dataset.get(game_id)
        if row is None:
            missing += 1
            continue

        data = parse_dummy_row(row)
        cache_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        found += 1

    print(f"[{len(ids)} id(s) procesados] {found} completados, {skipped} ya en caché, "
          f"{missing} sin match en el dataset placeholder (probablemente juegos nuevos; "
          "van a quedar sin estos datos hasta --mode api)")


def main():
    parser = argparse.ArgumentParser(description="Enriquecimiento del universo de juegos con datos de BGG (caché por id)")
    parser.add_argument("ids", nargs="*", help="ids de BGG puntuales; si no se pasan, se usan todos los del universo")
    parser.add_argument("--mode", choices=["dummy", "api"], default="dummy",
                         help="dummy = dataset placeholder de terceros (default, hoy); "
                              "api = xmlapi2 oficial (requiere app aprobada)")
    parser.add_argument("--force", action="store_true", help="re-generar aunque ya esté en caché")
    args = parser.parse_args()

    ids = args.ids or ids_from_universe()
    if not ids:
        parser.error("No hay ids para procesar: pasá ids a mano o asegurate de que el universo tenga juegos con bgg_url exacto")

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    if args.mode == "api":
        enrich_api(ids, force=args.force)
    else:
        enrich_dummy(ids, force=args.force)

    print(f"\nCaché en {CACHE_DIR} ({len(list(CACHE_DIR.glob('*.json')))} juego(s) en total)")
    print("Corré 02_data_preparation/integrate_data.py para que data.json tome los campos que faltaban.")


if __name__ == "__main__":
    main()
