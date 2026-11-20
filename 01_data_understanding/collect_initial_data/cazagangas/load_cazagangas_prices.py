"""Trae el precio más barato en Argentina de cada juego con link a Cazagangas.

De dónde sale: la ficha de cada juego (`/juego/<slug>`) dice "Disponible en N tiendas entre $A – $B":
son precios de TIENDAS, o sea juegos nuevos. El JSON-LD de la misma ficha (`AggregateOffer`) NO sirve: mezcla
las publicaciones de la Feria (usados de particulares) y su `lowPrice` puede ser el de un usado. El sitemap y
los feeds RSS no traen precios, así que hace falta un pedido por juego (~3,5 s cada uno con la pausa: ~4 horas
para ~4.600 juegos; por eso se corre de a tandas y retoma donde quedó).

Qué guarda, en las mismas filas de data/01_data_understanding/cazagangas_data.jsonl:
  - precio_ars: el precio más barato en tiendas (nuevo); null si nunca hubo stock. Si el juego se queda sin stock
    se CONSERVA el último precio visto (junto con tiendas = 0): el sitio lo muestra hasta 6 meses como "últ."
  - precio_ars_max: el más caro en tiendas
  - tiendas: cantidad de tiendas con el juego hoy (0 = sin stock)
  - fecha_con_stock: último día en que se vio con stock (cuándo se vio ese precio)
  - fecha_precio: día en que se miró (los precios cambian: ver --refresh)

Empieza por los juegos mejor rankeados en BGG (los que más se miran en la web).

Uso:
    python3 01_data_understanding/collect_initial_data/cazagangas/load_cazagangas_prices.py [--rapido] [--limit N] [--refresh DIAS]

--rapido: para la actualización mensual (~30 min en vez de ~4,5 h). Recorre el listado `/juegos?disponibilidad=on`
("Ver sólo en stock", ~210 páginas de 10 juegos con "desde $X en N tiendas"): los que coinciden con lo guardado se
confirman sin visitar su ficha, los que no aparecen quedan "sin stock", y solo se mira la ficha de los que cambiaron
o de los dudosos (tarjetas sin "N tiendas": ese precio es de la Feria). La ficha sigue siendo la fuente confiable: el
precio del listado no siempre coincide (Toy Battle $14.400 en el listado, $71.900 en la ficha, verificado 2026-11-20).
Si alguna página del listado no responde, no se marca sin stock a nadie por no aparecer.

--limit N: mira como máximo N juegos en esta corrida (para ir de a tandas).
--refresh DIAS: vuelve a mirar los que tienen un precio de hace DIAS días o más (por default,
solo los que nunca se miraron).

Después hay que regenerar el sitio: `python3 02_data_preparation/integrate_data.py` y
`python3 02_data_preparation/build_catalog.py`.
"""
import argparse
import sys
from pathlib import Path
import datetime
import json
import re
import time
import urllib.error
import urllib.request

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from logs_actualizacion_data import write_logs_actualizacion_data  # noqa: E402
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


LISTADO_URL = "https://www.cazagangas.com.ar/juegos{pagina}?disponibilidad=on"  # "Ver sólo en stock": 10 juegos por página
PAGINAS_RE = re.compile(r'pagination-link hide-mobile"[^>]*>\s*<div>(\d+)</div>')
TARJETA_SLUG_RE = re.compile(r'href="/juego/([a-z0-9-]+)"')
TARJETA_PRECIO_RE = re.compile(r'game-price">\$([\d.]+)<')
TARJETA_TIENDAS_RE = re.compile(r'seller-count">(\d+) tienda')


def parse_listado(html):
    """({slug: (precio, tiendas)}, {slug sin cantidad de tiendas}, ultima_pagina) de una página del listado.

    Una tarjeta con "N tiendas" muestra el precio "desde" de TIENDAS. Una sin esa cantidad muestra un precio de la
    Feria (usados): no se usa, el juego queda como dudoso para mirar su ficha."""
    trozos = html.split("game-prices-options")
    con_tiendas, dudosos = {}, set()
    for anterior, cuerpo in zip(trozos, trozos[1:]):
        slugs = TARJETA_SLUG_RE.findall(anterior)
        if not slugs:
            continue
        precio, tiendas = TARJETA_PRECIO_RE.search(cuerpo[:1500]), TARJETA_TIENDAS_RE.search(cuerpo[:1500])
        if precio and tiendas:
            con_tiendas[slugs[-1]] = (int(precio.group(1).replace(".", "")), int(tiendas.group(1)))
        else:
            dudosos.add(slugs[-1])
    paginas = [int(p) for p in PAGINAS_RE.findall(html)]
    return con_tiendas, dudosos, max(paginas) if paginas else 1


