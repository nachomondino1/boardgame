"""Código compartido por los scripts de BGG (initialize_bgg_data.py,
search_new_game.py, modify_values.py, extract_new_fields.py): paths,
fetch del dataset de Hugging Face / API oficial, y lectura/escritura de
data/01_data_understanding/universo_juegos.jsonl y bgg_data.jsonl.

Regla central de bgg_data.jsonl: NINGUNA función de acá reescribe el
archivo entero salvo write_bgg_cache_full (solo para el bootstrap, donde
no hay nada previo que perder). Para todo lo demás (agregar un juego
nuevo, editar un campo, sumar una columna) se usa upsert_bgg_cache, que
lee lo que ya está en disco y solo toca las filas/campos indicados —
así una fila editada a mano (ej. jug_min/max de community en vez de
caja) nunca se pisa con el dataset de origen en una corrida posterior.
"""
import ast
import csv
import html
import io
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
import json

csv.field_size_limit(10_000_000)  # el dataset de origen (Hugging Face) trae descripciones largas en una sola celda CSV

ROOT = Path(__file__).resolve().parent.parent.parent.parent
UNIVERSO_PATH = ROOT / "data" / "01_data_understanding" / "universo_juegos.jsonl"
BGG_DATA_PATH = ROOT / "data" / "01_data_understanding" / "bgg_data.jsonl"

DATASET_URL = (
    "https://huggingface.co/datasets/mmpa/board_game_analysis/"
    "resolve/main/games_detailed_info2025.csv"
)
API_URL = "https://boardgamegeek.com/xmlapi2/thing"
CRAWL_DELAY_SECONDS = 5  # robots.txt de BGG: Crawl-delay: 5
USER_AGENT = "boardgame-personal-catalog/1.0 (uso personal; contacto: negocios.mondineta@gmail.com)"

# data/01_data_understanding/universo_juegos.jsonl: identidad pura, sin
# estado ni ninguna opinión tuya (eso es mis_datos.jsonl).
UNIVERSO_FIELDS = ["bgg_id", "nombre", "bgg_url", "link_cazagangas"]
# data/01_data_understanding/bgg_data.jsonl: 100% de BGG.
# Orden de escritura: primero los campos cortos/estructurados, al final
# los de texto libre o longitud muy variable (descripcion) — así un
# campo largo en un juego puntual no corre de lugar a los campos que lo
# preceden en esa misma fila, y es más fácil ubicar una columna a ojo
# al editar el .jsonl a mano. Si extract_new_fields.py suma una columna
# nueva, se agrega acá (al final, antes de "descripcion" si es corta).
BGG_CACHE_FIELDS = [
    "bgg_id", "anio", "edad_min", "jug_min", "jug_max", "jug_best_min", "jug_best_max",
    "duracion_min", "duracion_max", "complejidad", "puntaje_bgg", "reviews_bgg", "ranking_bgg",
    "disenador", "mecanicas", "categorias", "descripcion",
]
LIST_FIELDS = {"mecanicas", "categorias"}

# Tags de BGG (mecánicas o categorías, da igual de cuál de las dos venga)
# que señalan modos de juego no competitivos de forma razonablemente
# confiable. "Semi-Cooperative Game" es el tag que usa BGG para juegos con
# un objetivo compartido pero intereses individuales en tensión (ej.
# traidor oculto) — el calce más cercano a "Cooperativo y competitivo".
# Usado tanto acá (search_new_game.py, para prellenar el stub de
# mis_datos.jsonl) como en 02_data_preparation/construct_data.py (para
# derivar `modo` en el build si todavía no está cargado a mano) — una sola
# definición, nunca duplicada.
MECANICA_SEMI_COOP = "Semi-Cooperative Game"
MECANICA_EQUIPOS = "Team-Based Game"
MECANICA_COOP = "Cooperative Game"


