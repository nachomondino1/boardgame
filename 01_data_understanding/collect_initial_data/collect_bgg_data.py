"""Recolección inicial de BGG, a partir del catálogo de identidad en
data/01_data_understanding/universo_juegos.jsonl (ver DATA_PLAYBOOK.md,
"Las columnas que no vienen de BGG viven en su propio archivo"):

- data/01_data_understanding/universo_juegos.jsonl — EL catálogo de
  identidad: bgg_id, nombre, bgg_url, link_cazagangas. Es la lista de
  "qué juegos conoce este repo", sin opinión tuya sobre ellos (eso vive en
  mis_datos.jsonl, que es 100% manual — ver más abajo). Este script sí lo
  escribe (bootstrap, --add), siempre identidad pura: nunca un estado, ni
  tu puntaje, ni nada de mis_datos.jsonl.
- data/01_data_understanding/bgg_data.jsonl — caché 100% regenerable de
  datos de BGG (rating, duración, etc.) para cada bgg_id de
  universo_juegos.jsonl. Se reescribe entera en cada corrida; si se borra,
  se reconstruye sola con el próximo refresh.
- data/01_data_understanding/mis_datos.jsonl — estado, modo, transportable,
  mi_puntaje, pros, cons, notas: 100% tuyo, lo cargás vos a mano. Este
  script NUNCA lo toca ni lo lee.

Formato de todos: JSON Lines, un juego por línea (no un array). Se eligió
sobre CSV porque `descripcion` trae texto libre de BGG con saltos de línea
reales adentro, lo que en CSV hacía que una sola fila se desparramara en
decenas de líneas visuales en el editor — en JSONL un salto de línea dentro
de un string se escapa (`\\n` literal), así que cada juego queda
garantizado en una sola línea física, buscable por nombre con Ctrl+F.

El resto de bgg_data.jsonl (anio, descripcion, disenador, edad_min,
jug_min/max, jug_best_min/max, duracion_min/max, complejidad, puntaje_bgg,
reviews_bgg, ranking_bgg, mecanicas, categorias) sale de BGG y se refresca
en cada corrida. `mecanicas`/`categorias` se guardan como array JSON (no
como string separado por "|").

Tres usos:
  1. Bootstrap (primera vez, universo_juegos.jsonl no existe todavía): arma
     el catálogo con el top N del ranking de BGG + tus propios juegos (lee
     ludoteca/mi_ludoteca.json UNA SOLA VEZ para identidad — después de
     este bootstrap ese archivo ya no hace falta, se puede borrar). No
     asigna ningún estado: eso lo cargás vos en mis_datos.jsonl aparte.
  2. Refresh (default si universo_juegos.jsonl ya existe, sin --add):
     reconstruye bgg_data.jsonl entero a partir de los bgg_id que ya están
     en universo_juegos.jsonl. Nunca toca universo_juegos.jsonl ni
     mis_datos.jsonl.
  3. Agregar un juego puntual (--add): `collect_bgg_data.py --add <id o
     nombre>`. Resuelve bgg_id/nombre/bgg_url automático contra el dataset
     y agrega la fila a universo_juegos.jsonl con `link_cazagangas` vacío
     — cargá ese link a mano (la ficha real en cazagangas.com.ar/juego/...)
     y corré check_cazagangas_links.py para verificarlo. Después, agregá
     el juego a mis_datos.jsonl a mano con el estado que quieras: este
     script no lo hace por vos.

De dónde sale el dato de BGG hoy: BGG cerró el acceso sin auth a xmlapi2
(401 hasta que aprueben la aplicación registrada) — ver DATA_PLAYBOOK.md.
Mientras tanto, se usa como placeholder un dataset público de terceros con
un snapshot de BGG de 2025 (games_detailed_info2025.csv de
mmpa/board_game_analysis en Hugging Face, ~28.000 juegos, sin auth): trae
tanto el ranking completo (columna "Board Game Rank") como los detalles por
juego, en un solo archivo — no hace falta combinar dos datasets distintos.
`--mode api` reemplaza esto por xmlapi2/thing en cuanto BGG apruebe la app.

Uso:
    python3 01_data_understanding/collect_initial_data/collect_bgg_data.py                  # bootstrap o refresh según corresponda
    python3 01_data_understanding/collect_initial_data/collect_bgg_data.py --top 1500       # bootstrap con otro tamaño de universo
    python3 01_data_understanding/collect_initial_data/collect_bgg_data.py --add 174430     # agrega Gloomhaven a universo_juegos.jsonl
    python3 01_data_understanding/collect_initial_data/collect_bgg_data.py --add "Wingspan"
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

csv.field_size_limit(10_000_000)  # el dataset de origen (Hugging Face) trae descripciones largas en una sola celda CSV

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
UNIVERSO_PATH = ROOT / "data" / "01_data_understanding" / "universo_juegos.jsonl"
BGG_DATA_PATH = ROOT / "data" / "01_data_understanding" / "bgg_data.jsonl"
LUDOTECA_PATH = HERE / "ludoteca" / "mi_ludoteca.json"

DATASET_URL = (
    "https://huggingface.co/datasets/mmpa/board_game_analysis/"
    "resolve/main/games_detailed_info2025.csv"
)
API_URL = "https://boardgamegeek.com/xmlapi2/thing"
CRAWL_DELAY_SECONDS = 5  # robots.txt de BGG: Crawl-delay: 5
USER_AGENT = "boardgame-personal-catalog/1.0 (uso personal; contacto: negocios.mondineta@gmail.com)"

TOP_N_DEFAULT = 1000

# data/01_data_understanding/universo_juegos.jsonl: identidad pura, sin
# estado ni ninguna opinión tuya (eso es mis_datos.jsonl, que este script
# ni lee ni escribe).
UNIVERSO_FIELDS = ["bgg_id", "nombre", "bgg_url", "link_cazagangas"]
# data/01_data_understanding/bgg_data.jsonl: 100% de BGG, se refresca entero en cada corrida.
BGG_FIELDS = ["anio", "descripcion", "disenador", "edad_min", "jug_min", "jug_max", "jug_best_min", "jug_best_max",
              "duracion_min", "duracion_max", "complejidad", "puntaje_bgg", "reviews_bgg", "ranking_bgg",
              "mecanicas", "categorias"]
# Orden de escritura: primero los campos cortos/estructurados (numéricos o
# de longitud parecida entre juegos), al final los de texto libre o
# longitud muy variable (descripcion) — así un campo largo en un juego
# puntual no corre de lugar a los campos que lo preceden en esa misma fila,
# y es más fácil ubicar una columna a ojo al editar el .jsonl a mano.
BGG_CACHE_FIELDS = [
    "bgg_id", "anio", "edad_min", "jug_min", "jug_max", "jug_best_min", "jug_best_max",
    "duracion_min", "duracion_max", "complejidad", "puntaje_bgg", "reviews_bgg", "ranking_bgg",
    "disenador", "mecanicas", "categorias", "descripcion",
]
LIST_FIELDS = {"mecanicas", "categorias"}

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
        # jug_min/jug_max: esto es el rango de CAJA (minplayers/maxplayers),
        # no el "Community" de la ficha de BGG. Regla fija: priorizar
        # siempre el dato de Community sobre este cuando se lo tenga (el
        # dataset placeholder no lo trae, solo se puede chequear a mano en
        # la ficha o si el usuario lo pasa) — y si se usa este valor de
        # caja por default, dejar nota en "notas" aclarándolo. Ver
        # 01_data_understanding/README.md, tabla de columnas.
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


# ---------------------------------------------------------------------------
# universo_juegos.jsonl / bgg_data.jsonl: leer / escribir (un objeto JSON
# por línea, ver docstring)
# ---------------------------------------------------------------------------

def load_universo():
    with UNIVERSO_PATH.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def write_universo(rows):
    with UNIVERSO_PATH.open("w", encoding="utf-8") as f:
        for row in rows:
            ordered = {k: (row.get(k) or "") for k in UNIVERSO_FIELDS}
            f.write(json.dumps(ordered, ensure_ascii=False))
            f.write("\n")


def write_bgg_cache(rows):
    with BGG_DATA_PATH.open("w", encoding="utf-8") as f:
        for row in rows:
            ordered = {k: (row.get(k) or ([] if k in LIST_FIELDS else "")) for k in BGG_CACHE_FIELDS}
            f.write(json.dumps(ordered, ensure_ascii=False))
            f.write("\n")


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
            "bgg_url": bgg_url or "",
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
            "bgg_url": f"https://boardgamegeek.com/boardgame/{r['id']}",
        })
        added += 1

    print(f"Bootstrap: {len(own)} juego(s) propios + {added} candidatos del top {top_n} de BGG "
          f"(identidad nomás — cargá el estado de cada uno en mis_datos.jsonl a mano).")
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


def add_game(term, dataset):
    row = find_in_dataset(term, dataset)
    new_row = {
        "bgg_id": row["id"],
        "nombre": row["name"],
        "bgg_url": f"https://boardgamegeek.com/boardgame/{row['id']}",
        "link_cazagangas": "",
    }
    print(f"Agregando a {UNIVERSO_PATH.name}: {new_row['nombre']} (bgg_id={new_row['bgg_id']})")
    print("  Falta: link_cazagangas a mano (la ficha real en cazagangas.com.ar/juego/...),")
    print(f"  y el estado en mis_datos.jsonl (este script no lo toca).")
    return new_row


# ---------------------------------------------------------------------------

def build_bgg_cache(universo_rows, dataset, mode):
    """Reconstruye el caché de BGG entero a partir de los bgg_id no vacíos
    de universo_rows — un juego sin bgg_id (BGG_SKIP, o sin match todavía)
    simplemente no tiene fila acá, no es un error."""
    ids = [(r.get("bgg_id") or "").strip() for r in universo_rows]
    ids = [i for i in ids if i]

    cache_rows = []
    for i, bgg_id in enumerate(ids):
        if mode == "api":
            attrs = fetch_api_attributes(bgg_id)
            if i < len(ids) - 1:
                time.sleep(CRAWL_DELAY_SECONDS)
        else:
            source = dataset.get(bgg_id)
            attrs = dataset_row_to_attributes(source) if source else None
        row = {"bgg_id": bgg_id}
        if attrs:
            row.update(attrs)
        cache_rows.append(row)
    return cache_rows


def main():
    parser = argparse.ArgumentParser(description="Catálogo de identidad (data/01_data_understanding/universo_juegos.jsonl) + caché de BGG (data/01_data_understanding/bgg_data.jsonl)")
    parser.add_argument("--add", metavar="ID_O_NOMBRE", help="agrega un juego puntual a universo_juegos.jsonl (por id de BGG o nombre)")
    parser.add_argument("--top", type=int, default=TOP_N_DEFAULT, help="tamaño del universo en el bootstrap (default 1000)")
    parser.add_argument("--mode", choices=["dummy", "api"], default="dummy",
                         help="dummy = dataset placeholder de terceros (default, hoy); "
                              "api = xmlapi2 oficial (requiere app aprobada)")
    args = parser.parse_args()

    dataset = fetch_dataset() if args.mode == "dummy" else {}

    if args.add:
        if not UNIVERSO_PATH.exists():
            parser.error(f"No existe {UNIVERSO_PATH} todavía; corré el script sin --add primero para el bootstrap")
        rows = load_universo()
        if args.add.strip().isdigit() and any(r["bgg_id"] == args.add.strip() for r in rows):
            sys.exit(f"El juego con bgg_id {args.add} ya está en {UNIVERSO_PATH}.")
        rows.append(add_game(args.add, dataset))
        write_universo(rows)
    elif not UNIVERSO_PATH.exists():
        rows = bootstrap(dataset, args.top)
        write_universo(rows)
    else:
        rows = load_universo()
        print(f"{len(rows)} juego(s) ya en {UNIVERSO_PATH}, refrescando caché de BGG...")

    cache_rows = build_bgg_cache(rows, dataset, args.mode)
    write_bgg_cache(cache_rows)
    print(f"\nOK: {len(rows)} juego(s) en {UNIVERSO_PATH}, {len(cache_rows)} con datos de BGG en {BGG_DATA_PATH}")


if __name__ == "__main__":
    main()
