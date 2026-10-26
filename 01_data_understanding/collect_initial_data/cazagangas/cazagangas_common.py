"""Código compartido por check_cazagangas_links.py y
search_new_game.py (collect_initial_data/bgg/): slug best-effort a partir
del nombre del juego + verificación real por HTTP.

El slug nunca se guarda a ciegas: `slugify()` arma una URL candidata,
pero solo vale la pena cargarla en universo_juegos.jsonl si `check_status()`
le devuelve 200 — si no, se deja `link_cazagangas` vacío para cargar a
mano (la decisión de "nunca adivinar" se cambió a "adivinar, pero nunca
sin verificar con un HEAD real antes de guardar nada").
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
UNIVERSO_PATH = ROOT / "data" / "01_data_understanding" / "universo_juegos.jsonl"
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
    if not OUTPUT_PATH.exists():
        return {}
    with OUTPUT_PATH.open(encoding="utf-8") as f:
        rows = [json.loads(line) for line in f if line.strip()]
    return {row["nombre"]: row for row in rows}


def upsert_cazagangas_cache(entries_by_nombre):
    """Mergea {nombre: {bgg_id, status_http, fecha_chequeado}} sobre lo que
    ya está en cazagangas_data.jsonl, sin perder lo que ya había (igual
    patrón que upsert_bgg_cache en bgg_common.py)."""
    existing = load_cazagangas_cache()
    existing.update(entries_by_nombre)
    with OUTPUT_PATH.open("w", encoding="utf-8") as f:
        for row in existing.values():
            f.write(json.dumps(row, ensure_ascii=False))
            f.write("\n")


def resolver_link(nombre, bgg_id):
    """Arma un slug best-effort a partir del nombre, lo verifica con un
    HEAD real, y devuelve (url, status). Solo tiene sentido guardar `url`
    en universo_juegos.jsonl si status == "200" — el llamador decide eso,
    acá solo se resuelve y se verifica."""
    slug = slugify(nombre)
    if not slug:
        return None, "error"
    url = f"https://www.cazagangas.com.ar/juego/{slug}"
    status = check_status(url)
    if status == "200":
        upsert_cazagangas_cache({nombre: {
            "bgg_id": bgg_id,
            "nombre": nombre,
            "status_http": status,
            "fecha_chequeado": datetime.date.today().isoformat(),
        }})
    return url, status
