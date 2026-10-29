"""Código compartido por check_cazagangas_links.py y
refresh_bgg_data.py (collect_initial_data/bgg/): slug best-effort a partir
del nombre del juego + verificación real por HTTP.

El slug nunca se guarda a ciegas: `slugify()` arma una URL candidata,
pero solo vale la pena guardarla en cazagangas_data.jsonl si `check_status()`
le devuelve 200 (adivinar, pero nunca sin verificar con un HEAD real antes
de guardar nada).

cazagangas_data.jsonl: una fila por juego con link a Cazagangas — `bgg_id`,
`link_cazagangas`, `status_http`, `fecha_chequeado`. El link vive solo acá.
"""
import datetime
import json
import re
import time
import unicodedata
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUTPUT_PATH = ROOT / "data" / "01_data_understanding" / "cazagangas_data.jsonl"

USER_AGENT = "boardgame-personal-catalog/1.0 (uso personal; contacto: negocios.mondineta@gmail.com)"
CRAWL_DELAY_SECONDS = 2


def slugify(nombre):
    """Mismo algoritmo que tenía cazagangasUrl() en docs/js/shared.js
    cuando el frontend todavía armaba el link solo: sin tildes, en
    minúscula, todo lo que no sea [a-z0-9] se vuelve "-"."""
    s = unicodedata.normalize("NFD", (nombre or "").lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s


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


def load_cazagangas_cache():
    """bgg_id -> fila de cazagangas_data.jsonl."""
    if not OUTPUT_PATH.exists():
        return {}
    with OUTPUT_PATH.open(encoding="utf-8") as f:
        rows = [json.loads(line) for line in f if line.strip()]
    return {row["bgg_id"]: row for row in rows}


def write_cazagangas_cache(by_bgg_id):
    with OUTPUT_PATH.open("w", encoding="utf-8") as f:
        for row in by_bgg_id.values():
            f.write(json.dumps(row, ensure_ascii=False))
            f.write("\n")


def resolver_link(nombres, bgg_id, max_intentos=12):
    """Prueba un slug best-effort por cada nombre de `nombres` (el principal
    primero, después los alternativos de BGG) y, de cada uno, también el
    título sin subtítulo (lo que va antes de ":" o "–"): "The Crew" está en
    Cazagangas como `la-tripulacion`, que sale de "La Tripulación: En busca
    del noveno planeta". Verifica cada slug con un HEAD real y devuelve
    (url, status) del primero que da 200 — y lo guarda en cazagangas_data.jsonl.
    Si ninguno da 200, no guarda nada y devuelve el resultado del primer intento."""
    candidatos = []
    for nombre in nombres:
        candidatos += [nombre, re.split(r"\s*[:–—]\s", nombre or "", maxsplit=1)[0]]
    primero, vistos = None, set()
    for nombre in candidatos:
        slug = slugify(nombre)
        if not slug or slug in vistos:
            continue
        vistos.add(slug)
        if len(vistos) > max_intentos:
            break
        url = f"https://www.cazagangas.com.ar/juego/{slug}"
        status = check_status(url)
        primero = primero or (url, status)
        if status == "200":
            existing = load_cazagangas_cache()
            existing[bgg_id] = {
                "bgg_id": bgg_id,
                "link_cazagangas": url,
                "status_http": status,
                "fecha_chequeado": datetime.date.today().isoformat(),
            }
            write_cazagangas_cache(existing)
            return url, status
        time.sleep(CRAWL_DELAY_SECONDS)
    return primero or (None, "error")
