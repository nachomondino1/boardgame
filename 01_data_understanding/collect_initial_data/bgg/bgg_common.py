"""Código compartido por los scripts de BGG (initialize_bgg_data.py,
refresh_bgg_data.py, search_new_game.py): paths, requests a la API oficial y
al dataset de Hugging Face, y lectura/escritura de
data/01_data_understanding/bgg_data.jsonl (el universo de juegos: todo juego
con fila acá existe para el repo) y bgg_collection.jsonl.

Regla de esta carpeta: los datos se guardan CRUDOS, con los mismos nombres
de campo que la fuente (BGG) y sin calcular nada. Toda columna derivada
(jugadores best/recomendados, precio de referencia, modo, etc.) se
construye en 02_data_preparation/construct_data.py.

Forma de cada valor en bgg_data.jsonl: la del dataset de Hugging Face (que a
su vez es la respuesta de la API de BGG convertida a dict) — strings para los
escalares, listas para los `link` y para los polls (con las claves '@...'
del XML). La API oficial y el dataset llenan exactamente la misma forma, así
que 02_data_preparation lee un solo formato.

Regla central de bgg_data.jsonl: NINGUNA función de acá reescribe el
archivo entero salvo write_bgg_cache_full (solo para el bootstrap, donde
no hay nada previo que perder). Para todo lo demás se usa upsert_bgg_cache,
que lee lo que ya está en disco y solo toca las filas/campos indicados.
"""
import ast
import csv
import io
import json
import os
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path

csv.field_size_limit(10_000_000)  # el dataset de origen (Hugging Face) trae descripciones largas en una sola celda CSV

ROOT = Path(__file__).resolve().parent.parent.parent.parent
BGG_DATA_PATH = ROOT / "data" / "01_data_understanding" / "bgg_data.jsonl"
COLLECTION_PATH = ROOT / "data" / "01_data_understanding" / "bgg_collection.jsonl"

DATASET_URL = (
    "https://huggingface.co/datasets/mmpa/board_game_analysis/"
    "resolve/main/games_detailed_info2025.csv"
)
API_URL = "https://boardgamegeek.com/xmlapi2/thing"
COLLECTION_URL = "https://boardgamegeek.com/xmlapi2/collection"
BATCH_SIZE = 20  # ids por request a la API
CRAWL_DELAY_SECONDS = 5  # robots.txt de BGG: Crawl-delay: 5
USER_AGENT = "boardgame-personal-catalog/1.0 (uso personal; contacto: negocios.mondineta@gmail.com)"

# data/01_data_understanding/bgg_collection.jsonl: TU colección en BGG,
# cruda (atributos de <status> y <rating> de xmlapi2/collection, mismos
# nombres). `rating` es tu puntaje ("N/A" si no puntuaste).
COLLECTION_FIELDS = [
    "bgg_id", "name", "own", "prevowned", "fortrade", "want", "wanttoplay", "wanttobuy",
    "wishlist", "preordered", "lastmodified", "rating", "numplays", "comment",
]

# data/01_data_understanding/bgg_data.jsonl: 100% de BGG, crudo. Los nombres
# son los del dataset de Hugging Face / la API ("Board Game Rank" incluido).
# Orden: primero los campos cortos, al final los largos o de longitud muy
# variable, para ubicar una columna a ojo al abrir el .jsonl.
BGG_CACHE_FIELDS = [
    "bgg_id", "yearpublished", "minage", "minplayers", "maxplayers",
    "playingtime", "minplaytime", "maxplaytime",
    "usersrated", "average", "bayesaverage", "Board Game Rank", "averageweight", "owned", "wishing",
    "boardgamedesigner", "boardgamepublisher", "boardgamemechanic", "boardgamecategory", "boardgamefamily",
    "name", "alternate", "thumbnail",
    "suggested_num_players", "poll_summary", "suggested_playerage", "suggested_language_dependence",
    "marketplacelistings", "description",
]
# Campos cuyo valor es una lista (vacía si BGG no devuelve nada); el resto son strings.
LIST_FIELDS = {
    "boardgamedesigner", "boardgamepublisher", "boardgamemechanic", "boardgamecategory", "boardgamefamily",
    "alternate", "suggested_num_players", "poll_summary", "suggested_playerage",
    "suggested_language_dependence", "marketplacelistings",
}
# poll_summary (el "Best with 3–4 players" ya calculado por BGG) y
# marketplacelistings solo los llena la API (el dataset no los trae);
# marketplacelistings además solo cuando se pide, porque agrega mucho peso al pedido. Los listados más
# viejos que esto suelen estar vendidos, así que no se guardan.
MARKETPLACE_MAX_AGE_DAYS = 730


