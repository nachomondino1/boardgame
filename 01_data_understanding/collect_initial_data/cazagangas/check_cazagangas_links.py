"""Chequea si el link a Cazagangas de cada juego de la Watchlist existe de
verdad: el frontend (docs/js/shared.js, antes de esto) armaba el link a
partir del nombre del juego (slug best-effort) sin saber si esa página
existe en la tienda. Esto resuelve esa duda una sola vez acá, en vez de que
el navegador de cada visita tenga que adivinar.

Arma la misma URL que armaba el frontend (`https://www.cazagangas.com.ar/
juego/<slug>`, slug = nombre normalizado: sin tildes, en minúscula, todo lo
que no sea [a-z0-9] se vuelve "-") y le pega un HEAD (fallback GET si el
servidor no soporta HEAD) para guardar el código HTTP real.

robots.txt de Cazagangas permite crawling general (`User-agent: *` sin
Disallow; solo bloquea a AhrefsBot/SemrushBot, que no somos). No hay
Crawl-delay explícito; se usa 2s entre requests, más corto que el de
El Bosque Lúdico (5s) porque acá es un HEAD liviano, no una página entera.

Alcance: juegos en Watchlist o Want to buy (lo único que linkea a
Cazagangas hoy es ¿Cuál comprar?, ver docs/comprar.html) — ampliar el
alcance si en algún momento el link se muestra en otra página.

Uso:
    python3 01_data_understanding/collect_initial_data/cazagangas/check_cazagangas_links.py [--limit N] [--refresh]

--limit N: chequea como máximo N juegos pendientes (para ir de a tandas, la
Watchlist puede ser grande). --refresh: re-chequea también los que ya
tienen un resultado guardado (por default se saltean, para no re-pegarle a
links que ya sabemos que andan o no).

Alcance de los candidatos: sale de data/01_data_understanding/mis_datos.jsonl
(estado/nombre son columnas tuyas, no de BGG — ver DATA_PLAYBOOK.md, "Las
columnas que no vienen de BGG viven en su propio archivo").

Salida: data/01_data_understanding/cazagangas_data.jsonl (bgg_id primera
columna; integrate_data.py lo matchea por nombre, igual que grupos.json).

[PENDIENTE] Hoy solo confirma que el link existe (código HTTP). En algún
momento esto se amplía a scraper real: precio, stock/disponibilidad y en
qué tienda(s) de Argentina se puede comprar cada juego (Cazagangas agrega
varias tiendas por juego, no es un único vendedor) — ver README.md,
"Pendiente si esto vale la pena".
"""
import argparse
import datetime
import json
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
MIS_DATOS_PATH = ROOT / "data" / "01_data_understanding" / "mis_datos.jsonl"
OUTPUT_PATH = ROOT / "data" / "01_data_understanding" / "cazagangas_data.jsonl"

USER_AGENT = "boardgame-personal-catalog/1.0 (uso personal; contacto: negocios.mondineta@gmail.com)"
CRAWL_DELAY_SECONDS = 2
ESTADOS_RELEVANTES = {"Watchlist", "Want to buy"}


def slugify(nombre):
    """Mismo algoritmo que cazagangasUrl() en docs/js/shared.js — si se
    toca uno, tocar el otro."""
    s = unicodedata.normalize("NFD", (nombre or "").lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s


def load_candidatos():
    if not MIS_DATOS_PATH.exists():
        sys.exit(f"No existe {MIS_DATOS_PATH}; corré primero collect_bgg_data.py")
    with MIS_DATOS_PATH.open(encoding="utf-8") as f:
        games = [json.loads(line) for line in f if line.strip()]
    candidatos = [g for g in games if (g.get("estado") or "").strip() in ESTADOS_RELEVANTES]
    if not candidatos:
        sys.exit(f"No encontré juegos en {sorted(ESTADOS_RELEVANTES)} en {MIS_DATOS_PATH}")
    return candidatos


def check_status(url, retries=3):
    """HEAD primero (liviano); si el servidor no lo soporta (405/501),
    reintenta con GET. Devuelve el código HTTP como string, o "error" si la
    request no llegó a completarse (timeout, DNS, etc. — no confundir con
    un 404 real, que sí es una respuesta válida: el juego no está)."""
    for method in ("HEAD", "GET"):
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT}, method=method)
        delay = CRAWL_DELAY_SECONDS
        for attempt in range(1, retries + 1):
            try:
                with urllib.request.urlopen(req, timeout=15) as resp:
                    return str(resp.status)
            except urllib.error.HTTPError as e:
                if e.code in (405, 501) and method == "HEAD":
                    break  # probar GET
                if e.code in (429, 503) and attempt < retries:
                    time.sleep(delay)
                    delay *= 2
                    continue
                return str(e.code)
            except Exception:
                if attempt < retries:
                    time.sleep(delay)
                    delay *= 2
                    continue
                return "error"
    return "error"


def main():
    parser = argparse.ArgumentParser(description="Chequea si el link a Cazagangas de cada juego de la Watchlist existe")
    parser.add_argument("--limit", type=int, default=None,
                         help="chequear como máximo N juegos pendientes")
    parser.add_argument("--refresh", action="store_true",
                         help="re-chequear también los que ya tienen un resultado guardado")
    args = parser.parse_args()

    candidatos = load_candidatos()

    existing = {}
    if OUTPUT_PATH.exists():
        with OUTPUT_PATH.open(encoding="utf-8") as f:
            existing = {json.loads(line)["nombre"]: json.loads(line) for line in f if line.strip()}

    pendientes = candidatos if args.refresh else [g for g in candidatos if g["nombre"] not in existing]
    if args.limit is not None:
        pendientes = pendientes[: args.limit]
    if not pendientes:
        print("Nada pendiente de chequear (corré con --refresh para re-chequear todo).")
        return

    hoy = datetime.date.today().isoformat()
    for i, game in enumerate(pendientes):
        nombre = game["nombre"]
        slug = slugify(nombre)
        url = f"https://www.cazagangas.com.ar/juego/{slug}" if slug else None
        if url is None:
            status = "error"
        else:
            status = check_status(url)
        print(f"[{i + 1}/{len(pendientes)}] {nombre}: {url} -> {status}")

        existing[nombre] = {
            "bgg_id": game.get("bgg_id"),
            "nombre": nombre,
            "link_cazagangas": url,
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
