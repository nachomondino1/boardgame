"""Releva el precio actual de cada juego en links.json pegándole a su ficha
de producto en El Bosque Lúdico (no a /search/, ver resolve_bosque_links.py
para por qué).

Cada ficha de producto trae un atributo data-variants con un JSON embebido
(precio, stock, disponibilidad) — se parsea eso en vez de clases CSS, que
cambian más seguido con el tema de la tienda.

Uso:
    python3 01_data_understanding/bosque_ludico/resolve_bosque_links.py   # primero, si no corrió
    python3 01_data_understanding/bosque_ludico/collect_bosque_precios.py

Salida: 01_data_understanding/bosque_ludico/bosque_data.json
"""
import datetime
import html
import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

USER_AGENT = "boardgame-personal-catalog/1.0 (uso personal; contacto: negocios.mondineta@gmail.com)"
CRAWL_DELAY_SECONDS = 5  # ninguna regla explícita en robots.txt para User-agent: *, mismo criterio conservador que enrich_bgg.py

ROOT = Path(__file__).resolve().parent
LINKS_PATH = ROOT / "links.json"
OUTPUT_PATH = ROOT / "bosque_data.json"


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


def parse_price(page_html, url):
    match = re.search(r'data-variants="([^"]*)"', page_html)
    if not match:
        raise RuntimeError(f"No encontré data-variants en {url}; puede que la tienda haya cambiado el tema.")
    variants = json.loads(html.unescape(match.group(1)))
    if not variants:
        raise RuntimeError(f"data-variants vino vacío en {url}")

    disponibles = [v for v in variants if v.get("available")]
    variant = disponibles[0] if disponibles else variants[0]
    return {
        "precio": variant.get("price_number"),
        "moneda": "ARS",
        "disponible": bool(variant.get("available")),
        "stock": variant.get("stock"),
    }


def main():
    if not LINKS_PATH.exists():
        sys.exit(f"No existe {LINKS_PATH}; corré primero resolve_bosque_links.py")
    links = json.loads(LINKS_PATH.read_text(encoding="utf-8"))

    hoy = datetime.date.today().isoformat()
    results = []
    con_link = [l for l in links if l.get("bosque_url")]

    for i, link in enumerate(con_link):
        nombre, url = link["nombre"], link["bosque_url"]
        print(f"[{i + 1}/{len(con_link)}] {nombre}...")
        try:
            page_html = http_get(url)
            precio = parse_price(page_html, url)
        except Exception as e:
            print(f"  error: {e}", file=sys.stderr)
            results.append({"nombre": nombre, "bosque_url": url, "fecha_relevado": hoy, "error": str(e)})
        else:
            results.append({"nombre": nombre, "bosque_url": url, "fecha_relevado": hoy, **precio})
            print(f"  ${precio['precio']} disponible={precio['disponible']}")

        if i < len(con_link) - 1:
            time.sleep(CRAWL_DELAY_SECONDS)

    OUTPUT_PATH.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nGuardado en {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
