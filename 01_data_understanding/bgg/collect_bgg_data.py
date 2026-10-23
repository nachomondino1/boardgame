"""Recolección inicial de BGG: un único archivo, bgg_data.csv, que es a la
vez el "universo de juegos" (qué juegos existen, con qué estado) y sus datos
de BGG (rating, duración, etc.) — reemplaza lo que antes eran tres piezas
separadas (collect_bgg_rankings.py + game_universe.py + enrich_bgg.py).

bgg_id es la primera columna, para poder integrar fácil con lo que salga de
otras fuentes (ej. bosque_data.csv el día que se automatice — ver el README
de esta carpeta).

Columnas que son tuyas, nunca las toca el enriquecimiento de BGG:
    bgg_id, nombre, estado, bgg_url, modo, mi_puntaje, pros, cons, youtube, notas
El resto (anio, descripcion, disenador, edad_min, jug_min/max,
jug_best_min/max, duracion_min/max, complejidad, puntaje_bgg, reviews_bgg,
ranking_bgg, mecanicas, categorias) sale de BGG y se refresca en cada corrida.

Tres usos:
  1. Bootstrap (primera vez, bgg_data.csv no existe todavía): arma el
     universo con el top N del ranking de BGG + tus propios juegos (lee
     ludoteca/mi_ludoteca.json UNA SOLA VEZ para taguear Own/Prev. owned —
     después de este bootstrap ese archivo ya no hace falta, se puede
     borrar). El resto de los juegos del top N quedan en Watchlist.
  2. Refresh (default si bgg_data.csv ya existe, sin --add): re-descarga el
     dataset de BGG y actualiza los campos de BGG de los juegos que YA
     están en bgg_data.csv. Nunca agrega ni saca filas.
  3. Agregar un juego puntual (--add): `collect_bgg_data.py --add <id o
     nombre> [--estado Own|"Prev. owned"|Watchlist]`. Así es como se
     amplía el universo de acá en más — bgg_data.csv no se regenera solo,
     se le pide explícitamente que sume un juego.

De dónde sale el dato de BGG hoy: BGG cerró el acceso sin auth a xmlapi2
(401 hasta que aprueben la aplicación registrada) — ver DATA_PLAYBOOK.md.
Mientras tanto, se usa como placeholder un dataset público de terceros con
un snapshot de BGG de 2025 (games_detailed_info2025.csv de
mmpa/board_game_analysis en Hugging Face, ~28.000 juegos, sin auth): trae
tanto el ranking completo (columna "Board Game Rank") como los detalles por
juego, en un solo archivo — no hace falta combinar dos datasets distintos.
`--mode api` reemplaza esto por xmlapi2/thing en cuanto BGG apruebe la app.

Uso:
    python3 01_data_understanding/bgg/collect_bgg_data.py                  # bootstrap o refresh según corresponda
    python3 01_data_understanding/bgg/collect_bgg_data.py --top 1500       # bootstrap con otro tamaño de universo
    python3 01_data_understanding/bgg/collect_bgg_data.py --add 174430     # agrega Gloomhaven (Watchlist)
    python3 01_data_understanding/bgg/collect_bgg_data.py --add "Wingspan" --estado Own
"""
import argparse
import ast
import csv
import difflib
import html
import io
import json
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

csv.field_size_limit(10_000_000)  # el dataset trae descripciones largas en una sola celda

HERE = Path(__file__).resolve().parent
BGG_DATA_PATH = HERE / "bgg_data.csv"
LUDOTECA_PATH = HERE.parent / "ludoteca" / "mi_ludoteca.json"

DATASET_URL = (
    "https://huggingface.co/datasets/mmpa/board_game_analysis/"
    "resolve/main/games_detailed_info2025.csv"
)
API_URL = "https://boardgamegeek.com/xmlapi2/thing"
CRAWL_DELAY_SECONDS = 5  # robots.txt de BGG: Crawl-delay: 5
USER_AGENT = "boardgame-personal-catalog/1.0 (uso personal; contacto: negocios.mondineta@gmail.com)"

TOP_N_DEFAULT = 1000

# Columnas propias (nunca las pisa el enriquecimiento) vs. las que vienen de BGG.
OWNED_FIELDS = ["bgg_id", "nombre", "estado", "bgg_url", "modo", "mi_puntaje", "pros", "cons", "youtube", "notas"]
BGG_FIELDS = ["anio", "descripcion", "disenador", "edad_min", "jug_min", "jug_max", "jug_best_min", "jug_best_max",
              "duracion_min", "duracion_max", "complejidad", "puntaje_bgg", "reviews_bgg", "ranking_bgg",
              "mecanicas", "categorias"]
ALL_FIELDS = OWNED_FIELDS + BGG_FIELDS

# Mismo patrón que tenía ludoteca_source.py: para ediciones locales o
# nombres que no matchean bien contra BGG, se fuerza el término de
# búsqueda o se marca el juego como sin ficha razonable en BGG. Solo se usa
# en el bootstrap (una sola lectura de mi_ludoteca.json).
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
# Dataset placeholder (modo dummy, default)
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
        "jug_min": num("minplayers"),
        "jug_max": num("maxplayers"),
        "jug_best_min": best_min,
        "jug_best_max": best_max,
        "duracion_min": num("minplaytime", zero_is_missing=True),
        "duracion_max": num("maxplaytime", zero_is_missing=True),
        "complejidad": num("averageweight"),
        "puntaje_bgg": num("average"),
        "reviews_bgg": num("usersrated"),
        "ranking_bgg": num("Board Game Rank"),
        "mecanicas": "|".join(mecanicas),
        "categorias": "|".join(categorias),
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
        "mecanicas": "|".join(mecanicas),
        "categorias": "|".join(categorias),
    }


