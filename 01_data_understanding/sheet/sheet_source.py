"""Lee la pestaña "Juegos" del Google Sheet "Juegos_de_mesa" y la normaliza a
una lista de dicts por juego (identidad + Estado + campos cargados a mano).
Esta es la fuente de verdad de qué juegos existen y qué estado tienen — todo
lo demás (02_data_preparation/build_data.py, los scripts de Bosque Lúdico en
esta misma carpeta) parte de acá, nunca al revés.

La planilla es accesible por link (sin login), asi que se descarga como CSV
via el endpoint de export de Google Sheets, sin credenciales.

Las columnas se mapean por el texto de su encabezado (no por posicion), para
no romperse si se agrega o reordena una columna en el Sheet. Una columna
nueva que no matchee ninguna regla de HEADER_RULES se ignora en silencio.

Uso como módulo:
    from sheet_source import load_games
    games = load_games()  # todos los juegos, cualquier Estado

Uso como script: imprime un resumen por Estado, útil para chequear rápido
que el Sheet se está leyendo bien sin tener que correr todo build_data.py.
"""
import csv
import io
import re
import sys
import unicodedata
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from collections import Counter

SPREADSHEET_ID = "1ocu4prKGISdyRu9d1P-pVDx_paZoWTrDFpN8Dm51Yik"
GID = "1538311213"  # pestaña "Juegos"
SHEET_NAME = "Juegos"
EXPORT_URL = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/export?format=csv&gid={GID}"
XLSX_EXPORT_URL = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/export?format=xlsx"

NS_MAIN = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
NS_R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
NS_PKG_REL = "{http://schemas.openxmlformats.org/package/2006/relationships}"

HEADER_RULES = [
    ("nombre ingles", "nombre_en"),
    ("nombre espanol", "nombre_es"),
    ("modo", "modo"),
    ("ano", "anio"),
    ("descripcion", "descripcion"),
    ("jug min", "jug_min"),
    ("jug max", "jug_max"),
    ("jug best min", "jug_best_min"),
    ("jug best max", "jug_best_max"),
    ("duracion", "duracion"),
    ("edad min", "edad_min"),
    ("weight", "complejidad"),
    ("complejidad", "complejidad"),
    ("disenador", "disenador"),
    ("puntaje bgg", "puntaje_bgg"),
    ("reviews bgg", "reviews_bgg"),
    ("puntaje ajust bgg", "puntaje_ajust_bgg"),
    ("ranking bgg", "ranking_bgg"),
    ("pros", "pros"),
    ("cons", "cons"),
    ("mi puntaje", "mi_puntaje"),
    ("estado", "estado"),
    ("link a tienda", "link_tienda"),
    ("costo", "costo"),
    ("relacion precio calidad", "precio_calidad"),
    ("youtube", "youtube"),
    ("notas", "notas"),
]

# El link a BGG se toma del hyperlink que ya está puesto a mano sobre cada
# celda de la columna "Nombre ingles" en el Sheet (Insertar > Link). La API
# CSV no expone hyperlinks, asi que para leerlos se descarga el mismo Sheet
# como .xlsx (que sí los preserva) y se parsean del XML del paquete OOXML.
#
# Si una fila no tiene hyperlink puesto, se cae a un link de busqueda de BGG
# por titulo (usando "Nombre ingles", no la traduccion local): no es el
# permalink exacto, pero lleva directo al juego correcto en la gran mayoria
# de los casos. BGG_SEARCH_OVERRIDES pisa el termino de busqueda para esas
# filas, cuando el nombre de la caja no coincide con el titulo real en BGG
# (la pista suele estar en la columna Notas del Sheet).
# BGG_SKIP son juegos sin una ficha razonable en BGG (combos de dos juegos,
# rompecabezas, etc), y gana aunque la fila tenga un hyperlink puesto.
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

NUMERIC_FIELDS_FLOAT = {"complejidad", "puntaje_bgg", "puntaje_ajust_bgg", "precio_calidad"}
NUMERIC_FIELDS_INT = {"anio", "jug_min", "jug_max", "jug_best_min", "jug_best_max", "duracion", "edad_min",
                       "reviews_bgg", "ranking_bgg", "mi_puntaje", "costo"}
TEXT_FIELDS = {"nombre", "nombre_en", "nombre_es", "modo", "descripcion", "disenador", "pros", "cons", "estado",
               "link_tienda", "youtube", "notas"}


def normalize(s):
    s = (s or "").strip().lower()
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = "".join(c if c.isalnum() else " " for c in s)
    return " ".join(s.split())