def recorrer_listado():
    """Recorre todo el listado "sólo en stock". Devuelve (con_tiendas, dudosos, completo): `completo` es False si
    alguna página no respondió (entonces no se puede afirmar que un juego que no aparece no tiene stock)."""
    con_tiendas, dudosos, completo = {}, set(), True
    pagina, ultima = 1, 1
    while pagina <= ultima:
        html = fetch(LISTADO_URL.format(pagina="" if pagina == 1 else f"/{pagina}"))
        if html is None:
            completo = False
            print(f"  listado, página {pagina}: sin respuesta")
        else:
            ct, du, ultima_pag = parse_listado(html)
            con_tiendas.update(ct)
            dudosos |= du
            ultima = max(ultima, ultima_pag)
        if pagina % 20 == 0 or pagina == ultima:
            print(f"  listado: {pagina}/{ultima} páginas, {len(con_tiendas)} juegos con precio de tiendas")
        pagina += 1
        if pagina <= ultima:
            time.sleep(CRAWL_DELAY_SECONDS)
    return con_tiendas, dudosos, completo


def rapido(filas, hoy):
    """Pasada rápida: el listado dice qué juegos tienen stock y su precio "desde"; solo se visita la ficha de los
    que cambiaron respecto de lo guardado o de los dudosos (el precio del listado no siempre coincide con el de la
    ficha: Toy Battle $14.400 en el listado contra $71.900 en la ficha). Devuelve contadores para el log."""
    con_tiendas, dudosos, completo = recorrer_listado()
    hoy_txt = hoy.isoformat()
    stats = {"confirmados": 0, "fichas": 0, "sin_stock": 0, "perdieron_stock": 0, "sin_respuesta": 0, "completo": completo, "cols": {}}
    a_visitar = []
    for fila in filas.values():
        if fila.get("status_http") != "200":
            continue
        slug = fila["link_cazagangas"].rstrip("/").rsplit("/", 1)[-1]
        if slug in con_tiendas and (fila.get("precio_ars"), fila.get("tiendas")) == con_tiendas[slug]:
            fila["fecha_precio"] = hoy_txt  # el listado confirma lo ya guardado
            stats["confirmados"] += 1
        elif slug in con_tiendas or slug in dudosos:
            a_visitar.append(fila)
        elif completo:  # no está en el listado "sólo en stock": ninguna tienda lo tiene
            if fila.get("tiendas"):
                stats["cols"]["tiendas"] = stats["cols"].get("tiendas", 0) + 1
                stats["perdieron_stock"] += 1
            aplicar_precio(fila, None, None, 0, hoy_txt)
            stats["sin_stock"] += 1
        else:
            a_visitar.append(fila)  # listado incompleto: no se da por sin stock, se mira su ficha
    print(f"Listado: {stats['confirmados']} confirmados, {stats['sin_stock']} sin stock; {len(a_visitar)} fichas para verificar.")
    for i, fila in enumerate(a_visitar, 1):
        html = fetch(fila["link_cazagangas"])
        if html is None:
            stats["sin_respuesta"] += 1
            print(f"[{i}/{len(a_visitar)}] bgg_id={fila['bgg_id']}: sin respuesta, se reintenta en la próxima corrida")
        else:
            precio, maximo, tiendas = parse_precio(html)
            for c, v in (("precio_ars", precio), ("precio_ars_max", maximo), ("tiendas", tiendas)):
                if v is not None and fila.get(c) != v:
                    stats["cols"][c] = stats["cols"].get(c, 0) + 1
            if precio is None and fila.get("tiendas"):
                stats["perdieron_stock"] += 1
            aplicar_precio(fila, precio, maximo, tiendas, hoy_txt)
            stats["fichas"] += 1
            print(f"[{i}/{len(a_visitar)}] bgg_id={fila['bgg_id']}: {'$' + format(precio, ',').replace(',', '.') + f' ({tiendas} tiendas)' if precio is not None else 'sin ofertas'}")
        if i % GUARDAR_CADA == 0:
            write_cazagangas_cache(filas)
        if i < len(a_visitar):
            time.sleep(CRAWL_DELAY_SECONDS)
    return stats