# ---------------------------------------------------------------------------
# bgg_data.csv: leer / escribir
# ---------------------------------------------------------------------------

def load_existing():
    with BGG_DATA_PATH.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_csv(rows):
    with BGG_DATA_PATH.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=ALL_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") or "" for k in ALL_FIELDS})


# ---------------------------------------------------------------------------
# Bootstrap: ludoteca (una sola vez) + top N del ranking de BGG
# ---------------------------------------------------------------------------

def load_ludoteca_once():
    if not LUDOTECA_PATH.exists():
        print(f"Aviso: no encontré {LUDOTECA_PATH}, bootstrap sin juegos propios.", file=sys.stderr)
        return []

    entries = json.loads(LUDOTECA_PATH.read_text(encoding="utf-8"))
    own = []
    for entry in entries:
        nombre_en = (entry.get("nombre_en") or "").strip()
        if not nombre_en:
            continue
        nombre = entry.get("nombre_es") or nombre_en

        if nombre_en in BGG_SKIP:
            bgg_url = None
        elif entry.get("bgg_url"):
            bgg_url = entry["bgg_url"]
        else:
            term = BGG_SEARCH_OVERRIDES.get(nombre_en) or re.sub(r"\s*\([^)]*\)\s*$", "", nombre_en).strip()
            bgg_url = "https://boardgamegeek.com/geeksearch.php?action=search&objecttype=boardgame&q=" + urllib.parse.quote(term)

        own.append({
            "bgg_id": entry.get("bgg_id") or extract_bgg_id(bgg_url) or "",
            "nombre": nombre,
            "estado": entry.get("estado") or "",
            "bgg_url": bgg_url or "",
            "modo": entry.get("modo") or "",
            "mi_puntaje": entry.get("mi_puntaje") or "",
            "pros": entry.get("pros") or "",
            "cons": entry.get("cons") or "",
            "youtube": entry.get("youtube") or "",
            "notas": entry.get("notas") or "",
        })
    return own


def bootstrap(dataset, top_n):
    own = load_ludoteca_once()
    owned_ids = {g["bgg_id"] for g in own if g["bgg_id"]}
    rows = list(own)

    ranked = sorted(dataset.values(), key=lambda r: float(r.get("Board Game Rank") or 10**9))
    added = 0
    for r in ranked:
        if added >= top_n:
            break
        if r["id"] in owned_ids:
            continue
        rows.append({
            "bgg_id": r["id"],
            "nombre": r["name"],
            "estado": "Watchlist",
            "bgg_url": f"https://boardgamegeek.com/boardgame/{r['id']}",
        })
        added += 1

    print(f"Bootstrap: {len(own)} juego(s) propios + {added} candidatos del top {top_n} de BGG.")
    return rows


# ---------------------------------------------------------------------------
# Agregar un juego puntual
# ---------------------------------------------------------------------------

def find_in_dataset(term, dataset):
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


def add_game(term, estado, dataset):
    row = find_in_dataset(term, dataset)
    new_row = {
        "bgg_id": row["id"],
        "nombre": row["name"],
        "estado": estado or "Watchlist",
        "bgg_url": f"https://boardgamegeek.com/boardgame/{row['id']}",
    }
    print(f"Agregando: {new_row['nombre']} (bgg_id={new_row['bgg_id']}, estado={new_row['estado']})")
    return new_row


# ---------------------------------------------------------------------------

def enrich(rows, dataset, mode):
    for i, row in enumerate(rows):
        bgg_id = (row.get("bgg_id") or "").strip()
        if not bgg_id:
            continue
        if mode == "api":
            attrs = fetch_api_attributes(bgg_id)
            if i < len(rows) - 1:
                time.sleep(CRAWL_DELAY_SECONDS)
        else:
            source = dataset.get(bgg_id)
            attrs = dataset_row_to_attributes(source) if source else None
        if attrs:
            row.update(attrs)
    return rows


def main():
    parser = argparse.ArgumentParser(description="Universo de juegos + datos de BGG en un único bgg_data.csv")
    parser.add_argument("--add", metavar="ID_O_NOMBRE", help="agrega un juego puntual (por id de BGG o nombre)")
    parser.add_argument("--estado", choices=["Own", "Prev. owned", "Watchlist"],
                         help="estado del juego agregado con --add (default Watchlist)")
    parser.add_argument("--top", type=int, default=TOP_N_DEFAULT, help="tamaño del universo en el bootstrap (default 1000)")
    parser.add_argument("--mode", choices=["dummy", "api"], default="dummy",
                         help="dummy = dataset placeholder de terceros (default, hoy); "
                              "api = xmlapi2 oficial (requiere app aprobada)")
    args = parser.parse_args()

    if args.estado and not args.add:
        parser.error("--estado solo tiene sentido junto con --add")

    dataset = fetch_dataset() if args.mode == "dummy" else {}

    if args.add:
        if not BGG_DATA_PATH.exists():
            parser.error(f"No existe {BGG_DATA_PATH} todavía; corré el script sin --add primero para el bootstrap")
        rows = load_existing()
        if args.add.strip().isdigit() and any(r["bgg_id"] == args.add.strip() for r in rows):
            sys.exit(f"El juego con bgg_id {args.add} ya está en {BGG_DATA_PATH}.")
        rows.append(add_game(args.add, args.estado, dataset))
    elif not BGG_DATA_PATH.exists():
        rows = bootstrap(dataset, args.top)
    else:
        rows = load_existing()
        print(f"{len(rows)} juego(s) ya en {BGG_DATA_PATH}, refrescando datos de BGG...")

    enrich(rows, dataset, args.mode)
    write_csv(rows)
    print(f"\nOK: {len(rows)} juego(s) en {BGG_DATA_PATH}")


if __name__ == "__main__":
    main()
