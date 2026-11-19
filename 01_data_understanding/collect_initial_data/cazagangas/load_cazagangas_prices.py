"""Trae el precio más barato en Argentina de cada juego con link a Cazagangas.

De dónde sale: la ficha de cada juego (`/juego/<slug>`) dice "Disponible en N tiendas entre $A – $B":
son precios de TIENDAS, o sea juegos nuevos. El JSON-LD de la misma ficha (`AggregateOffer`) NO sirve: mezcla
las publicaciones de la Feria (usados de particulares) y su `lowPrice` puede ser el de un usado. El sitemap y
los feeds RSS no traen precios, así que hace falta un pedido por juego (~3,5 s cada uno con la pausa: ~4 horas
para ~4.600 juegos; por eso se corre de a tandas y retoma donde quedó).

Qué guarda, en las mismas filas de data/01_data_understanding/cazagangas_data.jsonl:
  - precio_ars: el precio más barato en tiendas (nuevo), o null si ninguna tienda lo tiene
  - precio_ars_max: el más caro en tiendas
  - tiendas: cantidad de tiendas con el juego
  - fecha_precio: día en que se miró (los precios cambian: ver --refresh)

Empieza por los juegos mejor rankeados en BGG (los que más se miran en la web).

Uso:
    python3 01_data_understanding/collect_initial_data/cazagangas/load_cazagangas_prices.py [--limit N] [--refresh DIAS]

--limit N: mira como máximo N juegos en esta corrida (para ir de a tandas).
--refresh DIAS: vuelve a mirar los que tienen un precio de hace DIAS días o más (por default,
solo los que nunca se miraron).

Después hay que regenerar el sitio: `python3 02_data_preparation/integrate_data.py` y
`python3 02_data_preparation/build_catalog.py`.
"""
import argparse
import datetime
import json
import re
import time
import urllib.error
import urllib.request

from cazagangas_common import CRAWL_DELAY_SECONDS, ROOT, load_cazagangas_cache, write_cazagangas_cache

BGG_DATA_PATH = ROOT / "data" / "01_data_understanding" / "bgg_data.jsonl"
# User-Agent genérico: no lleva datos personales (el de cazagangas_common sí lleva un contacto).
USER_AGENT = "boardgame-personal-catalog/1.0 (uso personal)"
GUARDAR_CADA = 25  # juegos: así una corrida cortada no pierde lo ya mirado

def fetch(url, reintentos=3):
    espera = CRAWL_DELAY_SECONDS
    for intento in range(1, reintentos + 1):
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return response.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as e:
            if e.code in (429, 503) and intento < reintentos:
                time.sleep(espera)
                espera *= 2
                continue
            return None  # 404 u otro: la ficha ya no existe
        except Exception:
            if intento < reintentos:
                time.sleep(espera)
                espera *= 2
                continue
            return None
    return None


TIENDAS_RE = re.compile(r'available-stores-tag">\s*<div>Disponible en (\d+) tiendas?</div>')
RANGO_RE = re.compile(r'available-price-range-tag">\s*<div>\$([\d.]+)</div>')


def parse_precio(html):
    """(precio_ars, precio_ars_max, tiendas) de las TIENDAS de la ficha (juegos nuevos), o (None, None, 0)
    si ninguna tienda lo tiene.

    No se usa el JSON-LD (`AggregateOffer`): mezcla las publicaciones de la Feria (juegos usados de
    particulares) con las de las tiendas, así que `lowPrice` puede ser el de un usado (Wingspan: $100.000
    usado contra $120.950 en tienda). El bloque "Disponible en N tiendas entre $A – $B" del HTML es solo
    de tiendas."""
    tiendas = TIENDAS_RE.search(html)
    if not tiendas:
        return None, None, 0
    # Los precios son los del rango que sigue al "Disponible en N tiendas". La Feria tiene su propio bloque
    # ("N publicaciones en la Feria", con otro rango de precios, que puede ir antes o después): se corta ahí.
    resto = html[tiendas.end():]
    corte = resto.find("available-users-tag")
    if corte >= 0:
        resto = resto[:corte]
    precios = [int(p.replace(".", "")) for p in RANGO_RE.findall(resto[:1500])]
    if not precios:
        return None, None, 0
    return min(precios), max(precios), int(tiendas.group(1))


def ranking_por_juego():
    ranking = {}
    with BGG_DATA_PATH.open(encoding="utf-8") as f:
        for line in f:
            juego = json.loads(line)
            try:
                ranking[juego["bgg_id"]] = int(juego.get("Board Game Rank"))
            except (TypeError, ValueError):
                ranking[juego["bgg_id"]] = 10**9  # sin ranking: al final
    return ranking


def pendiente(fila, refresh_dias, hoy):
    if fila.get("status_http") != "200":
        return False
    if not fila.get("fecha_precio"):
        return True
    if refresh_dias is None:
        return False
    return (hoy - datetime.date.fromisoformat(fila["fecha_precio"])).days >= refresh_dias


def main():
    parser = argparse.ArgumentParser(description="Trae el precio más barato de Cazagangas para cada juego con link")
    parser.add_argument("--limit", type=int, default=None, help="mirar como máximo N juegos en esta corrida")
    parser.add_argument("--refresh", type=int, default=None, metavar="DIAS", help="volver a mirar los precios de hace DIAS días o más")
    args = parser.parse_args()

    filas = load_cazagangas_cache()
    hoy = datetime.date.today()
    ranking = ranking_por_juego()
    pendientes = sorted((f for f in filas.values() if pendiente(f, args.refresh, hoy)), key=lambda f: ranking.get(f["bgg_id"], 10**9))
    total = len(pendientes)
    if args.limit is not None:
        pendientes = pendientes[: args.limit]
    if not pendientes:
        print("Nada pendiente (--refresh DIAS para volver a mirar precios viejos).")
        return
    print(f"{total} juego(s) pendientes; esta corrida mira {len(pendientes)}.")

    con_precio = 0
    for i, fila in enumerate(pendientes, 1):
        html = fetch(fila["link_cazagangas"])
        if html is None:
            print(f"[{i}/{len(pendientes)}] bgg_id={fila['bgg_id']}: sin respuesta, se reintenta en la próxima corrida")
        else:
            precio, maximo, tiendas = parse_precio(html)
            fila.update({"precio_ars": precio, "precio_ars_max": maximo, "tiendas": tiendas, "fecha_precio": hoy.isoformat()})
            con_precio += precio is not None
            print(f"[{i}/{len(pendientes)}] bgg_id={fila['bgg_id']}: {'$' + format(precio, ',').replace(',', '.') + f' ({tiendas} tiendas)' if precio is not None else 'sin ofertas'}")
        if i % GUARDAR_CADA == 0:
            write_cazagangas_cache(filas)
        if i < len(pendientes):
            time.sleep(CRAWL_DELAY_SECONDS)

    write_cazagangas_cache(filas)
    print(f"\nListo: {con_precio} de {len(pendientes)} con precio. Guardado en cazagangas_data.jsonl.")


if __name__ == "__main__":
    main()
