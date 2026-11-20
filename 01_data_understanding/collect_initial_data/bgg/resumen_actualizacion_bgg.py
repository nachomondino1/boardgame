"""Resumen de una actualización COMPLETA de BGG: qué juegos subieron o cayeron más en el ranking y
cuáles sumaron más reviews (votos) desde la actualización anterior.

Por qué es un script aparte y no columnas del log por corrida: una actualización completa sale en varias
corridas de refresh_bgg_data.py (BGG corta, se retoma, etc.), y cada corrida vería solo su pedazo. Acá se compara
la tabla entera contra una "foto" (ranking y votos de cada juego) guardada al cerrar la actualización anterior.

Cuándo correrlo: UNA vez, cuando la actualización de BGG ya está completa (todos los juegos con la fecha de
hoy). Suma una fila a `01_data_understanding/actualizaciones/resumen_actualizaciones_bgg.csv` y guarda la foto nueva
(`data/01_data_understanding/bgg_foto.json`, no se versiona) para la próxima vez.

Columnas del CSV:
  fecha                       día en que se armó el resumen
  desde                       fecha de la foto contra la que se compara
  juegos_comparados           juegos con ranking en las dos fotos
  mayores_subidas_ranking     los que más puestos subieron: "Nombre (#antes→#ahora)"
  mayores_caidas_ranking      los que más puestos cayeron, con el mismo formato
  mas_reviews_nuevas          los que más votos sumaron: "Nombre (+N)"
  observacion                 aclaraciones (--nota)

Solo cuentan los juegos con ranking <= --ranking-max (default 5000) en alguna de las dos fotos: más abajo un
salto de miles de puestos no dice nada (un juego del #20.000 al #15.000 casi no cambió de relevancia).

Uso:
    python3 01_data_understanding/collect_initial_data/bgg/resumen_actualizacion_bgg.py [--dry-run] [--top 10] [--nota "..."]
    ... --base-git REF   la primera vez, sin foto: compara contra el docs/data/index.json de ese commit
"""
import argparse
import csv
import datetime
import json
import statistics
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BGG_DATA_PATH = ROOT / "data" / "01_data_understanding" / "bgg_data.jsonl"
FOTO_PATH = ROOT / "data" / "01_data_understanding" / "bgg_foto.json"
CSV_PATH = ROOT / "01_data_understanding" / "actualizaciones" / "resumen_actualizaciones_bgg.csv"
COLUMNAS = ["fecha", "desde", "juegos_comparados", "mayores_subidas_ranking", "mayores_caidas_ranking",
            "mas_reviews_nuevas", "observacion"]


def entero(valor):
    """int de un valor de BGG ("12", 12) o None (vacío, "Not Ranked")."""
    try:
        return int(float(valor))
    except (TypeError, ValueError):
        return None


def foto_actual():
    """{bgg_id: [nombre, ranking, votos]} de bgg_data.jsonl, y la fecha más reciente de actualización."""
    juegos, fechas = {}, set()
    with BGG_DATA_PATH.open(encoding="utf-8") as f:
        for linea in f:
            g = json.loads(linea)
            juegos[g["bgg_id"]] = [g.get("name"), entero(g.get("Board Game Rank")), entero(g.get("usersrated"))]
            fechas.add(g.get("fecha_actualizacion"))
    return juegos, max(f for f in fechas if f)


def foto_de_git(ref):
    """Lo mismo, pero sacado del docs/data/index.json que había en el commit `ref`."""
    salida = subprocess.run(["git", "-C", str(ROOT), "show", f"{ref}:docs/data/index.json"], capture_output=True, text=True, check=True).stdout
    d = json.loads(salida)
    c = d["cols"]
    i_id, i_nom, i_rank, i_votos = (c.index(x) for x in ("bgg_id", "nombre", "ranking_bgg", "reviews_bgg"))
    fecha = subprocess.run(["git", "-C", str(ROOT), "log", "-1", "--format=%ad", "--date=short", ref], capture_output=True, text=True, check=True).stdout.strip()
    return {r[i_id]: [r[i_nom], entero(r[i_rank]), entero(r[i_votos])] for r in d["rows"]}, fecha


def destacados(base, actual, top=10, ranking_max=5000):
    """(comparados, subidas, caidas, mas_reviews) entre dos fotos {bgg_id: [nombre, ranking, votos]}.
    Ranking: BGG numera de 1 para arriba, así que subir es pasar de #20 a #12 (un número más chico)."""
    rank, votos = [], []
    for bgg_id, (nombre, r_nuevo, v_nuevo) in actual.items():
        if bgg_id not in base:
            continue
        _, r_viejo, v_viejo = base[bgg_id]
        if r_viejo and r_nuevo and r_viejo != r_nuevo and min(r_viejo, r_nuevo) <= ranking_max:
            rank.append((r_viejo - r_nuevo, nombre or bgg_id, r_viejo, r_nuevo))  # > 0: subió
        if v_viejo is not None and v_nuevo is not None and v_nuevo > v_viejo:
            votos.append((v_nuevo - v_viejo, nombre or bgg_id))
    comparados = sum(1 for i, v in actual.items() if i in base and v[1] and base[i][1])
    subidas = sorted((x for x in rank if x[0] > 0), reverse=True)[:top]
    caidas = sorted(x for x in rank if x[0] < 0)[:top]
    mas_votos = sorted(votos, reverse=True)[:top]
    return (comparados,
            "; ".join(f"{nom} (#{v}→#{n})" for _, nom, v, n in subidas),
            "; ".join(f"{nom} (#{v}→#{n})" for _, nom, v, n in caidas),
            "; ".join(f"{nom} (+{d:,})".replace(",", ".") for d, nom in mas_votos))


