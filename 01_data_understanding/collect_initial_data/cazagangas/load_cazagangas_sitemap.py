"""Carga en data/01_data_understanding/cazagangas_data.jsonl los links a Cazagangas
cruzando el catálogo de BGG contra el sitemap de Cazagangas.

Por qué así: adivinar el slug juego por juego es lento (un pedido de ~2 s por
candidato) y falla con los nombres en español ("The Resistance: Avalon" está como
`la-resistencia-avalon`). Cazagangas publica la lista de todos sus juegos en
`/sitemap-games-N.xml` (~8.500 juegos, ~20 pedidos; su robots.txt lo permite), así que
se baja esa lista una vez y se busca ahí, sin más pedidos.

Qué hace:
  1. Baja los sitemaps de juegos (2 s entre pedidos).
  2. Por cada juego de bgg_data.jsonl, slugifica el nombre principal y cada nombre
     alternativo de BGG (ahí están los españoles) y los busca en el sitemap.
  3. Elige el link con estas reglas:
       - nombre principal exacto: si un solo juego de BGG tiene ese nombre, es suyo; si hay
         varios con el mismo nombre (Dune, Dominion...), va al más votado (`usersrated`);
       - nombre alternativo (español, etc.): solo si ese slug le toca a un solo juego;
       - NUNCA por título corto (lo que va antes de ":"): `/juego/monopoly` le calzaba a
         decenas de variantes (Monopoly: Metallica, Monopoly: Cars 2...).
  4. Guarda las filas nuevas en cazagangas_data.jsonl con `status_http` "200" (que esté
     en el sitemap es la verificación) y `origen` ("sitemap", "sitemap-homonimo-mas-votado" o
     "sitemap-nombre-alterno"). No toca los links que ya tienen 200; sí reemplaza los 404/sin chequear.

Uso:
    python3 01_data_understanding/collect_initial_data/cazagangas/load_cazagangas_sitemap.py [--dry-run]

--dry-run: hace todo menos escribir el archivo (muestra los números).

Después de correrlo hay que regenerar el sitio: `python3 02_data_preparation/integrate_data.py`
y `python3 02_data_preparation/build_catalog.py` (o `./sync_data.sh`).
"""
import argparse
import collections
import datetime
import json
import re
import sys
import time
import urllib.request

from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from refresh_log import write_refresh_log  # noqa: E402
from cazagangas_common import CRAWL_DELAY_SECONDS, ROOT, load_cazagangas_cache, slugify, write_cazagangas_cache

BASE_URL = "https://www.cazagangas.com.ar"
BGG_DATA_PATH = ROOT / "data" / "01_data_understanding" / "bgg_data.jsonl"
# User-Agent genérico: no lleva datos personales (el de cazagangas_common sí lleva un contacto).
USER_AGENT = "boardgame-personal-catalog/1.0 (uso personal)"


def fetch(url):
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read().decode("utf-8")


def sitemap_slugs():
    """Slugs de todas las páginas /juego/<slug> de Cazagangas."""
    index = fetch(f"{BASE_URL}/sitemap.xml")
    archivos = [u for u in re.findall(r"<loc>([^<]+)</loc>", index) if "sitemap-games-" in u]
    slugs = set()
    for i, url in enumerate(archivos):
        slugs.update(re.findall(r"<loc>%s/juego/([^<]+)</loc>" % re.escape(BASE_URL), fetch(url)))
        if i < len(archivos) - 1:
            time.sleep(CRAWL_DELAY_SECONDS)
    print(f"Sitemap: {len(archivos)} archivo(s), {len(slugs)} juegos en Cazagangas.")
    return slugs


def elegir_links(juegos, slugs):
    """{bgg_id: (slug, origen)} aplicando las reglas del docstring."""
    por_slug = collections.defaultdict(set)  # slug -> juegos que lo reclaman con cualquier nombre
    exacto = collections.defaultdict(set)    # slug -> juegos cuyo nombre principal da ese slug
    alternos = collections.defaultdict(list)  # bgg_id -> slugs de sus nombres alternativos
    votos = {}
    for juego in juegos:
        bgg_id = juego["bgg_id"]
        votos[bgg_id] = int(juego.get("usersrated") or 0)
        principal = slugify(juego.get("name"))
        if principal in slugs:
            por_slug[principal].add(bgg_id)
            exacto[principal].add(bgg_id)
        for nombre in juego.get("alternate") or []:
            slug = slugify(nombre)
            if slug in slugs and slug != principal and slug not in alternos[bgg_id]:
                por_slug[slug].add(bgg_id)
                alternos[bgg_id].append(slug)

    elegidos = {}
    for slug, ids in exacto.items():
        if len(ids) == 1:
            elegidos[next(iter(ids))] = (slug, "sitemap")
        else:
            elegidos[max(ids, key=votos.get)] = (slug, "sitemap-homonimo-mas-votado")
    usados = {slug for slug, _ in elegidos.values()}
    for bgg_id, slugs_alt in alternos.items():
        if bgg_id in elegidos:
            continue
        for slug in slugs_alt:
            if len(por_slug[slug]) == 1 and slug not in usados:
                elegidos[bgg_id] = (slug, "sitemap-nombre-alterno")
                usados.add(slug)
                break
    return elegidos


def main():
    parser = argparse.ArgumentParser(description="Carga links a Cazagangas cruzando BGG contra su sitemap")
    parser.add_argument("--dry-run", action="store_true", help="no escribe cazagangas_data.jsonl, solo muestra los números")
    args = parser.parse_args()

    inicio = time.time()
    slugs = sitemap_slugs()
    with BGG_DATA_PATH.open(encoding="utf-8") as f:
        juegos = [json.loads(line) for line in f if line.strip()]
    elegidos = elegir_links(juegos, slugs)

    filas = load_cazagangas_cache()
    hoy = datetime.date.today().isoformat()
    nuevos = reemplazados = respetados = 0
    for bgg_id, (slug, origen) in elegidos.items():
        existente = filas.get(bgg_id)
        if existente and existente.get("status_http") == "200":
            respetados += 1
            continue
        if existente:
            reemplazados += 1
        else:
            nuevos += 1
        filas[bgg_id] = {
            "bgg_id": bgg_id,
            "link_cazagangas": f"{BASE_URL}/juego/{slug}",
            "status_http": "200",
            "fecha_chequeado": hoy,
            "origen": origen,
        }

    por_origen = collections.Counter(origen for _, origen in elegidos.values())
    print(f"Juegos de BGG con página en Cazagangas: {len(elegidos)} {dict(por_origen)}")
    print(f"Nuevos: {nuevos} | reemplazan un 404/sin chequear: {reemplazados} | ya tenían 200 (se respetan): {respetados}")
    ok = sum(1 for fila in filas.values() if fila.get("status_http") == "200")
    if args.dry_run:
        print(f"--dry-run: no se escribió nada (quedarían {len(filas)} filas, {ok} con 200).")
        return
    write_cazagangas_cache(filas)
    write_refresh_log("Cazagangas (sitemap)", "load_cazagangas_sitemap.py", " ".join(sys.argv[1:]), len(juegos), nuevos + reemplazados,
                      nuevos, 0, 2, {"link_cazagangas": nuevos + reemplazados} if nuevos + reemplazados else {}, time.time() - inicio,
                      f"{len(elegidos)} con página en el sitemap; {respetados} ya tenían 200")
    print(f"Guardado: {len(filas)} filas, {ok} con 200.")


if __name__ == "__main__":
    main()