def normalize(s):
    s = (s or "").strip().lower()
    s = unicodedata.normalize("NFD", s)
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


def extract_bgg_id(url):
    match = re.search(r"/boardgame(?:expansion)?/(\d+)", url or "")
    return match.group(1) if match else None


# ---------------------------------------------------------------------------
# Requests
# ---------------------------------------------------------------------------

def load_env(name):
    """`name` del entorno, o de .env en la raíz del repo (gitignored)."""
    value = os.environ.get(name)
    env_path = ROOT / ".env"
    if not value and env_path.exists():
        for line in env_path.read_text().splitlines():
            key, _, raw = line.partition("=")
            if key.strip() == name:
                value = raw.strip().strip("\"'")
    if not value:
        raise RuntimeError(f"Falta {name} (variable de entorno o .env en la raíz del repo)")
    return value


def load_bgg_token():
    return load_env("BGG_TOKEN")


def http_get(url, authorized=False, retries=3):
    """GET con reintento ante 429/503. `authorized=True` manda el token de
    BGG: usarlo SOLO con boardgamegeek.com, nunca con otro host."""
    headers = {"User-Agent": USER_AGENT}
    if authorized:
        headers["Authorization"] = f"Bearer {load_bgg_token()}"
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


# ---------------------------------------------------------------------------
# Dataset de Hugging Face
# ---------------------------------------------------------------------------

def fetch_dataset():
    print(f"Descargando dataset de BGG ({DATASET_URL})...")
    raw = http_get(DATASET_URL)
    rows = {row["id"]: row for row in csv.DictReader(io.StringIO(raw)) if row.get("id")}
    print(f"{len(rows)} juegos en el dataset.\n")
    return rows


def _literal(value, default):
    """Varias columnas del dataset vienen como el repr de Python de una
    lista/dict (ej. "['Mathias Wigge']"), no JSON. ast.literal_eval es
    seguro acá (nunca ejecuta código, solo literales)."""
    value = (value or "").strip()
    if not value:
        return default
    try:
        return ast.literal_eval(value)
    except (ValueError, SyntaxError):
        return default


def _as_list(value):
    """Cuando un poll tiene un único elemento, el dataset trae un dict
    pelado en vez de una lista de un elemento — normalizar a lista."""
    if isinstance(value, dict):
        return [value]
    return value if isinstance(value, list) else []


def dataset_row_to_raw(row):
    """Fila del CSV de Hugging Face -> fila cruda de bgg_data.jsonl."""
    out = {}
    for field in BGG_CACHE_FIELDS:
        if field == "bgg_id":
            out[field] = row.get("id", "")
        elif field in ("marketplacelistings", "poll_summary"):
            out[field] = []  # solo la API lo trae
        elif field in LIST_FIELDS:
            out[field] = _as_list(_literal(row.get(field), []))
        else:
            out[field] = (row.get(field) or "").strip()
    return out


# ---------------------------------------------------------------------------
# API oficial (xmlapi2/thing): XML -> misma forma cruda que el dataset
# ---------------------------------------------------------------------------

def _poll_results(item, poll_name):
    poll = item.find(f"poll[@name='{poll_name}']")
    return poll.findall("results") if poll is not None else []


def _marketplace_listings(item):
    cutoff = datetime.now(timezone.utc) - timedelta(days=MARKETPLACE_MAX_AGE_DAYS)
    listings = []
    for listing in item.findall("marketplacelistings/listing"):
        price, cond, date = listing.find("price"), listing.find("condition"), listing.find("listdate")
        if price is None or cond is None or date is None:
            continue
        try:
            listed_at = datetime.strptime(date.get("value"), "%a, %d %b %Y %H:%M:%S %z")
        except ValueError:
            continue
        if listed_at >= cutoff:
            listings.append({
                "listdate": date.get("value"), "price": price.get("value"),
                "currency": price.get("currency"), "condition": cond.get("value"),
            })
    return listings


