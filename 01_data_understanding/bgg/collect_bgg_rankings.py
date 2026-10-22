"""Descarga el top N del ranking de BGG desde un dataset público de terceros
(no la API de BGG, que sigue devolviendo 401 sin auth — ver enrich_bgg.py) y
lo guarda versionado en el repo.

Fuente: github.com/beefsack/bgg-ranking-historicals, un CSV diario (scrapeado
por ese proyecto, no por nosotros) con el ranking completo de BGG — id,
nombre, año, ranking, puntaje, cantidad de reviews, URL. Es un archivo
público en texto plano servido por raw.githubusercontent.com, sin auth ni
challenge.

Esto es la base para el universo de "juegos candidatos a comprar"
(game_universe.py, en esta misma carpeta un nivel arriba): cualquier juego
de este top N que no esté ya en el Sheet (Own/Prev. owned) entra como
Watchlist en el dataset integrado.

Salida: 01_data_understanding/bgg/bgg_top1000.csv — SE COMMITEA (a
diferencia del resto de lo que recolecta 01_data_understanding/, que es
caché gitignored): es un snapshot pinneado, no un derivado que se puede
recalcular igual en cualquier momento — re-correr este script y versionar el
diff deja ver qué juegos subieron/bajaron de ranking entre corridas.

Uso:
    python3 01_data_understanding/bgg/collect_bgg_rankings.py [--top N]
"""
import argparse
import csv
import io
import json
import re
import sys
import urllib.request
from pathlib import Path

REPO = "beefsack/bgg-ranking-historicals"
COMMITS_API = f"https://api.github.com/repos/{REPO}/commits?per_page=1"
RAW_URL_TMPL = f"https://raw.githubusercontent.com/{REPO}/master/{{filename}}"
USER_AGENT = "boardgame-personal-catalog/1.0 (uso personal; contacto: negocios.mondineta@gmail.com)"

OUTPUT_PATH = Path(__file__).resolve().parent / "bgg_top1000.csv"
OUTPUT_FIELDS = ["bgg_id", "nombre", "anio", "ranking_bgg", "puntaje_bgg", "reviews_bgg", "bgg_url"]


def http_get(url):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8")


def latest_csv_filename():
    """El repo tiene miles de CSVs (uno por día desde 2016); la API de
    listado de contenidos de GitHub corta en 1000 archivos, así que en vez
    de listar el directorio se lee el último commit (su mensaje es
    "Added YYYY-MM-DD.csv")."""
    commits = json.loads(http_get(COMMITS_API))
    message = commits[0]["commit"]["message"]
    match = re.search(r"(\d{4}-\d{2}-\d{2}\.csv)", message)
    if not match:
        sys.exit(f"No pude extraer el nombre del CSV del último commit: {message!r}")
    return match.group(1)


def to_int(s):
    s = (s or "").strip()
    return int(s) if s else None


def to_float(s):
    s = (s or "").strip()
    return float(s) if s else None


def main():
    parser = argparse.ArgumentParser(description="Descarga el top N del ranking de BGG (dataset público de terceros)")
    parser.add_argument("--top", type=int, default=1000, help="cuántos juegos guardar, por ranking (default 1000)")
    args = parser.parse_args()

    filename = latest_csv_filename()
    print(f"Descargando {filename}...")
    raw = http_get(RAW_URL_TMPL.format(filename=filename))
    rows = list(csv.DictReader(io.StringIO(raw)))
    rows.sort(key=lambda r: to_int(r["Rank"]) or 10**9)
    top = rows[: args.top]

    with OUTPUT_PATH.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_FIELDS)
        writer.writeheader()
        for r in top:
            writer.writerow({
                "bgg_id": r["ID"],
                "nombre": r["Name"],
                "anio": to_int(r.get("Year")),
                "ranking_bgg": to_int(r["Rank"]),
                "puntaje_bgg": to_float(r.get("Average")),
                "reviews_bgg": to_int(r.get("Users rated")),
                "bgg_url": "https://boardgamegeek.com" + r["URL"],
            })

    print(f"OK: top {len(top)} guardado en {OUTPUT_PATH} (fuente: {filename})")


if __name__ == "__main__":
    main()