def to_float(s):
    s = (s or "").strip()
    if not s or s == "-":
        return None
    s = s.replace(".", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def to_int(s):
    f = to_float(s)
    return int(f) if f is not None else None


def resolve_bgg_url(nombre, exact_url):
    if nombre in BGG_SKIP:
        return None
    if exact_url:
        return exact_url
    term = BGG_SEARCH_OVERRIDES.get(nombre)
    if term is None:
        term = re.sub(r"\s*\([^)]*\)\s*$", "", nombre).strip()
    return "https://boardgamegeek.com/geeksearch.php?action=search&objecttype=boardgame&q=" + urllib.parse.quote(term)


def col_letter(idx):
    """Convierte un indice de columna 0-based al estilo A1 (0 -> 'A', 26 -> 'AA')."""
    idx += 1
    letters = ""
    while idx > 0:
        idx, rem = divmod(idx - 1, 26)
        letters = chr(65 + rem) + letters
    return letters


def fetch_csv_rows():
    req = urllib.request.Request(EXPORT_URL, headers={"User-Agent": "Mozilla/5.0 (sheet_source.py)"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read().decode("utf-8")
    return list(csv.reader(io.StringIO(raw)))


def fetch_sheet_hyperlinks(sheet_name):
    """Devuelve {ref_de_celda: url} con los hyperlinks puestos a mano en la
    hoja `sheet_name` (ej. {"A13": "https://boardgamegeek.com/..."}), leyendo
    el export .xlsx del Sheet (la API CSV no expone hyperlinks)."""
    req = urllib.request.Request(XLSX_EXPORT_URL, headers={"User-Agent": "Mozilla/5.0 (sheet_source.py)"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read()

    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        workbook = ET.fromstring(zf.read("xl/workbook.xml"))
        rid = None
        for sheet in workbook.find(f"{NS_MAIN}sheets").findall(f"{NS_MAIN}sheet"):
            if sheet.get("name") == sheet_name:
                rid = sheet.get(f"{NS_R}id")
                break
        if rid is None:
            raise RuntimeError(f"No encontre la hoja '{sheet_name}' en el xlsx.")

        wb_rels = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
        wb_targets = {r.get("Id"): r.get("Target") for r in wb_rels.findall(f"{NS_PKG_REL}Relationship")}
        sheet_target = wb_targets.get(rid)
        if not sheet_target:
            raise RuntimeError(f"No pude resolver la ruta de la hoja '{sheet_name}' en el xlsx.")
        sheet_path = "xl/" + sheet_target.lstrip("/")
        sheet_dir, sheet_file = sheet_path.rsplit("/", 1)
        sheet_rels_path = f"{sheet_dir}/_rels/{sheet_file}.rels"

        rel_targets = {}
        if sheet_rels_path in zf.namelist():
            sheet_rels = ET.fromstring(zf.read(sheet_rels_path))
            rel_targets = {r.get("Id"): r.get("Target") for r in sheet_rels.findall(f"{NS_PKG_REL}Relationship")}

        sheet_xml = ET.fromstring(zf.read(sheet_path))
        hyperlinks_el = sheet_xml.find(f"{NS_MAIN}hyperlinks")
        hyperlinks = {}
        if hyperlinks_el is not None:
            for hl in hyperlinks_el.findall(f"{NS_MAIN}hyperlink"):
                ref, link_rid = hl.get("ref"), hl.get(f"{NS_R}id")
                if ref and link_rid in rel_targets:
                    hyperlinks[ref] = rel_targets[link_rid]
        return hyperlinks


def map_header(header_row):
    field_by_col = {}
    for idx, cell in enumerate(header_row):
        norm = normalize(cell)
        for key, field in HEADER_RULES:
            if key in norm:
                field_by_col[idx] = field
                break
    return field_by_col


def build_games(rows, bgg_hyperlinks):
    header_idx = None
    for i, row in enumerate(rows):
        if row and "nombre_en" in map_header(row).values():
            header_idx = i
            break
    if header_idx is None:
        raise RuntimeError("No encontre la fila de encabezado (columna 'Nombre ingles') en el CSV exportado.")

    field_by_col = map_header(rows[header_idx])
    nombre_col = next(idx for idx, field in field_by_col.items() if field == "nombre_en")
    nombre_col_letter = col_letter(nombre_col)

    games = []
    for row_num, row in enumerate(rows[header_idx + 1:], start=header_idx + 2):
        if not row or not row[0].strip():
            continue
        game = {}
        for idx, field in field_by_col.items():
            value = row[idx] if idx < len(row) else ""
            if field in NUMERIC_FIELDS_FLOAT:
                game[field] = to_float(value)
            elif field in NUMERIC_FIELDS_INT:
                game[field] = to_int(value)
            else:
                game[field] = value.strip()
        # "Nombre español" es el nombre de catalogo cuando esta cargado (la
        # traduccion/edicion local); si esta vacio, el Sheet repite el mismo
        # nombre en "Nombre ingles" en vez de duplicarlo a mano.
        game["nombre"] = game.get("nombre_es") or game.get("nombre_en", "")
        exact_url = bgg_hyperlinks.get(f"{nombre_col_letter}{row_num}")
        game["bgg_url"] = resolve_bgg_url(game.get("nombre_en", ""), exact_url)
        games.append(game)
    return games


def load_games():
    """Punto de entrada único: Sheet -> lista de dicts por juego (cualquier
    Estado), con bgg_url ya resuelto. No aplica ningún enriquecimiento
    externo (BGG cache, Bosque Lúdico) — eso es trabajo de 02_data_preparation."""
    rows = fetch_csv_rows()
    try:
        bgg_hyperlinks = fetch_sheet_hyperlinks(SHEET_NAME)
    except Exception as e:
        print(f"Advertencia: no pude leer los hyperlinks de BGG del xlsx ({e}); uso busqueda por nombre.", file=sys.stderr)
        bgg_hyperlinks = {}
    games = build_games(rows, bgg_hyperlinks)
    if len(games) < 10:
        sys.exit(f"Advertencia: solo se parsearon {len(games)} juegos, algo puede estar mal.")
    return games


def main():
    games = load_games()
    counts = Counter(g.get("estado") or "(vacío)" for g in games)
    print(f"{len(games)} juegos leídos del Sheet:")
    for estado, n in counts.most_common():
        print(f"  {estado}: {n}")


if __name__ == "__main__":
    main()