def parse_item(item, marketplace=False):
    """<item> de xmlapi2/thing -> fila cruda de bgg_data.jsonl (sin bgg_id)."""
    ratings = item.find("statistics/ratings")

    def stat(tag):
        el = ratings.find(tag) if ratings is not None else None
        return el.get("value") if el is not None else ""

    def attr(path):
        el = item.find(path)
        return el.get("value") if el is not None else ""

    def links(link_type):
        return [l.get("value") for l in item.findall(f"link[@type='{link_type}']")]

    def text(tag):
        el = item.find(tag)
        return (el.text or "").strip() if el is not None and el.text else ""

    rank_el = ratings.find("ranks/rank[@name='boardgame']") if ratings is not None else None
    primary = next((n.get("value") for n in item.findall("name") if n.get("type") == "primary"), "")

    return {
        "yearpublished": attr("yearpublished"), "minage": attr("minage"),
        "minplayers": attr("minplayers"), "maxplayers": attr("maxplayers"),
        "playingtime": attr("playingtime"), "minplaytime": attr("minplaytime"), "maxplaytime": attr("maxplaytime"),
        "usersrated": stat("usersrated"), "average": stat("average"), "bayesaverage": stat("bayesaverage"),
        "Board Game Rank": rank_el.get("value") if rank_el is not None else "",
        "averageweight": stat("averageweight"), "owned": stat("owned"), "wishing": stat("wishing"),
        "boardgamedesigner": links("boardgamedesigner"), "boardgamepublisher": links("boardgamepublisher"),
        "boardgamemechanic": links("boardgamemechanic"), "boardgamecategory": links("boardgamecategory"),
        "boardgamefamily": links("boardgamefamily"),
        "name": primary,
        "alternate": [n.get("value") for n in item.findall("name") if n.get("type") == "alternate"],
        "thumbnail": text("thumbnail"),
        "suggested_num_players": [
            {"@numplayers": r.get("numplayers"),
             "result": [{"@value": x.get("value"), "@numvotes": x.get("numvotes")} for x in r.findall("result")]}
            for r in _poll_results(item, "suggested_numplayers")
        ],
        "poll_summary": [{"@name": r.get("name"), "@value": r.get("value")} for r in item.findall("poll-summary/result")],
        "suggested_playerage": [
            {"@value": x.get("value"), "@numvotes": x.get("numvotes")}
            for r in _poll_results(item, "suggested_playerage") for x in r.findall("result")
        ],
        "suggested_language_dependence": [
            {"@level": x.get("level"), "@value": x.get("value"), "@numvotes": x.get("numvotes")}
            for r in _poll_results(item, "language_dependence") for x in r.findall("result")
        ],
        "marketplacelistings": _marketplace_listings(item) if marketplace else [],
        "description": text("description"),
    }


def fetch_things(bgg_ids, marketplace=False, progress=None):
    """Pide `bgg_ids` en lotes de BATCH_SIZE (respetando el Crawl-delay
    entre lotes) y devuelve {bgg_id: fila cruda}. Un id que BGG no
    devuelve queda fuera."""
    ids = list(dict.fromkeys(bgg_ids))
    out = {}
    for start in range(0, len(ids), BATCH_SIZE):
        if start:
            time.sleep(CRAWL_DELAY_SECONDS)
        url = f"{API_URL}?id={','.join(ids[start:start + BATCH_SIZE])}&stats=1" + ("&marketplace=1" if marketplace else "")
        for item in ET.fromstring(http_get(url, authorized=True)).findall("item"):
            out[item.get("id")] = parse_item(item, marketplace)
        if progress:
            progress(min(start + BATCH_SIZE, len(ids)), len(ids))
    return out


def fetch_attributes(bgg_id, mode, dataset):
    """mode == "api": xmlapi2/thing. mode == "dummy": dataset de Hugging
    Face ya descargado (sin red extra)."""
    if mode == "api":
        return fetch_things([bgg_id], marketplace=True).get(str(bgg_id))
    row = dataset.get(bgg_id)
    return dataset_row_to_raw(row) if row else None


# ---------------------------------------------------------------------------
# Tu colección (xmlapi2/collection) -> bgg_collection.jsonl, cruda
# ---------------------------------------------------------------------------