def infer_modo(mecanicas, categorias):
    """Devuelve un modo sugerido a partir de mecánicas/categorías de BGG,
    o None si no hay ninguna (no hay base para decidir, no hay que asumir
    "Competitivo" a ciegas). Quien llama decide si eso pisa o no un valor
    ya cargado a mano — acá no se mira mis_datos.jsonl para nada."""
    tags = set(mecanicas or []) | set(categorias or [])
    if not tags:
        return None
    if MECANICA_SEMI_COOP in tags:
        return "Cooperativo y competitivo"
    if MECANICA_EQUIPOS in tags:
        return "Equipos"
    if MECANICA_COOP in tags:
        return "Cooperativo"
    return "Competitivo"  # tenemos mecánicas/categorías y ninguna es de las de arriba


def normalize(s):
    s = (s or "").strip().lower()
    s = unicodedata.normalize("NFD", s)
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


def extract_bgg_id(url):
    match = re.search(r"/boardgame(?:expansion)?/(\d+)", url or "")
    return match.group(1) if match else None


def http_get(url, retries=3):
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


# ---------------------------------------------------------------------------
# Dataset placeholder (modo dummy, default) — Hugging Face
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


def _best_numplayers(suggested_num_players):
    """El dataset trae una lista de entries, salvo cuando el juego solo
    tiene un rango de jugadores posible: ahí viene un único dict pelado
    en vez de una lista de un elemento (ej. "Traditional Card Games",
    bgg_id 21804) — normalizar acá antes de iterar."""
    if isinstance(suggested_num_players, dict):
        suggested_num_players = [suggested_num_players]
    best_result, best_votes = None, -1
    for entry in suggested_num_players:
        for result in entry.get("result", []):
            if result.get("@value") != "Best":
                continue
            votes = int(result.get("@numvotes", 0))
            if votes > best_votes:
                best_votes, best_result = votes, entry.get("@numplayers")
    if not best_result:
        return None, None
    parts = best_result.replace("+", "").split("-")
    return parts[0], parts[-1]


def dataset_row_to_attributes(row):
    def num(key, zero_is_missing=False):
        value = (row.get(key) or "").strip()
        if not value:
            return None
        if zero_is_missing and value == "0":
            return None  # el dataset usa 0 como "sin dato" en duración/edad, no un valor real
        return value

    designers = _literal(row.get("boardgamedesigner"), [])
    mecanicas = _literal(row.get("boardgamemechanic"), [])
    categorias = _literal(row.get("boardgamecategory"), [])
    best_min, best_max = _best_numplayers(_literal(row.get("suggested_num_players"), []))
    description = (row.get("description") or "").strip()

    return {
        "anio": num("yearpublished"),
        "descripcion": html.unescape(description) if description else None,
        "disenador": ", ".join(designers) if designers else None,
        "edad_min": num("minage", zero_is_missing=True),
        # jug_min/jug_max: rango de CAJA (minplayers/maxplayers), no el
        # "Community" de la ficha de BGG — priorizar siempre Community
        # cuando se lo tenga a mano (ver modify_values.py).
        # 0 = sin dato (mismo sentinel que duracion/edad), no "no soporta
        # jugadores" — visible en la cola larga (juegos sin ficha completa).
        "jug_min": num("minplayers", zero_is_missing=True),
        "jug_max": num("maxplayers", zero_is_missing=True),
        "jug_best_min": best_min,
        "jug_best_max": best_max,
        "duracion_min": num("minplaytime", zero_is_missing=True),
        "duracion_max": num("maxplaytime", zero_is_missing=True),
        # 0.0 = sin votos todavía (mismo sentinel que edad_min/duracion),
        # no un peso/puntaje real — aparece en la larga cola de juegos sin
        # reviews, invisible mientras solo se procesaba el top N.
        "complejidad": num("averageweight", zero_is_missing=True),
        "puntaje_bgg": num("average", zero_is_missing=True),
        "reviews_bgg": num("usersrated"),
        "ranking_bgg": num("Board Game Rank"),
        "mecanicas": mecanicas,
        "categorias": categorias,
    }


# ---------------------------------------------------------------------------
# API oficial (modo api, para cuando BGG apruebe la aplicación)
# ---------------------------------------------------------------------------