def aplicar_precio(fila, precio, maximo, tiendas, hoy_txt):
    """Guarda lo que se vio hoy en la fila. Si hay stock, el precio y `fecha_con_stock` (último día con stock) son
    los de hoy. Si no hay (precio None), se CONSERVA el último precio visto y su fecha: integrate_data.py lo sigue
    mostrando hasta 6 meses (marcado como "últ."), en vez de que el juego pierda el precio apenas se agota."""
    if precio is not None:
        fila.update({"precio_ars": precio, "precio_ars_max": maximo, "tiendas": tiendas, "fecha_con_stock": hoy_txt})
    else:
        if fila.get("precio_ars") is not None and not fila.get("fecha_con_stock"):
            fila["fecha_con_stock"] = fila.get("fecha_precio")  # filas viejas: el último chequeo con precio
        fila["tiendas"] = 0
    fila["fecha_precio"] = hoy_txt


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
    parser.add_argument("--rapido", action="store_true", help="pasada rápida (~30 min): recorre el listado de juegos en stock y solo mira la ficha de los que cambiaron")
    parser.add_argument("--motivo", default="", help="por qué corrés esto (columna motivo de logs_actualizacion_data.csv)")
    parser.add_argument("--nota", default="", help="observación para logs_actualizacion_data.csv (por qué se corre)")
    args = parser.parse_args()

    filas = load_cazagangas_cache()
    hoy = datetime.date.today()
    if args.rapido:
        inicio = time.time()
        s = rapido(filas, hoy)
        write_cazagangas_cache(filas)
        total = sum(f.get("status_http") == "200" for f in filas.values())
        tocados = s["confirmados"] + s["sin_stock"] + s["fichas"]
        write_logs_actualizacion_data("Cazagangas", "listado de juegos en stock + ficha de los que cambiaron", total, tocados, time.time() - inicio,
                          f"{s['confirmados']} confirmados por el listado, {s['fichas']} fichas verificadas, {s['sin_stock']} sin stock ({s['perdieron_stock']} lo perdieron hoy, conservan su último precio); "
                          f"el precio cambió en {s['cols'].get('precio_ars', 0)}; {s['sin_respuesta']} sin respuesta (se reintentan)",
                          motivo=args.motivo, observacion=args.nota + ("" if s["completo"] else " Listado incompleto: no se marcó sin stock a los que no aparecieron."))
        print(f"\nListo (rápido): {tocados} de {total} juegos al día. Guardado en cazagangas_data.jsonl.")
        return
    ranking = ranking_por_juego()
    pendientes = sorted((f for f in filas.values() if pendiente(f, args.refresh, hoy)), key=lambda f: ranking.get(f["bgg_id"], 10**9))
    total = len(pendientes)
    if args.limit is not None:
        pendientes = pendientes[: args.limit]
    if not pendientes:
        print("Nada pendiente (--refresh DIAS para volver a mirar precios viejos).")
        return
    print(f"{total} juego(s) pendientes; esta corrida mira {len(pendientes)}.")

    con_precio = sin_respuesta = cambiaron = 0
    inicio = time.time()
    cols = {}
    for i, fila in enumerate(pendientes, 1):
        html = fetch(fila["link_cazagangas"])
        if html is None:
            sin_respuesta += 1
            print(f"[{i}/{len(pendientes)}] bgg_id={fila['bgg_id']}: sin respuesta, se reintenta en la próxima corrida")
        else:
            precio, maximo, tiendas = parse_precio(html)
            nuevo = {"precio_ars": precio, "precio_ars_max": maximo, "tiendas": tiendas, "fecha_precio": hoy.isoformat()}
            dist = [c for c in ("precio_ars", "precio_ars_max", "tiendas") if nuevo[c] is not None and fila.get(c) != nuevo[c]]
            cambiaron += bool(dist)
            for c in dist:
                cols[c] = cols.get(c, 0) + 1
            aplicar_precio(fila, precio, maximo, tiendas, hoy.isoformat())
            con_precio += precio is not None
            print(f"[{i}/{len(pendientes)}] bgg_id={fila['bgg_id']}: {'$' + format(precio, ',').replace(',', '.') + f' ({tiendas} tiendas)' if precio is not None else 'sin ofertas'}")
        if i % GUARDAR_CADA == 0:
            write_cazagangas_cache(filas)
        if i < len(pendientes):
            time.sleep(CRAWL_DELAY_SECONDS)

    write_cazagangas_cache(filas)
    visitados = len(pendientes) - sin_respuesta
    write_logs_actualizacion_data("Cazagangas", "scraping del precio en la página de cada juego",
                      sum(f.get("status_http") == "200" for f in filas.values()), visitados, time.time() - inicio,
                      f"{con_precio} de {visitados} con precio; el precio cambió en {cols.get('precio_ars', 0)}; {sin_respuesta} sin respuesta (se reintentan)",
                      motivo=args.motivo, observacion=args.nota)
    print(f"\nListo: {con_precio} de {len(pendientes)} con precio. Guardado en cazagangas_data.jsonl.")


if __name__ == "__main__":
    main()
