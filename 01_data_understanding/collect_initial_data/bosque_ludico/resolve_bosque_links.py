"""PAUSADO por ahora (ver DATA_PLAYBOOK.md): el paso de integración que iba
a consumir esto (bgg_data.csv + bosque_data.csv por nombre) todavía no
existe. Este script sigue funcionando solo, generando links.json, pero
nada lo lee todavía — queda listo para cuando se construya esa integración.

Arma el catálogo central juego -> links externos (BGG + El Bosque Lúdico)
para los juegos en Watchlist de 01_data_understanding/collect_initial_data/bgg/bgg_data.csv (el
universo de juegos — ver collect_bgg_data.py), como paso previo a relevar
precios.

Unidad de análisis: un juego de la Watchlist. Para cada uno se guarda el
bgg_id, el nombre, el link a BGG y el link a su ficha en El Bosque Lúdico,
resuelto acá por nombre.

Por qué no se usa /search/?q=... de El Bosque Lúdico: su robots.txt bloquea
"Disallow: /search/" explícitamente. En cambio se descarga una sola vez su
sitemap.xml.gz (listado público pensado para ser indexado, no bloqueado) con
todas las fichas de producto, y se matchea cada juego contra esos slugs por
similitud de texto. Esto resuelve el link con un solo request, sin tocar
ninguna ruta disallowed.

Lee bgg_data.csv directo, no docs/data/data.json: ese archivo es un
*output* de 02_data_preparation, y 01_data_understanding (recolección
cruda) nunca depende de un output de 02 (integración) — solo al revés.

La Watchlist puede ser grande (hasta ~1000 candidatos del top N de BGG):
collect_bosque_precios.py acepta --limit para no tener que relevar el
precio de todos en una corrida.

Salida: 01_data_understanding/collect_initial_data/bosque_ludico/links.json (primera columna
bgg_id, para integrar fácil el día que exista esa integración).
Siguiente paso: 01_data_understanding/collect_initial_data/bosque_ludico/collect_bosque_precios.py
lee ese archivo y releva el precio actual de cada link.
"""
import csv
import gzip
import json
import re
import sys
import unicodedata
import urllib.request
from pathlib import Path

BGG_DATA_PATH = Path(__file__).resolve().parent.parent / "bgg" / "bgg_data.csv"

SITEMAP_URL = "https://acdn-us.mitiendanube.com/stores/005/798/114/themes/common/sitemap.xml.gz"
USER_AGENT = "boardgame-personal-catalog/1.0 (uso personal; contacto: negocios.mondineta@gmail.com)"

OUTPUT_PATH = Path(__file__).resolve().parent / "links.json"

MATCH_THRESHOLD = 0.8  # fracción de palabras del termino buscado que tienen que aparecer en el slug

# Mismo patrón que BGG_SEARCH_OVERRIDES / BGG_SKIP en bgg/collect_bgg_data.py:
# para ediciones locales o nombres que no matchean bien contra el catálogo
# de la tienda, se fuerza el término de búsqueda o se marca el juego como
# sin link.
BOSQUE_SEARCH_OVERRIDES = {
    # "Nombre del juego": "término a buscar en vez de nombre_en",
}
BOSQUE_SKIP = {
    # juegos que sabemos que la tienda no vende
}


def normalize(s):
    s = (s or "").strip().lower()
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = "".join(c if c.isalnum() else " " for c in s)
    return " ".join(s.split())


def load_watchlist():
    if not BGG_DATA_PATH.exists():
        sys.exit(f"No existe {BGG_DATA_PATH}; corré primero 01_data_understanding/collect_initial_data/bgg/collect_bgg_data.py")
    with BGG_DATA_PATH.open(encoding="utf-8") as f:
        games = list(csv.DictReader(f))
    watchlist = [g for g in games if (g.get("estado") or "").strip() == "Watchlist"]
    if not watchlist:
        sys.exit(f"No encontré juegos con estado Watchlist en {BGG_DATA_PATH}")
    return watchlist


