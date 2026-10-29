"""Verifica los links a Cazagangas ya guardados en
data/01_data_understanding/cazagangas_data.jsonl (bgg_id, link_cazagangas,
status_http, fecha_chequeado): no arma ninguna URL nueva acá (eso lo hace
search_new_game.py --add, ver cazagangas_common.resolver_link), solo le pega
un HEAD real (fallback GET si el servidor no soporta HEAD) a cada link para
guardar/refrescar el código HTTP.

robots.txt de Cazagangas permite crawling general (`User-agent: *` sin
Disallow; solo bloquea a AhrefsBot/SemrushBot, que no somos). No hay
Crawl-delay explícito; se usa 2s entre requests, más corto que el de
El Bosque Lúdico (5s) porque acá es un HEAD liviano, no una página entera.

Uso:
    python3 01_data_understanding/collect_initial_data/cazagangas/check_cazagangas_links.py [--limit N] [--refresh]

--limit N: chequea como máximo N links pendientes (para ir de a tandas).
--refresh: re-chequea también los que ya tienen un resultado guardado (por
default se saltean, para no re-pegarle a links que ya sabemos que andan o no).

[PENDIENTE] Hoy solo confirma que el link existe (código HTTP). En algún
momento esto se amplía a scraper real: precio, stock/disponibilidad y en
qué tienda(s) de Argentina se puede comprar cada juego (Cazagangas agrega
varias tiendas por juego, no es un único vendedor) — ver README.md,
"Pendiente si esto vale la pena".
"""
import argparse
import datetime
import time

from cazagangas_common import CRAWL_DELAY_SECONDS, OUTPUT_PATH, check_status, load_cazagangas_cache, write_cazagangas_cache


def main():
    parser = argparse.ArgumentParser(description="Verifica los links guardados en cazagangas_data.jsonl")
    parser.add_argument("--limit", type=int, default=None, help="chequear como máximo N links pendientes")
    parser.add_argument("--refresh", action="store_true", help="re-chequear también los que ya tienen un resultado guardado")
    args = parser.parse_args()

    entries = load_cazagangas_cache()
    if not entries:
        raise SystemExit(f"{OUTPUT_PATH} está vacío o no existe; agregá juegos con search_new_game.py --add.")

    pendientes = [e for e in entries.values() if args.refresh or not e.get("status_http")]
    if args.limit is not None:
        pendientes = pendientes[: args.limit]
    if not pendientes:
        print("Nada pendiente de chequear (corré con --refresh para re-chequear todo).")
        return

    hoy = datetime.date.today().isoformat()
    for i, entry in enumerate(pendientes):
        status = check_status(entry["link_cazagangas"])
        print(f"[{i + 1}/{len(pendientes)}] bgg_id={entry['bgg_id']}: {entry['link_cazagangas']} -> {status}")
        entry["status_http"], entry["fecha_chequeado"] = status, hoy
        if i < len(pendientes) - 1:
            time.sleep(CRAWL_DELAY_SECONDS)

    write_cazagangas_cache(entries)
    ok = sum(1 for v in entries.values() if v["status_http"] == "200")
    print(f"\nGuardado en {OUTPUT_PATH} ({len(entries)} link(s) en total, {ok} responden 200).")


if __name__ == "__main__":
    main()