GRUPOS = [("top 500", 1, 500), ("501 a 2.000", 501, 2000), ("2.001 a 5.000", 2001, 5000), ("más abajo de 5.000", 5001, 10**9)]


def tabla_por_grupo(base, actual):
    """Texto con cuánto se movió cada grupo del ranking (según su puesto en la foto vieja): sirve para
    decidir cada cuánto actualizar cada grupo. Se imprime, no va al CSV."""
    lineas = [f"{'grupo (puesto en la foto vieja)':<32}{'juegos':>8}{'cambió ranking':>16}{'mediana puestos':>17}{'mediana votos nuevos':>22}{'crecim. votos':>15}"]
    for nombre, desde, hasta in GRUPOS:
        movs, votos, crec, n = [], [], [], 0
        for bgg_id, (_, r_viejo, v_viejo) in base.items():
            if not r_viejo or not desde <= r_viejo <= hasta or bgg_id not in actual:
                continue
            _, r_nuevo, v_nuevo = actual[bgg_id]
            n += 1
            if r_nuevo:
                movs.append(abs(r_viejo - r_nuevo))
            if v_viejo is not None and v_nuevo is not None:
                votos.append(v_nuevo - v_viejo)
                if v_viejo:
                    crec.append(100 * (v_nuevo - v_viejo) / v_viejo)
        if not n:
            continue
        cambio = 100 * sum(1 for m in movs if m) / len(movs) if movs else 0
        med = lambda xs: statistics.median(xs) if xs else 0
        lineas.append(f"{nombre:<32}{n:>8}{cambio:>15.0f}%{med(movs):>17.0f}{med(votos):>22.0f}{med(crec):>14.1f}%")
    return "\n".join(lineas)


def escribir_fila(fila):
    nuevo = not CSV_PATH.exists()
    with CSV_PATH.open("a", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNAS)
        if nuevo:
            w.writeheader()
        w.writerow(fila)


def main():
    parser = argparse.ArgumentParser(description="Resumen de movimientos de ranking y reviews de una actualización completa de BGG")
    parser.add_argument("--top", type=int, default=10, help="cuántos juegos listar en cada columna")
    parser.add_argument("--ranking-max", type=int, default=5000, help="ignorar movimientos de juegos que están siempre más abajo de este puesto")
    parser.add_argument("--base-git", metavar="REF", help="comparar contra el docs/data/index.json de un commit (la primera vez, sin foto)")
    parser.add_argument("--solo-sin-cambios-hasta", metavar="REF2", help="con --base-git: comparar solo los juegos que NO cambiaron entre ese commit y REF2 "
                        "(los que una actualización parcial todavía no había tocado, p. ej. para dejar afuera los que venían de la copia de 2025)")
    parser.add_argument("--desde", help="fecha a anotar en `desde` si no es la del commit de --base-git (p. ej. cuando esos valores son de una actualización anterior al commit)")
    parser.add_argument("--nota", default="", help="observación para el CSV")
    parser.add_argument("--dry-run", action="store_true", help="muestra el resumen sin escribir el CSV ni la foto")
    args = parser.parse_args()

    actual, fecha_actual = foto_actual()
    if args.base_git:
        base, desde = foto_de_git(args.base_git)
        if args.solo_sin_cambios_hasta:
            intermedia, _ = foto_de_git(args.solo_sin_cambios_hasta)
            base = {i: v for i, v in base.items() if intermedia.get(i, [None, None, None])[1:] == v[1:]}
    elif FOTO_PATH.exists():
        foto = json.loads(FOTO_PATH.read_text(encoding="utf-8"))
        base, desde = foto["juegos"], foto["fecha"]
    else:
        raise SystemExit("No hay foto anterior: la primera vez usá --base-git <commit> (ver el docstring).")
    desde = args.desde or desde
    comparados, subidas, caidas, mas_reviews = destacados(base, actual, args.top, args.ranking_max)
    fila = {"fecha": datetime.date.today().isoformat(), "desde": desde, "juegos_comparados": comparados,
            "mayores_subidas_ranking": subidas, "mayores_caidas_ranking": caidas, "mas_reviews_nuevas": mas_reviews,
            "observacion": args.nota}
    for campo in COLUMNAS:
        print(f"{campo}: {fila[campo]}")
    print("\nCuánto se movió cada grupo (no va al CSV):\n" + tabla_por_grupo(base, actual))
    if args.dry_run:
        print("(dry-run: no se escribió nada)")
        return
    escribir_fila(fila)
    FOTO_PATH.write_text(json.dumps({"fecha": fecha_actual, "juegos": actual}, ensure_ascii=False), encoding="utf-8")
    print(f"OK: fila en {CSV_PATH.name} y foto nueva ({fecha_actual}) en {FOTO_PATH.name}")


if __name__ == "__main__":
    main()
