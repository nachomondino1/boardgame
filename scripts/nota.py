"""Agrega una nota personal a un juego (data/01_data_understanding/mis_notas.jsonl).

Las notas son solo para vos: el archivo está gitignored y build_catalog.py las vuelca a
docs/data/notas.json, que tampoco se versiona, así que se ven en local y no en el sitio publicado.

Uso:
    python3 scripts/nota.py "Heat" "la rejugabilidad me preocupa un poco"
    python3 scripts/nota.py 366013 < nota.txt          # texto por stdin (varias líneas)
    python3 scripts/nota.py "Heat" "texto" --fecha "2026-11-22 20:28"   # fecha distinta de ahora

El juego se busca por bgg_id o por nombre (sin acentos ni mayúsculas) en docs/data/names.json; si el
nombre da más de un juego, lista las opciones y no escribe nada: repetí con el bgg_id.
Después corré `python3 02_data_preparation/build_catalog.py` para verla en la web local.
"""
import argparse
import json
import sys
import unicodedata
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NAMES_PATH = ROOT / "docs" / "data" / "names.json"
NOTAS_PATH = ROOT / "data" / "01_data_understanding" / "mis_notas.jsonl"


def plain(text):
    return "".join(c for c in unicodedata.normalize("NFD", text.lower()) if unicodedata.category(c) != "Mn")


def buscar(consulta):
    filas = json.loads(NAMES_PATH.read_text(encoding="utf-8"))["rows"]
    exactos = [f for f in filas if f[0] == consulta]
    if exactos:
        return exactos
    q = plain(consulta)
    return [f for f in filas if q in plain(f[1]) or q in plain(f[2])]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("juego", help="bgg_id o nombre")
    ap.add_argument("texto", nargs="?", help="texto de la nota (si falta, se lee de stdin)")
    ap.add_argument("--fecha", help="AAAA-MM-DD HH:MM (por defecto, ahora)")
    args = ap.parse_args()

    texto = (args.texto if args.texto is not None else sys.stdin.read()).strip()
    if not texto:
        raise SystemExit("La nota está vacía.")
    encontrados = buscar(args.juego)
    if len(encontrados) != 1:
        print(f"{len(encontrados)} juegos para {args.juego!r}; repetí con el bgg_id de uno:" if encontrados else f"No encontré {args.juego!r}.")
        for f in encontrados[:15]:
            print(f"  {f[0]}  {f[1]} ({f[3]})")
        raise SystemExit(1)
    bgg_id, nombre = encontrados[0][0], encontrados[0][1]
    nota = {"bgg_id": bgg_id, "nombre": nombre, "fecha": args.fecha or datetime.now().strftime("%Y-%m-%d %H:%M"), "texto": texto}
    NOTAS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with NOTAS_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(nota, ensure_ascii=False) + "\n")
    print(f"Nota guardada para {nombre} ({bgg_id}), {nota['fecha']}.")


if __name__ == "__main__":
    main()
