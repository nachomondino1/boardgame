"""Verifica el link a Cazagangas de cada juego de
data/01_data_understanding/universo_juegos.jsonl que ya tenga uno cargado:
no arma ninguna URL nueva acá (eso lo hace search_new_game.py --add, al
agregar un juego — ver cazagangas_common.resolver_link), solo le pega un
HEAD real (fallback GET si el servidor no soporta HEAD) a lo que ya está
cargado, para guardar/refrescar el código HTTP.

robots.txt de Cazagangas permite crawling general (`User-agent: *` sin
Disallow; solo bloquea a AhrefsBot/SemrushBot, que no somos). No hay
Crawl-delay explícito; se usa 2s entre requests, más corto que el de
El Bosque Lúdico (5s) porque acá es un HEAD liviano, no una página entera.

Alcance: todo universo_juegos.jsonl con `link_cazagangas` no vacío — no
filtra por estado (ese campo ya ni vive en el mismo archivo, ver
mis_datos.jsonl). Si un juego no tiene link cargado todavía, no hay nada
que chequear para él, no es un error.

Uso:
    python3 01_data_understanding/collect_initial_data/cazagangas/check_cazagangas_links.py [--limit N] [--refresh]

--limit N: chequea como máximo N juegos pendientes (para ir de a tandas, el
catálogo puede ser grande). --refresh: re-chequea también los que ya
tienen un resultado guardado (por default se saltean, para no re-pegarle a
links que ya sabemos que andan o no).

Salida: data/01_data_understanding/cazagangas_data.jsonl (bgg_id primera
columna; integrate_data.py lo matchea por nombre, igual que grupos.json).
No repite `link_cazagangas` acá — esa URL vive en una sola parte,
universo_juegos.jsonl.

[PENDIENTE] Hoy solo confirma que el link existe (código HTTP). En algún
momento esto se amplía a scraper real: precio, stock/disponibilidad y en
qué tienda(s) de Argentina se puede comprar cada juego (Cazagangas agrega
varias tiendas por juego, no es un único vendedor) — ver README.md,
"Pendiente si esto vale la pena".
"""
import argparse
import datetime
import json
import time

from cazagangas_common import UNIVERSO_PATH, OUTPUT_PATH, CRAWL_DELAY_SECONDS, check_status, load_cazagangas_cache


def load_candidatos():
    if not UNIVERSO_PATH.exists():
        raise SystemExit(f"No existe {UNIVERSO_PATH}; corré primero initialize_bgg_data.py")
    with UNIVERSO_PATH.open(encoding="utf-8") as f:
        juegos = [json.loads(line) for line in f if line.strip()]
    candidatos = [g for g in juegos if (g.get("link_cazagangas") or "").strip()]
    if not candidatos:
        raise SystemExit(f"Ningún juego en {UNIVERSO_PATH} tiene link_cazagangas cargado todavía.")
    return candidatos


def main():
    parser = argparse.ArgumentParser(description="Verifica los links a Cazagangas cargados en universo_juegos.jsonl")
    parser.add_argument("--limit", type=int, default=None,
                         help="chequear como máximo N juegos pendientes")
    parser.add_argument("--refresh", action="store_true",
                         help="re-chequear también los que ya tienen un resultado guardado")
    args = parser.parse_args()

    candidatos = load_candidatos()
    existing = load_cazagangas_cache()

    pendientes = candidatos if args.refresh else [g for g in candidatos if g["nombre"] not in existing]
    if args.limit is not None:
        pendientes = pendientes[: args.limit]
    if not pendientes:
        print("Nada pendiente de chequear (corré con --refresh para re-chequear todo).")
        return

    hoy = datetime.date.today().isoformat()
    for i, game in enumerate(pendientes):
        nombre = game["nombre"]
        url = game["link_cazagangas"]
        status = check_status(url)
        print(f"[{i + 1}/{len(pendientes)}] {nombre}: {url} -> {status}")

        existing[nombre] = {
            "bgg_id": game.get("bgg_id"),
            "nombre": nombre,
            "status_http": status,
            "fecha_chequeado": hoy,
        }

        if i < len(pendientes) - 1:
            time.sleep(CRAWL_DELAY_SECONDS)

    OUTPUT_PATH.write_text(
        "\n".join(json.dumps(v, ensure_ascii=False) for v in existing.values()) + "\n",
        encoding="utf-8",
    )
    ok = sum(1 for v in existing.values() if v["status_http"] == "200")
    print(f"\nGuardado en {OUTPUT_PATH} ({len(existing)} juego(s) en total, {ok} con link que responde 200).")


if __name__ == "__main__":
    main()
