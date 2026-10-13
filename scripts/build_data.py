"""Regenera data.json a partir de la pestaña "Juegos" del Google Sheet.

La planilla es accesible por link (sin login), asi que se descarga como CSV
via el endpoint de export de Google Sheets, sin credenciales.

Las columnas se mapean por el texto de su encabezado (no por posicion), para
no romperse si se agrega o reordena una columna en el Sheet. Una columna
nueva que no matchee ninguna regla de HEADER_RULES se ignora en silencio.
"""
import csv
import io
import json
import sys
import unicodedata
import urllib.request

SPREADSHEET_ID = "1ocu4prKGISdyRu9d1P-pVDx_paZoWTrDFpN8Dm51Yik"
GID = "1538311213"  # pestaña "Juegos"
EXPORT_URL = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/export?format=csv&gid={GID}"

OUTPUT_PATH = "data.json"

HEADER_RULES = [
    ("juego", "nombre"),
    ("modo", "modo"),
    ("ano", "anio"),
    ("descripcion", "descripcion"),
    ("jug min", "jug_min"),
    ("jug max", "jug_max"),
    ("jug best", "jug_best"),
    ("entra con", "entra_con_expansion"),
    ("duracion", "duracion"),
    ("edad min", "edad_min"),
    ("complejidad", "complejidad"),
    ("disenador", "disenador"),
    ("puntaje bgg", "puntaje_bgg"),
    ("reviews bgg", "reviews_bgg"),
    ("p x r", "p_x_r"),
    ("ranking bgg", "ranking_bgg"),
    ("pros", "pros"),
    ("cons", "cons"),
    ("mi puntaje", "mi_puntaje"),
    ("estado", "estado"),
    ("ocasion ideal", "ocasion_ideal"),
    ("expansion", "expansion"),
    ("youtube", "youtube"),
    ("notas", "notas"),
]

NUMERIC_FIELDS_FLOAT = {"complejidad", "puntaje_bgg", "p_x_r"}
NUMERIC_FIELDS_INT = {"anio", "jug_min", "jug_max", "duracion", "edad_min", "reviews_bgg", "ranking_bgg", "mi_puntaje"}
TEXT_FIELDS = {"nombre", "modo", "descripcion", "jug_best", "entra_con_expansion", "disenador",
               "pros", "cons", "estado", "ocasion_ideal", "expansion", "youtube", "notas"}


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


def fetch_csv_rows():
    req = urllib.request.Request(EXPORT_URL, headers={"User-Agent": "Mozilla/5.0 (build_data.py)"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read().decode("utf-8")
    return list(csv.reader(io.StringIO(raw)))


def map_header(header_row):
    field_by_col = {}
    for idx, cell in enumerate(header_row):
        norm = normalize(cell)
        for key, field in HEADER_RULES:
            if key in norm:
                field_by_col[idx] = field
                break
    return field_by_col


def build_games(rows):
    header_idx = None
    for i, row in enumerate(rows):
        if row and normalize(row[0]) == "juego":
            header_idx = i
            break
    if header_idx is None:
        raise RuntimeError("No encontre la fila de encabezado (columna 'Juego') en el CSV exportado.")

    field_by_col = map_header(rows[header_idx])
    if "nombre" not in field_by_col.values():
        raise RuntimeError("No pude mapear la columna 'Juego' del encabezado.")

    games = []
    for row in rows[header_idx + 1:]:
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
        games.append(game)
    return games


def main():
    rows = fetch_csv_rows()
    games = build_games(rows)
    if len(games) < 10:
        print(f"Advertencia: solo se parsearon {len(games)} juegos, algo puede estar mal.", file=sys.stderr)
        sys.exit(1)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(games, f, ensure_ascii=False, indent=2)
    print(f"OK: {len(games)} juegos escritos en {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
