"""Enriquecimiento externo con caché: completa datos de BGG (puntaje, reviews,
ranking, complejidad, etc.) para los juegos de data/data.json que tienen un
link exacto a BGG, y los guarda en data/cache/bgg/<id>.json.

Este script NO corre en el cron de GitHub Actions: BGG cerró el acceso sin
auth a su xmlapi2 (devuelve 401 hasta que aprueben la aplicación registrada)
y la página normal exige pasar un challenge de Cloudflare a mano. Por eso es
un paso manual, local, que alguien corre de vez en cuando (ver README).

Dos modos:
  - api  (default, para cuando BGG apruebe la aplicación): xmlapi2/thing, la
         vía oficial.
  - html (mientras tanto): reusa una sesión de navegador que vos pasaste a
         mano por el challenge de Cloudflare. Nunca intenta resolver el
         challenge ni evadir la detección de bots: si la sesión expiró,
         el script falla y avisa en vez de reintentar a ciegas.

build_data.py lee este caché y completa SOLO los campos que el Sheet dejó
vacíos (None) — el Sheet sigue siendo la fuente de verdad; esto es un
fallback, no un override.

Uso:
    # arma el caché para todos los juegos de data/data.json con link exacto a BGG
    python3 scripts/enrich_bgg.py --mode html --cookies cookies.json

    # o para ids puntuales
    python3 scripts/enrich_bgg.py --mode html --cookies cookies.json 174430 161936
"""
import argparse
import html
import json
import re
import sys
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

API_URL = "https://boardgamegeek.com/xmlapi2/thing"
GAME_URL = "https://boardgamegeek.com/boardgame/{id}"
CRAWL_DELAY_SECONDS = 5  # robots.txt de BGG: Crawl-delay: 5
USER_AGENT = "boardgame-personal-catalog/1.0 (uso personal; contacto: negocios.mondineta@gmail.com)"

ROOT = Path(__file__).resolve().parent.parent
DATA_PATH = ROOT / "data" / "data.json"
CACHE_DIR = ROOT / "data" / "cache" / "bgg"


def extract_id(value: str) -> str | None:
    match = re.search(r"/boardgame(?:expansion)?/(\d+)", value)
    if match:
        return match.group(1)
    if value.strip().isdigit():
        return value.strip()
    return None


def ids_from_catalog() -> list[str]:
    games = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    ids = []
    for game in games:
        gid = extract_id(game.get("bgg_url") or "")
        if gid and gid not in ids:
            ids.append(gid)
    return ids


def load_cookies(path: str) -> dict:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError('El archivo de cookies debe ser un JSON {"nombre": "valor", ...}')
    return data


def http_get(url: str, cookies: dict | None, retries: int = 3) -> str:
    headers = {"User-Agent": USER_AGENT}
    if cookies:
        headers["Cookie"] = "; ".join(f"{k}={v}" for k, v in cookies.items())
    req = urllib.request.Request(url, headers=headers)

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


def fetch_raw(game_id: str, mode: str, cookies: dict | None) -> str:
    if mode == "api":
        return http_get(f"{API_URL}?id={game_id}&stats=1", cookies=None)

    content = http_get(GAME_URL.format(id=game_id), cookies=cookies)
    if "Unauthorized" in content[:200] or "Just a moment" in content or "Verify you are human" in content:
        raise RuntimeError(
            f"BGG devolvió un challenge/bloqueo para el juego {game_id}. "
            "Tu sesión (cookies) probablemente expiró: volvé a pasar el "
            "challenge a mano en el navegador y actualizá --cookies."
        )
    return content


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


def parse_html_item(game_id: str, page_html: str) -> dict:
    match = re.search(r"GEEK\.geekitemPreload\s*=\s*(\{.*?\});", page_html, re.DOTALL)
    if not match:
        raise RuntimeError(
            f"No encontré el bloque GEEK.geekitemPreload para el juego {game_id}; "
            "puede que BGG haya cambiado el formato de la página."
        )
    item = json.loads(match.group(1))["item"]
    stats = item.get("stats", {})
    links = item.get("links", {})
    designers = ", ".join(l["name"] for l in links.get("boardgamedesigner", [])) or None

    rankinfo = item.get("rankinfo") or []
    overall_rank = next((r.get("rank") for r in rankinfo if r.get("rankobjecttype") == "subtype"), None)

    best = ((item.get("polls") or {}).get("userplayers") or {}).get("best") or []

    return {
        "id": str(item.get("id")),
        "disenador": designers,
        "edad_min": item.get("minage"),
        "jug_min": item.get("minplayers"),
        "jug_max": item.get("maxplayers"),
        "jug_best_min": best[0]["min"] if best else None,
        "jug_best_max": best[0]["max"] if best else None,
        "duracion": item.get("maxplaytime"),
        "complejidad": stats.get("avgweight"),
        "puntaje_bgg": stats.get("average"),
        "reviews_bgg": stats.get("usersrated"),
        "ranking_bgg": overall_rank,
    }


def enrich(ids: list[str], mode: str, cookies: dict | None, force: bool):
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    for i, game_id in enumerate(ids):
        cache_file = CACHE_DIR / f"{game_id}.json"
        if cache_file.exists() and not force:
            print(f"[{i + 1}/{len(ids)}] {game_id}: ya en caché, salteo")
            continue

        print(f"[{i + 1}/{len(ids)}] {game_id} ({mode})...")
        raw = fetch_raw(game_id, mode, cookies)

        if mode == "api":
            root = ET.fromstring(raw)
            item_el = root.find("item")
            if item_el is None:
                print(f"  sin resultado para {game_id}", file=sys.stderr)
                continue
            data = parse_api_item(item_el)
        else:
            data = parse_html_item(game_id, raw)

        cache_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  puntaje={data['puntaje_bgg']} rank={data['ranking_bgg']} complejidad={data['complejidad']}")

        if i < len(ids) - 1:
            time.sleep(CRAWL_DELAY_SECONDS)


def main():
    parser = argparse.ArgumentParser(description="Enriquecimiento de data.json con datos de BGG (caché por id)")
    parser.add_argument("ids", nargs="*", help="ids de BGG puntuales; si no se pasan, se usan todos los del catálogo")
    parser.add_argument("--mode", choices=["api", "html"], default="api",
                         help="api = xmlapi2 oficial (requiere app aprobada); "
                              "html = reusa tu sesión ya autenticada contra el challenge de Cloudflare")
    parser.add_argument("--cookies", help="JSON con las cookies de tu sesión (solo --mode html)")
    parser.add_argument("--force", action="store_true", help="re-descargar aunque ya esté en caché")
    args = parser.parse_args()

    if args.mode == "html" and not args.cookies:
        parser.error("--mode html requiere --cookies (exportá las cookies de tu sesión ya logueada)")

    ids = args.ids or ids_from_catalog()
    if not ids:
        parser.error("No hay ids para procesar: pasá ids a mano o asegurate de que data/data.json tenga bgg_url con link exacto")

    cookies = load_cookies(args.cookies) if args.cookies else None
    enrich(ids, mode=args.mode, cookies=cookies, force=args.force)
    print(f"\nCaché en {CACHE_DIR} ({len(list(CACHE_DIR.glob('*.json')))} juego(s) en total)")
    print("Corré scripts/build_data.py para que data.json tome los campos que faltaban.")


if __name__ == "__main__":
    main()