def fetch_product_slugs():
    req = urllib.request.Request(SITEMAP_URL, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req) as resp:
        raw = gzip.decompress(resp.read())
    xml = raw.decode("utf-8", errors="replace")

    slugs = []
    for loc in re.findall(r"<loc>(https://www\.elbosqueludico\.com\.ar/productos/[^<]+)</loc>", xml):
        slug = loc.rstrip("/").rsplit("/", 1)[-1]
        if not slug:
            continue
        words = slug.split("-")
        # Tiendanube le agrega un sufijo random de 4-6 caracteres alfanumericos
        # a los slugs que colisionan (p.ej. "ark-nova-v2ui5"); si el ultimo
        # token tiene un digito, asumimos que es ese sufijo y lo descartamos
        # para no ensuciar el matching por texto.
        if len(words) > 1 and re.fullmatch(r"[a-z0-9]{3,6}", words[-1]) and any(c.isdigit() for c in words[-1]):
            words = words[:-1]
        slugs.append((loc, normalize(" ".join(words))))
    if not slugs:
        sys.exit(f"El sitemap de El Bosque Lúdico no trajo ningún producto; revisá {SITEMAP_URL}")
    return slugs


def containment_score(term_words, slug_norm):
    """Fracción de las palabras del término buscado que aparecen como palabra
    completa en el slug. Más estricto que un ratio de caracteres: evita
    matchear "Codenames" contra "cometas" solo porque compart en letras."""
    slug_words = set(slug_norm.split())
    if not term_words:
        return 0.0
    found = sum(1 for w in term_words if w in slug_words)
    return found / len(term_words)


def best_match(terms, slugs):
    """Prueba cada término candidato (nombre_en, luego nombre) contra todos
    los slugs y devuelve el mejor match. Ante empate, prefiere el slug cuya
    cantidad de palabras está más cerca de la del término (para no preferir
    una expansión/variante mucho más larga sobre el juego base)."""
    best = (None, 0.0)
    for term in terms:
        term_words = [w for w in normalize(term).split() if len(w) >= 3]
        if not term_words:
            continue
        for url, norm_slug in slugs:
            score = containment_score(term_words, norm_slug)
            if score > best[1]:
                best = (url, score)
            elif score == best[1] and score > 0 and best[0]:
                prev_len = len(dict(slugs)[best[0]].split())
                if abs(len(norm_slug.split()) - len(term_words)) < abs(prev_len - len(term_words)):
                    best = (url, score)
        if best[1] >= MATCH_THRESHOLD:
            break
    return best


def main():
    watchlist = load_watchlist()
    slugs = fetch_product_slugs()

    results = []
    for game in watchlist:
        bgg_id = game.get("bgg_id")
        nombre = game.get("nombre")

        if nombre in BOSQUE_SKIP:
            results.append({
                "bgg_id": bgg_id, "nombre": nombre, "bgg_url": game.get("bgg_url"),
                "bosque_url": None, "match_score": None,
            })
            print(f"{nombre}: salteado (BOSQUE_SKIP)")
            continue

        term = BOSQUE_SEARCH_OVERRIDES.get(nombre) or nombre
        url, score = best_match([term], slugs)
        if score < MATCH_THRESHOLD:
            url, score = None, None
            print(f"{nombre}: sin match confiable (buscado: {term!r})")
        else:
            print(f"{nombre}: {url} (score={score:.2f})")

        results.append({
            "bgg_id": bgg_id, "nombre": nombre, "bgg_url": game.get("bgg_url"),
            "bosque_url": url, "match_score": round(score, 2) if score else None,
        })

    OUTPUT_PATH.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    sin_match = sum(1 for r in results if not r["bosque_url"])
    print(f"\n{len(results)} juego(s) en Watchlist, {sin_match} sin link a El Bosque Lúdico.")
    print(f"Guardado en {OUTPUT_PATH}")
    print("Revisá los match_score bajos a mano: si el match está mal, agregalo a "
          "BOSQUE_SEARCH_OVERRIDES o BOSQUE_SKIP y volvé a correr este script.")


if __name__ == "__main__":
    main()