def fetch_api_attributes(bgg_id):
    raw = http_get(f"{API_URL}?id={bgg_id}&stats=1")
    root = ET.fromstring(raw)
    item = root.find("item")
    if item is None:
        return None

    def text(tag, attr="value"):
        el = item.find(tag)
        return el.get(attr) if el is not None else None

    stats = item.find("statistics/ratings")
    rating = stats.find("average").get("value") if stats is not None and stats.find("average") is not None else None
    usersrated = stats.find("usersrated").get("value") if stats is not None and stats.find("usersrated") is not None else None
    rank_el = stats.find("ranks/rank[@name='boardgame']") if stats is not None else None
    rank = rank_el.get("value") if rank_el is not None else None
    weight = stats.find("averageweight").get("value") if stats is not None and stats.find("averageweight") is not None else None

    designers = [l.get("value") for l in item.findall("link[@type='boardgamedesigner']")]
    mecanicas = [l.get("value") for l in item.findall("link[@type='boardgamemechanic']")]
    categorias = [l.get("value") for l in item.findall("link[@type='boardgamecategory']")]

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

    desc_el = item.find("description")
    description = html.unescape(desc_el.text.strip()) if desc_el is not None and desc_el.text else None

    return {
        "anio": text("yearpublished"),
        "descripcion": description,
        "disenador": ", ".join(designers) or None,
        "edad_min": text("minage"),
        "jug_min": text("minplayers"),
        "jug_max": text("maxplayers"),
        "jug_best_min": best_min,
        "jug_best_max": best_max,
        "duracion_min": text("minplaytime"),
        "duracion_max": text("maxplaytime"),
        "complejidad": weight,
        "puntaje_bgg": rating,
        "reviews_bgg": usersrated,
        "ranking_bgg": rank,
        "mecanicas": mecanicas,
        "categorias": categorias,
    }


def fetch_attributes(bgg_id, mode, dataset):
    """mode == "api": xmlapi2/thing (respeta el Crawl-delay). mode ==
    "dummy": dataset de Hugging Face ya descargado (sin red extra)."""
    if mode == "api":
        return fetch_api_attributes(bgg_id)
    row = dataset.get(bgg_id)
    return dataset_row_to_attributes(row) if row else None


# ---------------------------------------------------------------------------
# universo_juegos.jsonl / bgg_data.jsonl: leer / escribir (un objeto JSON
# por línea)
# ---------------------------------------------------------------------------

def load_universo():
    if not UNIVERSO_PATH.exists():
        sys.exit(f"No existe {UNIVERSO_PATH} todavía; corré initialize_bgg_data.py primero")
    with UNIVERSO_PATH.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def write_universo(rows):
    with UNIVERSO_PATH.open("w", encoding="utf-8") as f:
        for row in rows:
            ordered = {k: (row.get(k) or "") for k in UNIVERSO_FIELDS}
            f.write(json.dumps(ordered, ensure_ascii=False))
            f.write("\n")


def load_bgg_cache():
    """Lee bgg_data.jsonl tal cual está en disco (incluye lo editado a
    mano). Lista vacía si el archivo todavía no existe."""
    if not BGG_DATA_PATH.exists():
        return []
    with BGG_DATA_PATH.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def _ordered_row(row, fields=BGG_CACHE_FIELDS):
    return {k: (row.get(k) if row.get(k) not in (None, "") else ([] if k in LIST_FIELDS else "")) for k in fields}


def write_bgg_cache_full(rows, fields=BGG_CACHE_FIELDS):
    """Reescribe el archivo entero. Usar SOLO en el bootstrap (no hay
    nada previo que perder) — cualquier otro caso de uso debe pasar por
    upsert_bgg_cache."""
    with BGG_DATA_PATH.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(_ordered_row(row, fields), ensure_ascii=False))
            f.write("\n")


def upsert_bgg_cache(updates_by_id, fields=BGG_CACHE_FIELDS):
    """Mergea `updates_by_id` ({bgg_id: {campo: valor, ...}}) sobre lo
    que ya está en bgg_data.jsonl: una fila existente cuyo bgg_id está en
    updates_by_id se actualiza solo en esos campos (lo demás, incluido
    cualquier edición manual previa, queda intacto); un bgg_id nuevo se
    agrega como fila nueva al final; una fila existente que NO está en
    updates_by_id se reescribe tal cual, sin tocarla. Devuelve
    (agregadas, actualizadas)."""
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
            f.write(json.dumps(_ordered_row(row, fields), ensure_ascii=False))
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