def fetch_collection(username, retries=6):
    """Colección de `username` (solo juegos, sin expansiones). BGG responde
    202 mientras arma la lista: se reintenta hasta que da 200."""
    query = urllib.parse.urlencode({
        "username": username, "stats": 1, "subtype": "boardgame", "excludesubtype": "boardgameexpansion",
    })
    for _ in range(retries):
        req = urllib.request.Request(
            f"{COLLECTION_URL}?{query}",
            headers={"User-Agent": USER_AGENT, "Authorization": f"Bearer {load_bgg_token()}"},
        )
        with urllib.request.urlopen(req) as resp:
            if resp.status == 200:
                body = resp.read().decode("utf-8", errors="replace")
                break
        time.sleep(CRAWL_DELAY_SECONDS)
    else:
        raise RuntimeError("BGG no devolvió la colección (siguió en 202); reintentar en un rato")

    rows = []
    for item in ET.fromstring(body).findall("item"):
        status = item.find("status")
        rating = item.find("stats/rating")
        comment = item.find("comment")
        row = {k: (status.get(k) if status is not None else "") for k in COLLECTION_FIELDS}
        row.update({
            "bgg_id": item.get("objectid"),
            "name": (item.find("name").text or "") if item.find("name") is not None else "",
            "rating": rating.get("value") if rating is not None else "",
            "numplays": (item.find("numplays").text or "") if item.find("numplays") is not None else "",
            "comment": (comment.text or "") if comment is not None else "",
        })
        rows.append(row)
    return rows


def load_collection():
    if not COLLECTION_PATH.exists():
        return []
    with COLLECTION_PATH.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def write_collection(rows):
    """Foto completa de tu colección en BGG: se reescribe entera (no hay
    nada tuyo acá que pisar, todo viene de BGG)."""
    with COLLECTION_PATH.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps({k: row.get(k, "") for k in COLLECTION_FIELDS}, ensure_ascii=False))
            f.write("\n")


# ---------------------------------------------------------------------------
# bgg_data.jsonl: leer / escribir (un objeto JSON
# por línea)
# ---------------------------------------------------------------------------

def load_bgg_cache():
    """Lee bgg_data.jsonl tal cual está en disco. Lista vacía si el
    archivo todavía no existe."""
    if not BGG_DATA_PATH.exists():
        return []
    with BGG_DATA_PATH.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def _ordered_row(row):
    return {k: (row.get(k) if row.get(k) not in (None, "") else ([] if k in LIST_FIELDS else "")) for k in BGG_CACHE_FIELDS}


def write_bgg_cache_full(rows):
    """Reescribe el archivo entero. Usar SOLO en el bootstrap (no hay
    nada previo que perder) — cualquier otro caso de uso debe pasar por
    upsert_bgg_cache."""
    with BGG_DATA_PATH.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(_ordered_row(row), ensure_ascii=False))
            f.write("\n")


def upsert_bgg_cache(updates_by_id):
    """Mergea `updates_by_id` ({bgg_id: {campo: valor, ...}}) sobre lo
    que ya está en bgg_data.jsonl: una fila existente se actualiza solo en
    los campos indicados; un bgg_id nuevo se agrega al final; el resto
    queda igual. Devuelve (agregadas, actualizadas)."""
    existing = load_bgg_cache()
    by_id = {row.get("bgg_id"): row for row in existing if row.get("bgg_id")}

    added, updated = 0, 0
    for bgg_id, attrs in updates_by_id.items():
        if bgg_id in by_id:
            by_id[bgg_id].update(attrs)
            updated += 1
        else:
            new_row = {"bgg_id": bgg_id, **attrs}
            by_id[bgg_id] = new_row
            existing.append(new_row)
            added += 1

    with BGG_DATA_PATH.open("w", encoding="utf-8") as f:
        for row in existing:
            f.write(json.dumps(_ordered_row(row), ensure_ascii=False))
            f.write("\n")
    return added, updated


# ---------------------------------------------------------------------------
# Buscar un juego puntual en el dataset (por id o por nombre)
# ---------------------------------------------------------------------------

def find_in_dataset(term, dataset):
    import difflib

    if term.strip().isdigit():
        row = dataset.get(term.strip())
        if not row:
            sys.exit(f"No encontré el id de BGG {term} en el dataset.")
        return row

    norm_term = normalize(term)
    exact = [r for r in dataset.values() if normalize(r.get("name", "")) == norm_term]
    if len(exact) == 1:
        return exact[0]
    if len(exact) > 1:
        print(f"Varios juegos se llaman \"{term}\" exacto, uso el de mejor ranking:", file=sys.stderr)
        exact.sort(key=lambda r: float(r.get("Board Game Rank") or 10**9))
        return exact[0]

    names = [r.get("name", "") for r in dataset.values()]
    matches = difflib.get_close_matches(term, names, n=5, cutoff=0.6)
    if not matches:
        sys.exit(f"No encontré ningún juego parecido a \"{term}\" en el dataset. Probá con el id de BGG directo.")
    if len(matches) > 1:
        sys.exit("Más de un juego parecido, sé más específico o usá el id de BGG:\n  " + "\n  ".join(matches))
    best_name = matches[0]
    return next(r for r in dataset.values() if r.get("name") == best_name)
